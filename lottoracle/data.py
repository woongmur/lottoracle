"""당첨 회차 데이터 수집 / 캐시 / 로드."""

from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence

# 동행복권 회차별 당첨정보 API. srchLtEpsd 를 생략하면 최신 회차가 온다.
API_URL = "https://www.dhlottery.co.kr/lt645/selectPstLt645Info.do"
FIRST_DRAW_DATE = date(2002, 12, 7)  # 1회차 추첨일 (토요일)
DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "draws.json"
)


@dataclass(frozen=True)
class Prize:
    """한 등수의 당첨 현황."""

    rank: int
    winners: int    # 당첨 게임 수
    amount: int     # 1게임당 당첨금 (원)
    total: int = 0  # 그 등수 총 당첨금 (원)

    def to_dict(self) -> dict:
        return {"rank": self.rank, "winners": self.winners, "amount": self.amount, "total": self.total}

    @classmethod
    def from_dict(cls, raw: dict) -> "Prize":
        return cls(
            rank=int(raw["rank"]),
            winners=int(raw.get("winners", 0)),
            amount=int(raw.get("amount", 0)),
            total=int(raw.get("total", 0)),
        )


@dataclass(frozen=True)
class Draw:
    """한 회차의 당첨 결과."""

    no: int
    numbers: tuple[int, ...]  # 당첨번호 6개 (오름차순)
    bonus: int
    draw_date: str = ""
    first_winners: int = -1     # 1등 당첨 게임 수 (-1: 정보 없음)
    first_prize: int = -1       # 1게임당 1등 당첨금 (원, -1: 정보 없음)
    prizes: tuple[Prize, ...] = ()   # 1~5등 전체. 빈 튜플이면 아직 안 받아온 회차
    total_sales: int = -1       # 해당 회차 총 판매금액 (-1: 정보 없음)

    def __post_init__(self) -> None:
        if len(self.numbers) != 6:
            raise ValueError(f"{self.no}회차: 당첨번호는 6개여야 합니다 ({self.numbers})")
        if len(set(self.numbers)) != 6:
            raise ValueError(f"{self.no}회차: 당첨번호가 중복됩니다 ({self.numbers})")
        for n in (*self.numbers, self.bonus):
            if not 1 <= n <= 45:
                raise ValueError(f"{self.no}회차: 번호는 1~45 범위여야 합니다 ({n})")
        if self.bonus in self.numbers:
            raise ValueError(f"{self.no}회차: 보너스번호가 당첨번호와 겹칩니다")
        # 1~5등을 받아온 회차면 1등 요약 필드를 거기에 맞춘다 (옛 캐시와 호환).
        first = next((p for p in self.prizes if p.rank == 1), None)
        if first is not None:
            object.__setattr__(self, "first_winners", first.winners)
            object.__setattr__(self, "first_prize", first.amount)

    @property
    def all_numbers(self) -> tuple[int, ...]:
        """당첨번호 6개 + 보너스."""
        return (*self.numbers, self.bonus)

    @property
    def has_prizes(self) -> bool:
        """1~5등 당첨 현황을 갖고 있는 회차인지."""
        return len(self.prizes) == 5

    def prize_of(self, rank: int) -> Prize | None:
        return next((p for p in self.prizes if p.rank == rank), None)

    def to_dict(self) -> dict:
        out = {
            "no": self.no,
            "numbers": list(self.numbers),
            "bonus": self.bonus,
            "draw_date": self.draw_date,
        }
        if self.first_winners >= 0:
            out["first_winners"] = self.first_winners
        if self.first_prize >= 0:
            out["first_prize"] = self.first_prize
        if self.prizes:
            out["prizes"] = [p.to_dict() for p in self.prizes]
        if self.total_sales >= 0:
            out["total_sales"] = self.total_sales
        return out

    @classmethod
    def from_dict(cls, raw: dict) -> "Draw":
        return cls(
            no=int(raw["no"]),
            numbers=tuple(sorted(int(n) for n in raw["numbers"])),
            bonus=int(raw["bonus"]),
            draw_date=str(raw.get("draw_date", "")),
            first_winners=int(raw.get("first_winners", -1)),
            first_prize=int(raw.get("first_prize", -1)),
            prizes=tuple(Prize.from_dict(p) for p in raw.get("prizes", ())),
            total_sales=int(raw.get("total_sales", -1)),
        )


def estimate_latest_draw_no(today: date | None = None) -> int:
    """오늘 날짜 기준으로 존재할 법한 최신 회차 번호를 추정한다."""
    today = today or date.today()
    weeks = (today - FIRST_DRAW_DATE).days // 7
    return max(1, weeks + 1)


# ---------------------------------------------------------------- 원격 수집

