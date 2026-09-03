"""조합 하나를 숫자로 뜯어보는 지표들 (대한민국 로또 6/45 기준)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Sequence

NUMBER_POOL = tuple(range(1, 46))
PICK = 6
LOW_MAX = 22  # 저구간 1~22 / 고구간 23~45
# 5개 구간: 1~9, 10~19, 20~29, 30~39, 40~45
ZONE_BOUNDS = ((1, 9), (10, 19), (20, 29), (30, 39), (40, 45))
TWIN_NUMBERS = (11, 22, 33, 44)  # 속칭 '쌍둥이수'


def total_sum(nums: Sequence[int]) -> int:
    return sum(nums)


def odd_count(nums: Sequence[int]) -> int:
    return sum(1 for n in nums if n % 2)


def low_count(nums: Sequence[int]) -> int:
    return sum(1 for n in nums if n <= LOW_MAX)


def zone_counts(nums: Sequence[int]) -> tuple[int, ...]:
    return tuple(
        sum(1 for n in nums if lo <= n <= hi) for lo, hi in ZONE_BOUNDS
    )


def ac_value(nums: Sequence[int]) -> int:
    """AC값 = (서로 다른 차이의 개수) - 5. 6개 조합에서 0~10, 당첨조합은 7~10에 몰린다."""
    diffs = {abs(a - b) for a, b in combinations(sorted(nums), 2)}
    return len(diffs) - (len(nums) - 1)


def max_consecutive_run(nums: Sequence[int]) -> int:
    """가장 긴 연속수 길이. 예: (3,4,5,20,31,44) -> 3."""
    ordered = sorted(nums)
    best = run = 1
    for prev, cur in zip(ordered, ordered[1:]):
        run = run + 1 if cur - prev == 1 else 1
        best = max(best, run)
    return best


def consecutive_pairs(nums: Sequence[int]) -> int:
    ordered = sorted(nums)
    return sum(1 for a, b in zip(ordered, ordered[1:]) if b - a == 1)


def ending_digits(nums: Sequence[int]) -> tuple[int, ...]:
    return tuple(n % 10 for n in nums)


def ending_sum(nums: Sequence[int]) -> int:
    """끝수합. 당첨조합은 대체로 15~35."""
    return sum(ending_digits(nums))


def max_same_ending(nums: Sequence[int]) -> int:
    digits = ending_digits(nums)
    return max(digits.count(d) for d in set(digits))


def multiples_of_three(nums: Sequence[int]) -> int:
    return sum(1 for n in nums if n % 3 == 0)


def carryover_count(nums: Sequence[int], previous: Sequence[int]) -> int:
    """이월수: 직전 회차 당첨번호와 겹치는 개수."""
    return len(set(nums) & set(previous))


def spread(nums: Sequence[int]) -> int:
    return max(nums) - min(nums)


@dataclass(frozen=True)
class Profile:
    """조합 하나의 지표 묶음."""

    numbers: tuple[int, ...]
    total: int
    odd: int
    even: int
    low: int
    high: int
    zones: tuple[int, ...]
    ac: int
    max_run: int
    consecutive: int
    end_sum: int
    same_ending: int
    mult3: int
    spread: int
    carryover: int

    def summary(self) -> str:
        return (
            f"합계 {self.total} · 홀짝 {self.odd}:{self.even} · 고저 {self.low}:{self.high} · "
            f"AC {self.ac} · 끝수합 {self.end_sum} · 연속 {self.consecutive} · "
            f"구간 {'-'.join(str(z) for z in self.zones)} · 이월 {self.carryover}"
        )


def profile(nums: Sequence[int], previous: Sequence[int] = ()) -> Profile:
    ordered = tuple(sorted(nums))
    zones = zone_counts(ordered)
    odd = odd_count(ordered)
    low = low_count(ordered)
    return Profile(
        numbers=ordered,
        total=total_sum(ordered),
        odd=odd,
        even=len(ordered) - odd,
        low=low,
        high=len(ordered) - low,
        zones=zones,
        ac=ac_value(ordered),
        max_run=max_consecutive_run(ordered),
        consecutive=consecutive_pairs(ordered),
        end_sum=ending_sum(ordered),
        same_ending=max_same_ending(ordered),
        mult3=multiples_of_three(ordered),
        spread=spread(ordered),
        carryover=carryover_count(ordered, previous),
    )
