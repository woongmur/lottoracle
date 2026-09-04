"""민간속설 모듈 — 통계가 아니라 '기분'을 다루는 부분.

여기 있는 규칙은 어느 것도 당첨 확률을 바꾸지 못한다. 확률은 그대로 1/8,145,060이다.
다만 로또는 어차피 취향 싸움이라, 한국에서 오래 회자된 속설들을 가중치와 태그로
정직하게 구현해 둔다. 켜고 끄는 건 사용자 몫.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

from .data import Draw
from .metrics import NUMBER_POOL, TWIN_NUMBERS
from .seollal import SEOLLAL

# ---------------------------------------------------------------- 실제 볼 색상
# 동행복권 추첨 볼의 색: 노랑 1~10, 파랑 11~20, 빨강 21~30, 회색 31~40, 초록 41~45
COLOR_ZONES: tuple[tuple[str, int, int], ...] = (
    ("노랑", 1, 10),
    ("파랑", 11, 20),
    ("빨강", 21, 30),
    ("회색", 31, 40),
    ("초록", 41, 45),
)


def ball_color(n: int) -> str:
    for name, lo, hi in COLOR_ZONES:
        if lo <= n <= hi:
            return name
    raise ValueError(f"1~45 범위를 벗어난 번호: {n}")


def color_counts(nums: Sequence[int]) -> dict[str, int]:
    counts = {name: 0 for name, _, _ in COLOR_ZONES}
    for n in nums:
        counts[ball_color(n)] += 1
    return counts


def color_signature(nums: Sequence[int]) -> str:
    counts = color_counts(nums)
    return " ".join(f"{k}{v}" for k, v in counts.items() if v)


# ------------------------------------------------------- 로또 용지 배열(7열 격자)
SLIP_COLUMNS = 7


def slip_position(n: int) -> tuple[int, int]:
    """마킹 용지에서의 (행, 열). 1~45를 7열 격자로 놓는다."""
    return ((n - 1) // SLIP_COLUMNS, (n - 1) % SLIP_COLUMNS)


def is_slip_line(nums: Sequence[int]) -> bool:
    """용지에서 한 줄로 죽 그은 모양(같은 행/열/대각선)인지. 속설상 '피해야 할 모양'."""
    pos = [slip_position(n) for n in nums]
    rows = {r for r, _ in pos}
    cols = {c for _, c in pos}
    if len(rows) == 1 or len(cols) == 1:
        return True
    diag_down = {r - c for r, c in pos}
    diag_up = {r + c for r, c in pos}
    return len(diag_down) == 1 or len(diag_up) == 1


def slip_cluster_penalty(nums: Sequence[int]) -> int:
    """용지에서 붙어 있는(상하좌우 인접) 칸 쌍의 개수. 많으면 '뭉친 모양'."""
    pos = [slip_position(n) for n in nums]
    touching = 0
    for i, (r1, c1) in enumerate(pos):
        for r2, c2 in pos[i + 1:]:
            if abs(r1 - r2) + abs(c1 - c2) == 1:
                touching += 1
    return touching


# ------------------------------------------------------------------ 숫자 성질들
def primes() -> tuple[int, ...]:
    out = []
    for n in NUMBER_POOL:
        if n > 1 and all(n % d for d in range(2, int(n**0.5) + 1)):
            out.append(n)
    return tuple(out)


PRIME_NUMBERS = primes()
FIBONACCI_NUMBERS = (1, 2, 3, 5, 8, 13, 21, 34)
TRIANGULAR_NUMBERS = (1, 3, 6, 10, 15, 21, 28, 36, 45)
PERFECT_SQUARES = (1, 4, 9, 16, 25, 36)


def same_ending_groups(nums: Sequence[int]) -> dict[int, list[int]]:
    """동형수(끝수가 같은 번호) 묶음. 예: 3·13·23."""
    groups: dict[int, list[int]] = {}
    for n in sorted(nums):
        groups.setdefault(n % 10, []).append(n)
    return {d: g for d, g in groups.items() if len(g) > 1}


def neighbor_numbers(previous: Draw | None) -> set[int]:
    """이웃수: 직전 회차 당첨번호 ±1. '파동이 옆으로 번진다'는 속설."""
    if previous is None:
        return set()
    out: set[int] = set()
    for n in previous.all_numbers:
        out.update(x for x in (n - 1, n + 1) if 1 <= x <= 45)
    return out - set(previous.numbers)


# -------------------------------------------------------------------- 꿈해몽수
# 한국에서 흔히 회자되는 '꿈 → 번호' 대응. 근거는 없고, 재미로 쓰는 것이다.
DREAM_NUMBERS: dict[str, tuple[int, ...]] = {
    "돼지": (3, 7, 13, 27, 33, 37),
    "용": (1, 8, 9, 18, 28, 38),
    "조상": (4, 14, 24, 34, 44),
    "똥": (7, 17, 21, 27, 37, 43),
    "불": (5, 9, 19, 25, 29, 39),
    "물": (2, 6, 12, 22, 26, 42),
    "바다": (2, 12, 22, 32, 42, 45),
    "뱀": (6, 16, 23, 26, 36, 41),
    "호랑이": (3, 10, 13, 23, 30, 43),
    "아기": (1, 11, 15, 21, 31, 41),
    "돈": (7, 8, 17, 18, 27, 28),
    "무지개": (5, 7, 15, 25, 35, 45),
    "장례": (4, 9, 14, 19, 24, 40),
    "이빨": (2, 11, 20, 22, 29, 32),
    "산": (5, 10, 15, 20, 35, 40),
    "비": (6, 16, 26, 36, 44, 45),
}


def dream_numbers(keyword: str) -> tuple[int, ...]:
    """꿈 키워드에서 번호 뭉치를 찾는다. 부분 일치 허용('돼지꿈' -> '돼지')."""
    if not keyword:
        return ()
    text = keyword.strip()
    hits: list[int] = []
    for key, nums in DREAM_NUMBERS.items():
        if key in text:
            hits.extend(nums)
    return tuple(sorted(set(hits)))


# ------------------------------------------------------------- 생일수 / 띠수
ZODIAC_NUMBERS: dict[str, tuple[int, ...]] = {
    "쥐": (1, 13, 25, 37),
    "소": (2, 14, 26, 38),
    "호랑이": (3, 15, 27, 39),
    "토끼": (4, 16, 28, 40),
    "용": (5, 17, 29, 41),
    "뱀": (6, 18, 30, 42),
    "말": (7, 19, 31, 43),
    "양": (8, 20, 32, 44),
    "원숭이": (9, 21, 33, 45),
    "닭": (10, 22, 34),
    "개": (11, 23, 35),
    "돼지": (12, 24, 36),
}
ZODIAC_ORDER = ("원숭이", "닭", "개", "돼지", "쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양")


def zodiac_of_year(year: int) -> str:
    return ZODIAC_ORDER[year % 12]


def zodiac_of_birth(birth_date: str, lunar: bool = False) -> str:
    """생년월일에서 띠. 띠는 음력 해를 따른다.

    음력으로 적었으면 연도가 곧 음력 해라 그대로 쓰면 된다.
    양력이면 그해 설날보다 앞인지 봐야 한다 — 앞이면 아직 지난 해의 띠다.
    예: 1990-01-15(양력)은 1990년 설날(1/27)보다 앞이라 말띠가 아니라 뱀띠.

    설날을 모르는 연도(표 밖)는 연도만으로 정한다. 없는 것보다는 낫다.
    """
    if not birth_date or len(birth_date) < 4:
        return ""
    year = int(birth_date[:4])
    if not lunar and len(birth_date) >= 10:
        seollal = SEOLLAL.get(year)
        if seollal and birth_date[5:10] < seollal:
            year -= 1
    return zodiac_of_year(year)


def zodiac_numbers(name_or_year: str) -> tuple[int, ...]:
    if not name_or_year:
        return ()
    token = name_or_year.strip().replace("띠", "")
    if token.isdigit():
        token = zodiac_of_year(int(token))
    return ZODIAC_NUMBERS.get(token, ())


def birthday_numbers(text: str) -> tuple[int, ...]:
    """생일에서 뽑아내는 번호: 월, 일, 일의 자릿수 합, 연도 뒷 두 자리."""
    if not text:
        return ()
    digits = [int(x) for x in re.findall(r"\d+", text)]
    if not digits:
        return ()
    out: set[int] = set()
    try:
        parts = re.findall(r"\d+", text)
        if len(parts) >= 3:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            date(y if y > 1000 else 2000 + y, m, d)  # 유효성만 확인
            out.update(x for x in (m, d, (d // 10) + (d % 10), y % 100) if 1 <= x <= 45)
    except ValueError:
        pass
    out.update(x for x in digits if 1 <= x <= 45)
    return tuple(sorted(out))


# ------------------------------------------------------------------- 설정/적용
@dataclass
class Folklore:
    """속설 옵션 묶음. 전부 꺼도 코드는 정상 동작한다."""

    enabled: bool = True
    lucky: tuple[int, ...] = ()          # 행운수 — 가중치 상승
    avoid: tuple[int, ...] = ()          # 기피수 — 아예 제외 (예: 4 = 죽을 사)
    dream: str = ""                      # 꿈 키워드
    birthday: str = ""                   # 생일 (YYYY-MM-DD)
    zodiac: str = ""                     # 띠 또는 태어난 해
    lucky_weight: float = 1.6
    dream_weight: float = 1.4
    neighbor_weight: float = 1.25        # 이웃수(직전 ±1)
    twin_weight: float = 1.15            # 쌍둥이수 11·22·33·44
    color_balance: bool = True           # 5색이 한쪽으로 쏠리지 않게
    max_per_color: int = 3
    min_colors: int = 3
    avoid_slip_lines: bool = True        # 용지 직선/대각선 모양 회피
    max_slip_cluster: int = 3            # 용지에서 붙어 있는 칸 쌍의 상한
    tags: list[str] = field(default_factory=list)

    def wish_numbers(self) -> tuple[int, ...]:
        """행운수 + 꿈수 + 생일수 + 띠수를 합친 '내 편' 번호."""
        merged = set(self.lucky)
        merged.update(dream_numbers(self.dream))
        merged.update(birthday_numbers(self.birthday))
        merged.update(zodiac_numbers(self.zodiac))
        return tuple(sorted(n for n in merged if n not in set(self.avoid)))

    def excluded(self) -> set[int]:
        return {n for n in self.avoid if 1 <= n <= 45}

    def describe(self) -> list[str]:
        out: list[str] = []
        if self.lucky:
            out.append(f"행운수 {list(self.lucky)}")
        if self.avoid:
            out.append(f"기피수 {list(self.avoid)} 제외")
        if self.dream:
            got = dream_numbers(self.dream)
            out.append(f"꿈({self.dream}) → {list(got) or '해당 없음'}")
        if self.birthday:
            out.append(f"생일수 {list(birthday_numbers(self.birthday))}")
        if self.zodiac:
            out.append(f"띠수({self.zodiac}) {list(zodiac_numbers(self.zodiac))}")
        if self.color_balance:
            out.append(f"5색 균형(한 색 최대 {self.max_per_color}개)")
        if self.avoid_slip_lines:
            out.append("용지 직선·대각선 모양 회피")
        return out


def multipliers(fl: Folklore | None, previous: Draw | None) -> dict[int, float]:
    """번호별 속설 가중 배수. 속설을 끄면 전부 1.0."""
    base = {n: 1.0 for n in NUMBER_POOL}
    if fl is None or not fl.enabled:
        return base

    for n in fl.wish_numbers():
        base[n] *= fl.lucky_weight if n in fl.lucky else fl.dream_weight
    for n in neighbor_numbers(previous):
        base[n] *= fl.neighbor_weight
    for n in TWIN_NUMBERS:
        base[n] *= fl.twin_weight
    for n in fl.excluded():
        base[n] = 0.0
    return base


def accepts(fl: Folklore | None, nums: Sequence[int], lenient: bool = False) -> bool:
    """속설 기준의 모양 검사. lenient=True면 완화 단계에서 통과시킨다."""
    if fl is None or not fl.enabled or lenient:
        return True
    if fl.avoid_slip_lines and is_slip_line(nums):
        return False
    if slip_cluster_penalty(nums) > fl.max_slip_cluster:
        return False
    if fl.color_balance:
        counts = color_counts(nums)
        if max(counts.values()) > fl.max_per_color:
            return False
        if sum(1 for v in counts.values() if v) < fl.min_colors:
            return False
    return True


def luck_tags(
    fl: Folklore | None, nums: Sequence[int], previous: Draw | None
) -> list[str]:
    """조합에 걸린 속설을 사람이 읽을 문장으로."""
    tags: list[str] = []
    wish = set(fl.wish_numbers()) if fl and fl.enabled else set()
    hit_wish = sorted(set(nums) & wish)
    if hit_wish:
        tags.append(f"행운·꿈수 적중 {hit_wish}")

    hit_twin = sorted(set(nums) & set(TWIN_NUMBERS))
    if hit_twin:
        tags.append(f"쌍둥이수 {hit_twin}")

    hit_neighbor = sorted(set(nums) & neighbor_numbers(previous))
    if hit_neighbor:
        tags.append(f"이웃수(직전 ±1) {hit_neighbor}")

    groups = same_ending_groups(nums)
    if groups:
        tags.append(
            "동형수 " + ", ".join("·".join(str(x) for x in g) for g in groups.values())
        )

    hit_prime = sorted(set(nums) & set(PRIME_NUMBERS))
    if len(hit_prime) >= 3:
        tags.append(f"소수 {len(hit_prime)}개")
    hit_fib = sorted(set(nums) & set(FIBONACCI_NUMBERS))
    if len(hit_fib) >= 2:
        tags.append(f"피보나치수 {hit_fib}")

    tags.append(f"볼 색상 {color_signature(nums)}")
    return tags


def luck_score(fl: Folklore | None, nums: Sequence[int], previous: Draw | None) -> int:
    """0~100의 '기분 점수'. 확률과는 아무 상관이 없다 — 정말로."""
    score = 50
    wish = set(fl.wish_numbers()) if fl and fl.enabled else set()
    score += 8 * len(set(nums) & wish)
    score += 5 * len(set(nums) & set(TWIN_NUMBERS))
    score += 4 * len(set(nums) & neighbor_numbers(previous))
    counts = color_counts(nums)
    score += 6 * sum(1 for v in counts.values() if v)   # 색이 고루 퍼질수록 가점
    score -= 7 * max(0, max(counts.values()) - 3)
    score -= 5 * max(0, slip_cluster_penalty(nums) - 2)
    if is_slip_line(nums):
        score -= 20
    return max(0, min(100, score))