def _parse_payload(payload: dict) -> Draw | None:
    """selectPstLt645Info.do 응답(JSON)을 Draw 로 바꾼다. 회차가 없으면 None.

    응답 예::

        {"resultCode": null, "resultMessage": null,
         "data": {"list": [{"ltEpsd": 1239, "tm1WnNo": 11, ..., "tm6WnNo": 36,
                            "bnsWnNo": 8, "ltRflYmd": "20260829",
                            "rnk1WnNope": 13, "rnk1WnAmt": 2214789375,
                            "rnk1SumWnAmt": 28792261875, ... "rnk5WnAmt": 5000,
                            "rlvtEpsdSumNtslAmt": 58883645203}]}}
    """
    items = ((payload or {}).get("data") or {}).get("list") or []
    if not items:
        return None
    row = items[0]
    ymd = str(row.get("ltRflYmd") or "")
    draw_date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}" if len(ymd) == 8 else ymd
    prizes = []
    for rank in range(1, 6):
        if f"rnk{rank}WnNope" not in row:
            continue
        prizes.append(Prize(
            rank=rank,
            winners=int(row.get(f"rnk{rank}WnNope", 0) or 0),
            amount=int(row.get(f"rnk{rank}WnAmt", 0) or 0),
            total=int(row.get(f"rnk{rank}SumWnAmt", 0) or 0),
        ))
    return Draw(
        no=int(row["ltEpsd"]),
        numbers=tuple(sorted(int(row[f"tm{i}WnNo"]) for i in range(1, 7))),
        bonus=int(row["bnsWnNo"]),
        draw_date=draw_date,
        first_winners=int(row.get("rnk1WnNope", -1)),
        first_prize=int(row.get("rnk1WnAmt", -1)),
        prizes=tuple(prizes),
        total_sales=int(row.get("rlvtEpsdSumNtslAmt", -1) or -1),
    )


def _request(no: int | None, timeout: float, retries: int = 2) -> dict:
    """API 를 호출해 JSON 을 돌려준다. 일시적 네트워크 오류는 retries 번 더 시도한다."""
    url = API_URL if no is None else f"{API_URL}?srchLtEpsd={no}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "lottoracle/0.1", "Accept": "application/json"}
    )
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last_err = err
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
    assert last_err is not None
    raise last_err


def fetch_draw(no: int, timeout: float = 10.0) -> Draw | None:
    """동행복권 공개 API에서 한 회차를 가져온다. 아직 추첨 전이면 None."""
    return _parse_payload(_request(no, timeout))


def fetch_latest(timeout: float = 10.0) -> Draw | None:
    """API가 알려주는 가장 최근 추첨 회차를 가져온다."""
    return _parse_payload(_request(None, timeout))


def fetch_range(start: int, end: int, timeout: float = 10.0) -> list[Draw]:
    """[start, end] 구간을 순차 수집한다. 미추첨 회차를 만나면 거기서 멈춘다."""
    out: list[Draw] = []
    for no in range(start, end + 1):
        draw = fetch_draw(no, timeout=timeout)
        if draw is None:
            break
        out.append(draw)
    return out


def update_cache(path: str = DEFAULT_CACHE, timeout: float = 10.0) -> list[Draw]:
    """캐시에 없는 최신 회차만 이어서 받아 저장한다."""
    draws = load_draws(path, required=False)
    start = (max(d.no for d in draws) + 1) if draws else 1
    newest = fetch_latest(timeout=timeout)
    if newest is not None:
        end = newest.no
    else:
        end = estimate_latest_draw_no() + 1  # 추정이 하나 밀릴 수 있으니 여유를 둔다
    if start <= end:
        draws.extend(fetch_range(start, end, timeout=timeout))
    save_draws(draws, path)
    return draws


# ---------------------------------------------------------------- 로컬 입출력

def save_draws(draws: Iterable[Draw], path: str = DEFAULT_CACHE) -> None:
    ordered = sorted(draws, key=lambda d: d.no)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump([d.to_dict() for d in ordered], fp, ensure_ascii=False, indent=1)


def load_draws(path: str = DEFAULT_CACHE, required: bool = True) -> list[Draw]:
    """캐시 파일을 읽는다. required=False면 파일이 없을 때 빈 리스트."""
    if not os.path.exists(path):
        if required:
            raise FileNotFoundError(
                f"데이터 캐시가 없습니다: {path}\n먼저 `python -m lottoracle fetch` 를 실행하세요."
            )
        return []
    with open(path, encoding="utf-8") as fp:
        raw = json.load(fp)
    return sorted((Draw.from_dict(r) for r in raw), key=lambda d: d.no)


