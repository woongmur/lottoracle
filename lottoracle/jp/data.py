"""일본 로또 당첨번호 수집 / 대조 / 저장.

원본은 미즈호은행(당첨번호 공식 발표처)이지만 일본 밖 접속을 막는다(Akamai 403,
GitHub Actions 러너도 마찬가지). 그래서 일본의 당첨번호 집계 사이트 둘에서 1회부터의
전체 이력 CSV 를 받고, 라쿠텐 다카라쿠지의 '최근 10회' 표로 한 번 더 맞춰 본다.

  thekyo     loto6.thekyo.jp 등. 1회부터 전체 CSV (Shift_JIS)
  loto-life  loto-life.net. 1회부터 전체 CSV (Shift_JIS). 열 순서가 thekyo 와 다르다
  rakuten    takarakuji.rakuten.co.jp. 최근 10회 (HTML)

세 곳은 서로 독립된 운영처라, 둘 이상이 같은 값을 내야 받아들인다. 어느 한 곳이
잘못 적거나 형식을 바꾸면 갱신을 멈추고(예외) 워크플로가 실패 알림을 띄운다.
이미 저장된 과거 회차가 바뀌어 들어와도 멈춘다 — 조용히 덮어쓰지 않는다.

전체 이력을 받은 두 CSV 를 1회부터 대조해 본 결과(2026-10-14), 로또6 2,145회 ·
로또7 698회 · 미니로또 1,408회 모두 날짜·번호·보너스가 한 개도 다르지 않았다.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .games import GAMES, Game, get

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(ROOT, "data", "jp")
WEB_DATA_DIR = os.path.join(ROOT, "web", "data", "jp")

SOURCES: dict[str, dict[str, str]] = {
    "thekyo": {
        "loto6": "https://loto6.thekyo.jp/data/loto6.csv",
        "loto7": "https://loto7.thekyo.jp/data/loto7.csv",
        "miniloto": "https://miniloto.thekyo.jp/data/miniloto.csv",
    },
    "loto-life": {
        "loto6": "https://loto-life.net/csv/loto6",
        "loto7": "https://loto-life.net/csv/loto7",
        "miniloto": "https://loto-life.net/csv/mini",
    },
    "rakuten": {
        "loto6": "https://takarakuji.rakuten.co.jp/backnumber/loto6/lastresults/",
        "loto7": "https://takarakuji.rakuten.co.jp/backnumber/loto7/lastresults/",
        "miniloto": "https://takarakuji.rakuten.co.jp/backnumber/mini/lastresults/",
    },
}
CSV_SOURCES = ("thekyo", "loto-life")
USER_AGENT = "Mozilla/5.0 (compatible; lottoracle/1.0; +https://lottoracle.com)"


class SourceError(Exception):
    """원본이 이상하다 — 형식이 바뀌었거나, 서로 다르거나, 과거 값이 바뀌었다."""


@dataclass(frozen=True)
class JpDraw:
    """한 회차의 당첨 결과."""

    no: int
    date: str                         # YYYY-MM-DD
    numbers: tuple[int, ...]          # 본숫자 (오름차순)
    bonus: tuple[int, ...]            # 보너스 숫자 (로또7 은 2개, 추첨 순서 그대로)
    prizes: tuple[tuple[int, int], ...] = ()  # 등수별 (당첨 口수, 1口당 금액 엔). 비면 정보 없음
    carryover: int = -1               # 이월금 (엔). -1 은 정보 없음 또는 이월 없는 게임

    def key(self) -> tuple:
        """원본끼리 맞춰 볼 때 쓰는 값. 당첨금은 원본마다 늦게 채워지기도 해서 뺀다."""
        return (self.no, self.date, self.numbers, self.bonus)

    def to_dict(self) -> dict:
        out: dict = {"no": self.no, "date": self.date,
                     "numbers": list(self.numbers), "bonus": list(self.bonus)}
        if self.prizes:
            out["prizes"] = [list(p) for p in self.prizes]
        if self.carryover >= 0:
            out["carryover"] = self.carryover
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> "JpDraw":
        return cls(
            no=int(raw["no"]),
            date=str(raw["date"]),
            numbers=tuple(int(n) for n in raw["numbers"]),
            bonus=tuple(int(n) for n in raw["bonus"]),
            prizes=tuple((int(w), int(a)) for w, a in raw.get("prizes", ())),
            carryover=int(raw.get("carryover", -1)),
        )


# ---------------------------------------------------------------- 파싱

def decode(raw: bytes) -> str:
    """두 CSV 는 Shift_JIS(CP932). 나중에 UTF-8 로 바뀌어도 읽히게 한다."""
    for enc in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise SourceError("CSV 인코딩을 알 수 없습니다")


def _date(text: str) -> str:
    m = re.fullmatch(r"\s*(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s*", text)
    if not m:
        raise SourceError(f"날짜 형식이 아닙니다: {text!r}")
    y, mo, d = (int(x) for x in m.groups())
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _int(text: str) -> int:
    return int(text.replace(",", "").strip())


def _columns(game: Game, header: Sequence[str]) -> dict:
    """열 이름으로 위치를 잡는다. 두 CSV 는 열 순서가 다르고 이름도 조금 다르다."""
    cols: dict = {"main": {}, "bonus": {}, "winners": {}, "amount": {}}
    for i, name in enumerate(h.strip() for h in header):
        if name == "開催回":
            cols["no"] = i
        elif name in ("日付", "開催日"):
            cols["date"] = i
        elif m := re.fullmatch(r"第(\d)数字", name):
            cols["main"][int(m[1])] = i
        elif m := re.fullmatch(r"(?:BONUS|ボーナス)数字(\d?)", name):
            cols["bonus"][int(m[1] or 1)] = i
        elif m := re.fullmatch(r"(\d)等口数", name):
            cols["winners"][int(m[1])] = i
        elif m := re.fullmatch(r"(\d)等賞金", name):
            cols["amount"][int(m[1])] = i
        elif name == "キャリーオーバー":
            cols["carryover"] = i
    want = {
        "no": "no" in cols, "date": "date" in cols,
        "main": sorted(cols["main"]) == list(range(1, game.pick + 1)),
        "bonus": sorted(cols["bonus"]) == list(range(1, game.bonus + 1)),
        "winners": sorted(cols["winners"]) == list(range(1, game.ranks + 1)),
        "amount": sorted(cols["amount"]) == list(range(1, game.ranks + 1)),
    }
    missing = [k for k, ok in want.items() if not ok]
    if missing:
        raise SourceError(f"{game.name} CSV 열이 예상과 다릅니다 ({', '.join(missing)}): {list(header)}")
    return cols


def parse_csv(game: Game | str, text: str) -> list[JpDraw]:
    """전체 이력 CSV 한 장. 열 이름(일본어)으로 읽어서 두 사이트 모두 받는다."""
    game = get(game) if isinstance(game, str) else game
    rows = [r for r in csv.reader(io.StringIO(text)) if r and any(c.strip() for c in r)]
    if not rows:
        raise SourceError(f"{game.name} CSV 가 비었습니다")
    cols = _columns(game, rows[0])
    out: list[JpDraw] = []
    for row in rows[1:]:
        cell = lambda i: row[i].strip() if i < len(row) else ""  # noqa: E731
        if not cell(cols["no"]).isdigit():
            continue
        prizes: tuple[tuple[int, int], ...] = ()
        try:
            prizes = tuple((_int(cell(cols["winners"][r])), _int(cell(cols["amount"][r])))
                           for r in range(1, game.ranks + 1))
        except ValueError:
            prizes = ()  # 추첨 직후 당첨금이 아직 비어 있는 줄
        carry = -1
        if game.carryover and "carryover" in cols and cell(cols["carryover"]).replace(",", "").isdigit():
            carry = _int(cell(cols["carryover"]))
        try:
            out.append(JpDraw(
                no=int(cell(cols["no"])),
                date=_date(cell(cols["date"])),
                numbers=tuple(sorted(int(cell(cols["main"][k])) for k in range(1, game.pick + 1))),
                bonus=tuple(int(cell(cols["bonus"][k])) for k in range(1, game.bonus + 1)),
                prizes=prizes,
                carryover=carry,
            ))
        except ValueError as exc:
            raise SourceError(f"{game.name} CSV {cell(cols['no'])}회 줄을 읽지 못했습니다: {row}") from exc
    return out


_RAKUTEN_ROW = re.compile(r"<span>\s*第0*(\d+)回\s*</span>\s*(\d{4}/\d{1,2}/\d{1,2})(.*?)</tr>", re.S)
_RAKUTEN_UL = re.compile(r'<ul class="loto-popup-number( num-bonus)?">(.*?)</ul>', re.S)
_LI = re.compile(r"<li>\s*(\d+)\s*</li>")


def parse_rakuten(game: Game | str, html: str) -> list[JpDraw]:
    """라쿠텐 '직근 10회' 표. 당첨금은 없고 번호·보너스·날짜만 있다."""
    game = get(game) if isinstance(game, str) else game
    out: list[JpDraw] = []
    for m in _RAKUTEN_ROW.finditer(html):
        main: list[int] = []
        bonus: list[int] = []
        for ul in _RAKUTEN_UL.finditer(m[3]):
            (bonus if ul[1] else main).extend(int(x) for x in _LI.findall(ul[2]))
        out.append(JpDraw(no=int(m[1]), date=_date(m[2]),
                          numbers=tuple(sorted(main)), bonus=tuple(bonus)))
    if not out:
        raise SourceError(f"{game.name} 라쿠텐 표에서 회차를 하나도 찾지 못했습니다 (형식 변경?)")
    return out


# ---------------------------------------------------------------- 검사·대조

def check_draw(game: Game, d: JpDraw) -> None:
    """한 회차가 게임 규칙에 맞는가. 하나라도 어긋나면 원본이 잘못된 것이다."""
    where = f"{game.name} {d.no}회"
    if len(d.numbers) != game.pick or len(set(d.numbers)) != game.pick:
        raise SourceError(f"{where}: 본숫자가 서로 다른 {game.pick}개가 아닙니다 {d.numbers}")
    if len(d.bonus) != game.bonus or len(set(d.bonus)) != game.bonus:
        raise SourceError(f"{where}: 보너스가 서로 다른 {game.bonus}개가 아닙니다 {d.bonus}")
    if set(d.numbers) & set(d.bonus):
        raise SourceError(f"{where}: 보너스가 본숫자와 겹칩니다 {d.numbers} + {d.bonus}")
    if not all(1 <= n <= game.pool for n in d.numbers + d.bonus):
        raise SourceError(f"{where}: 1~{game.pool} 밖의 숫자가 있습니다 {d.numbers} + {d.bonus}")
    if d.prizes and len(d.prizes) != game.ranks:
        raise SourceError(f"{where}: 등수가 {game.ranks}개가 아닙니다")


def check_series(game: Game, draws: Sequence[JpDraw]) -> None:
    """1회부터 빠짐없이, 날짜는 앞으로만."""
    for i, d in enumerate(draws):
        check_draw(game, d)
        if d.no != i + 1:
            raise SourceError(f"{game.name}: {i + 1}회가 있어야 할 자리에 {d.no}회가 있습니다")
        if i and d.date <= draws[i - 1].date:
            raise SourceError(f"{game.name}: {d.no}회 날짜 {d.date} 가 앞 회차({draws[i - 1].date})보다 빠릅니다")


def agree(game: Game, a: Sequence[JpDraw], b: Sequence[JpDraw], what: str) -> int:
    """겹치는 회차가 모두 같아야 한다. 겹친 개수를 돌려준다."""
    bmap = {d.no: d for d in b}
    same = 0
    for d in a:
        other = bmap.get(d.no)
        if other is None:
            continue
        if d.key() != other.key():
            raise SourceError(f"{game.name} {d.no}회가 {what}에서 다릅니다: {d.key()} ≠ {other.key()}")
        if d.prizes and other.prizes and d.prizes != other.prizes:
            raise SourceError(f"{game.name} {d.no}회 당첨금이 {what}에서 다릅니다")
        same += 1
    return same


def combine(game: Game, sources: dict[str, list[JpDraw]]) -> tuple[list[JpDraw], list[str]]:
    """받은 원본들을 하나로. 둘 이상이 있어야 하고, 겹치는 곳은 모두 같아야 한다.

    전체 이력 CSV 가 적어도 하나 있어야 한다(라쿠텐은 최근 10회뿐이라 대조용).
    한쪽이 먼저 갱신돼 최신 회차가 하나에만 있으면 그대로 받는다 — 그 회차도
    라쿠텐 표에 있으면 거기서 맞춰 본다.
    """
    full = [name for name in CSV_SOURCES if name in sources]
    if not full:
        raise SourceError(f"{game.name}: 전체 이력 CSV 를 하나도 받지 못했습니다")
    if len(sources) < 2:
        raise SourceError(f"{game.name}: 원본이 {', '.join(sources)} 하나뿐이라 대조할 수 없습니다")
    notes: list[str] = []
    names = list(sources)
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            n = agree(game, sources[x], sources[y], f"{x}·{y} 사이")
            if n == 0:
                raise SourceError(f"{game.name}: {x}·{y} 사이에 겹치는 회차가 없어 대조할 수 없습니다")
            notes.append(f"{x}·{y} {n}회 일치")
    merged: dict[int, JpDraw] = {}
    for name in full + [n for n in names if n not in full]:
        for d in sources[name]:
            have = merged.get(d.no)
            if have is None or (not have.prizes and d.prizes):
                merged[d.no] = d
    return [merged[k] for k in sorted(merged)], notes


def merge_cache(game: Game, cached: Sequence[JpDraw], fresh: Sequence[JpDraw]) -> list[JpDraw]:
    """저장본에 새 회차를 잇는다. 과거 회차의 날짜·번호가 바뀌어 오면 멈춘다."""
    agree(game, cached, fresh, "저장본과 새 원본 사이")
    out = {d.no: d for d in cached}
    for d in fresh:
        # 번호는 위에서 같다고 확인했다. 당첨금이 있는 쪽이 새로 오면 그것으로 바꾼다
        # (라쿠텐에서만 먼저 받은 회차는 당첨금이 비어 있다가 CSV 가 따라오면 채워진다).
        if d.no not in out or d.prizes:
            out[d.no] = d
    return [out[k] for k in sorted(out)]


# ---------------------------------------------------------------- 입출력

def path_of(game: Game | str, base: str = DATA_DIR) -> str:
    key = game if isinstance(game, str) else game.key
    return os.path.join(base, f"{key}.json")


def dumps(game: Game, draws: Iterable[JpDraw]) -> str:
    """한 회차 한 줄. 매주 커밋 diff 가 새 줄 몇 개로만 보이게 한다."""
    lines = [json.dumps(d.to_dict(), ensure_ascii=False, separators=(",", ":")) for d in draws]
    head = json.dumps({"game": game.key, "name": game.name, "pool": game.pool,
                       "pick": game.pick, "bonus": game.bonus},
                      ensure_ascii=False, separators=(",", ":"))
    return head[:-1] + ',"draws":[\n' + ",\n".join(lines) + "\n]}\n"


def save(game: Game, draws: Sequence[JpDraw], *dirs: str) -> None:
    text = dumps(game, draws)
    for base in dirs or (DATA_DIR, WEB_DATA_DIR):
        os.makedirs(base, exist_ok=True)
        with open(path_of(game, base), "w", encoding="utf-8") as fp:
            fp.write(text)


def load(game: Game | str, base: str = DATA_DIR, required: bool = True) -> list[JpDraw]:
    p = path_of(game, base)
    if not os.path.exists(p):
        if required:
            raise FileNotFoundError(f"일본 로또 데이터가 없습니다: {p}\n먼저 `python3 tools/fetch_jp.py` 를 실행하세요.")
        return []
    with open(p, encoding="utf-8") as fp:
        raw = json.load(fp)
    return [JpDraw.from_dict(r) for r in raw["draws"]]


def download(url: str, timeout: float = 30.0, retries: int = 2) -> bytes:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise SourceError(f"받지 못했습니다: {url} ({last})")


@dataclass
class Report:
    game: str
    before: int
    after: int
    notes: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def line(self) -> str:
        head = f"{GAMES[self.game].name}: {self.before} → {self.after}회"
        tail = "; ".join(self.notes + [f"{s} 건너뜀" for s in self.skipped])
        return f"{head} ({tail})" if tail else head


def update(game: Game | str, fetch: Callable[[str], bytes] = download,
           data_dir: str = DATA_DIR, web_dir: str | None = WEB_DATA_DIR) -> Report:
    """원본들을 받아 대조하고 저장본에 잇는다. 원본 하나가 안 열리면 나머지로 간다."""
    game = get(game) if isinstance(game, str) else game
    sources: dict[str, list[JpDraw]] = {}
    skipped: list[str] = []
    for name, urls in SOURCES.items():
        try:
            raw = fetch(urls[game.key])
        except SourceError as exc:
            skipped.append(f"{name}({exc})")
            continue
        text = decode(raw)
        sources[name] = parse_rakuten(game, text) if name == "rakuten" else parse_csv(game, text)
    fresh, notes = combine(game, sources)
    cached = load(game, data_dir, required=False)
    draws = merge_cache(game, cached, fresh)
    check_series(game, draws)
    save(game, draws, *([data_dir] + ([web_dir] if web_dir else [])))
    return Report(game.key, max((d.no for d in cached), default=0), draws[-1].no, notes, skipped)
