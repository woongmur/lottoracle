"""당첨 회차 데이터 수집 / 캐시 / 로드."""

from __future__ import annotations

import csv
import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={no}"
FIRST_DRAW_DATE = date(2002, 12, 7)  # 1회차 추첨일 (토요일)
DEFAULT_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "draws.json"
)


@dataclass(frozen=True)
class Draw:
    """한 회차의 당첨 결과."""

    no: int
    numbers: tuple[int, ...]  # 당첨번호 6개 (오름차순)
    bonus: int
    draw_date: str = ""

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

    @property
    def all_numbers(self) -> tuple[int, ...]:
        """당첨번호 6개 + 보너스."""
        return (*self.numbers, self.bonus)

    def to_dict(self) -> dict:
        return {
            "no": self.no,
            "numbers": list(self.numbers),
            "bonus": self.bonus,
            "draw_date": self.draw_date,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Draw":
        return cls(
            no=int(raw["no"]),
            numbers=tuple(sorted(int(n) for n in raw["numbers"])),
            bonus=int(raw["bonus"]),
            draw_date=str(raw.get("draw_date", "")),
        )


def estimate_latest_draw_no(today: date | None = None) -> int:
    """오늘 날짜 기준으로 존재할 법한 최신 회차 번호를 추정한다."""
    today = today or date.today()
    weeks = (today - FIRST_DRAW_DATE).days // 7
    return max(1, weeks + 1)


# ---------------------------------------------------------------- 원격 수집

def fetch_draw(no: int, timeout: float = 10.0) -> Draw | None:
    """동행복권 공개 API에서 한 회차를 가져온다. 아직 추첨 전이면 None."""
    req = urllib.request.Request(
        API_URL.format(no=no), headers={"User-Agent": "lottoracle/0.1"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("returnValue") != "success":
        return None
    return Draw(
        no=int(payload["drwNo"]),
        numbers=tuple(sorted(int(payload[f"drwtNo{i}"]) for i in range(1, 7))),
        bonus=int(payload["bnusNo"]),
        draw_date=str(payload.get("drwNoDate", "")),
    )


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


def latest(draws: Sequence[Draw]) -> Draw | None:
    return max(draws, key=lambda d: d.no) if draws else None


def next_draw_date(today: date | None = None) -> date:
    """다음 추첨일(토요일)을 돌려준다."""
    today = today or date.today()
    return today + timedelta(days=(5 - today.weekday()) % 7 or 7)