def load_csv(path: str) -> list[Draw]:
    """CSV 수동 입력 지원. 헤더 없이 `회차,n1,n2,n3,n4,n5,n6,보너스[,날짜]`."""
    draws: list[Draw] = []
    with open(path, encoding="utf-8-sig", newline="") as fp:
        for row in csv.reader(fp):
            cells = [c.strip() for c in row if c.strip()]
            if not cells or not cells[0].lstrip("-").isdigit():
                continue  # 헤더/빈 줄 건너뛰기
            draws.append(
                Draw(
                    no=int(cells[0]),
                    numbers=tuple(sorted(int(c) for c in cells[1:7])),
                    bonus=int(cells[7]),
                    draw_date=cells[8] if len(cells) > 8 else "",
                )
            )
    return sorted(draws, key=lambda d: d.no)


# ---------------------------------------------------------------- 엑셀(xlsx)
_XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _digits(text: str) -> int:
    """'13 명', '2,214,789,375 원' 같은 문자열에서 정수만 뽑는다. 없으면 -1."""
    found = re.sub(r"[^0-9]", "", text or "")
    return int(found) if found else -1


def _xlsx_rows(path: str) -> list[dict[str, str]]:
    """첫 시트를 {열문자: 값} 딕셔너리 목록으로 읽는다. 외부 라이브러리 불필요."""
    with zipfile.ZipFile(path) as z:
        strings: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter(f"{_XLSX_NS}si"):
                strings.append("".join(t.text or "" for t in si.iter(f"{_XLSX_NS}t")))
        sheet_names = sorted(
            n for n in z.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        if not sheet_names:
            raise ValueError("시트를 찾을 수 없습니다.")
        root = ET.fromstring(z.read(sheet_names[0]))

    rows: list[dict[str, str]] = []
    for row in root.iter(f"{_XLSX_NS}row"):
        cells: dict[str, str] = {}
        for c in row.findall(f"{_XLSX_NS}c"):
            v = c.find(f"{_XLSX_NS}v")
            if v is None or v.text is None:
                continue
            value = strings[int(v.text)] if c.get("t") == "s" else v.text
            col = "".join(ch for ch in (c.get("r") or "") if ch.isalpha())
            cells[col] = value
        rows.append(cells)
    return rows


def load_xlsx(path: str) -> list[Draw]:
    """동행복권 '회차별 당첨번호' 엑셀 내보내기를 읽는다.

    기대 열: 회차 | 당첨번호 6칸 | 보너스 | (순위) | 당첨게임수 | 1게임당 당첨금액.
    헤더 행은 '회차' 글자가 있는 행으로 찾고, 그 아래를 데이터로 본다.
    """
    rows = _xlsx_rows(path)
    header_idx = next(
        (i for i, r in enumerate(rows) if any("회차" in v for v in r.values())), None
    )
    if header_idx is None:
        raise ValueError("'회차' 헤더를 찾을 수 없습니다. 동행복권 엑셀 형식인지 확인하세요.")
    header = rows[header_idx]
    col_no = next(k for k, v in header.items() if "회차" in v)
    col_first = next(k for k, v in header.items() if "당첨번호" in v)
    cols = [chr(ord(col_first) + i) for i in range(6)]
    col_bonus = chr(ord(col_first) + 6)
    col_winners = next((k for k, v in header.items() if "게임수" in v), None)
    col_prize = next((k for k, v in header.items() if "금액" in v), None)

    draws: list[Draw] = []
    for r in rows[header_idx + 1:]:
        try:
            no = int(float(r[col_no]))
            nums = tuple(sorted(int(float(r[c])) for c in cols))
            bonus = int(float(r[col_bonus]))
        except (KeyError, ValueError):
            continue
        draws.append(
            Draw(
                no=no,
                numbers=nums,
                bonus=bonus,
                first_winners=_digits(r.get(col_winners, "")) if col_winners else -1,
                first_prize=_digits(r.get(col_prize, "")) if col_prize else -1,
            )
        )
    if not draws:
        raise ValueError("엑셀에서 회차 데이터를 한 줄도 읽지 못했습니다.")
    return sorted(draws, key=lambda d: d.no)


def load_any(path: str) -> list[Draw]:
    """확장자로 판단해 xlsx / csv / json 을 읽는다."""
    lower = path.lower()
    if lower.endswith(".xlsx"):
        return load_xlsx(path)
    if lower.endswith(".csv"):
        return load_csv(path)
    return load_draws(path)


def merge(base: Sequence[Draw], incoming: Sequence[Draw]) -> list[Draw]:
    """회차 번호 기준으로 합친다. 같은 회차는 incoming 이 이긴다."""
    by_no = {d.no: d for d in base}
    by_no.update({d.no: d for d in incoming})
    return sorted(by_no.values(), key=lambda d: d.no)


def latest(draws: Sequence[Draw]) -> Draw | None:
    return max(draws, key=lambda d: d.no) if draws else None


def next_draw_date(today: date | None = None) -> date:
    """다음 추첨일(토요일)을 돌려준다."""
    today = today or date.today()
    return today + timedelta(days=(5 - today.weekday()) % 7 or 7)
