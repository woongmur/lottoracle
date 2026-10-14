"""일본 로또 조합 하나를 숫자로 뜯어보는 지표들.

합계·AC값·연속수·끝수 같은 계산은 번호 범위와 무관해서 한국 쪽 함수를 그대로 쓴다.
범위가 걸린 것(저구간 경계, 10단위 구간, 쌍둥이수)만 게임 규칙표에서 끌어낸다.
JS 판은 web/src/jp/metrics.js (골든 데이터로 대조).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..metrics import (
    ac_value, carryover_count, consecutive_pairs, ending_sum, max_consecutive_run,
    max_same_ending, multiples_of_three, odd_count, spread, total_sum,
)
from .games import Game

# 10단위 구간 이름. 미니로또(31까지)는 앞 넷만 쓴다.
ZONE_LABELS = ("한 자리", "10번대", "20번대", "30번대", "40번대")


def number_pool(game: Game) -> tuple[int, ...]:
    return tuple(range(1, game.pool + 1))


def low_max(game: Game) -> int:
    """저구간의 끝. 한국 로또가 45 를 1~22 / 23~45 로 가르듯 절반에서 자른다."""
    return game.pool // 2


def zone_bounds(game: Game) -> tuple[tuple[int, int], ...]:
    """10단위 구간: 1~9, 10~19, … 마지막 구간은 번호 끝에서 자른다."""
    out = [(1, 9)]
    lo = 10
    while lo <= game.pool:
        out.append((lo, min(lo + 9, game.pool)))
        lo += 10
    return tuple(out)


def twin_numbers(game: Game) -> tuple[int, ...]:
    """쌍둥이수 11·22·33 … 번호 범위 안의 것만."""
    return tuple(n for n in range(11, game.pool + 1, 11))


def expected_sum(game: Game) -> int:
    """본숫자 합의 이론 기대값 = 개수 × (범위+1) / 2. 세 게임 모두 정수로 떨어진다."""
    return game.pick * (game.pool + 1) // 2


def max_sum(game: Game) -> int:
    return sum(range(game.pool - game.pick + 1, game.pool + 1))


def max_ac(game: Game) -> int:
    """서로 다른 차이는 C(pick,2) 개를 넘을 수 없고, 1~(pool-1) 밖으로도 못 나간다."""
    pairs = game.pick * (game.pick - 1) // 2
    return min(pairs, game.pool - 1) - (game.pick - 1)


def low_count(game: Game, nums: Sequence[int]) -> int:
    return sum(1 for n in nums if n <= low_max(game))


def zone_counts(game: Game, nums: Sequence[int]) -> tuple[int, ...]:
    return tuple(sum(1 for n in nums if lo <= n <= hi) for lo, hi in zone_bounds(game))


@dataclass(frozen=True)
class Profile:
    """조합 하나의 지표 묶음. 필드는 한국판 Profile 과 같다."""

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


def profile(game: Game, nums: Sequence[int], previous: Sequence[int] = ()) -> Profile:
    ordered = tuple(sorted(nums))
    odd = odd_count(ordered)
    low = low_count(game, ordered)
    return Profile(
        numbers=ordered,
        total=total_sum(ordered),
        odd=odd,
        even=len(ordered) - odd,
        low=low,
        high=len(ordered) - low,
        zones=zone_counts(game, ordered),
        ac=ac_value(ordered),
        max_run=max_consecutive_run(ordered),
        consecutive=consecutive_pairs(ordered),
        end_sum=ending_sum(ordered),
        same_ending=max_same_ending(ordered),
        mult3=multiples_of_three(ordered),
        spread=spread(ordered),
        carryover=carryover_count(ordered, previous),
    )
