"""일본 로또 과거 회차에서 번호별 통계를 뽑아낸다. 한국판 stats.py 를 게임 규칙표로 옮긴 것.

다른 점: 보너스가 여러 개일 수 있다(로또7 은 둘). 보너스 빈도는 모두 센다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from .data import JpDraw
from .games import Game
from .metrics import number_pool, profile


@dataclass
class NumberStats:
    game: Game
    draws_used: int = 0
    frequency: Counter = field(default_factory=Counter)
    recent: Counter = field(default_factory=Counter)
    recent_window: int = 0
    gap: dict[int, int] = field(default_factory=dict)
    pairs: Counter = field(default_factory=Counter)
    bonus_frequency: Counter = field(default_factory=Counter)

    @property
    def mean_frequency(self) -> float:
        return (self.draws_used * self.game.pick) / self.game.pool if self.draws_used else 0.0

    def hot(self, n: int = 10) -> list[tuple[int, int]]:
        return self.recent.most_common(n)

    def cold(self, n: int = 10) -> list[tuple[int, int]]:
        return sorted(self.gap.items(), key=lambda kv: -kv[1])[:n]

    def companions(self, number: int, n: int = 6) -> list[tuple[int, int]]:
        scored = [(o, self.pairs[frozenset((number, o))]) for o in number_pool(self.game) if o != number]
        return sorted(scored, key=lambda kv: -kv[1])[:n]


def build(game: Game, draws: Sequence[JpDraw], recent_window: int = 30) -> NumberStats:
    st = NumberStats(game=game, draws_used=len(draws), recent_window=recent_window)
    pool = number_pool(game)
    if not draws:
        st.gap = {n: 0 for n in pool}
        return st

    ordered = sorted(draws, key=lambda d: d.no)
    for draw in ordered:
        st.frequency.update(draw.numbers)
        st.bonus_frequency.update(draw.bonus)
        for pair in combinations(sorted(draw.numbers), 2):
            st.pairs[frozenset(pair)] += 1

    for draw in ordered[-recent_window:]:
        st.recent.update(draw.numbers)

    last_seen = {n: -1 for n in pool}
    for idx, draw in enumerate(ordered):
        for n in draw.numbers:
            last_seen[n] = idx
    total = len(ordered)
    st.gap = {n: (total - 1 - idx if idx >= 0 else total) for n, idx in last_seen.items()}
    return st


@dataclass
class DrawProfileStats:
    count: int
    mean_sum: float
    sum_range_80: tuple[int, int]
    odd_distribution: Counter
    low_distribution: Counter
    ac_distribution: Counter
    end_sum_mean: float
    consecutive_ratio: float
    carryover_distribution: Counter


def profile_stats(game: Game, draws: Sequence[JpDraw]) -> DrawProfileStats:
    ordered = sorted(draws, key=lambda d: d.no)
    if not ordered:
        raise ValueError("분석할 회차 데이터가 없습니다.")

    sums, ends = [], []
    odd_d, low_d, ac_d, carry_d = Counter(), Counter(), Counter(), Counter()
    with_consecutive = 0
    for idx, draw in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        p = profile(game, draw.numbers, prev)
        sums.append(p.total)
        ends.append(p.end_sum)
        odd_d[p.odd] += 1
        low_d[p.low] += 1
        ac_d[p.ac] += 1
        if idx:
            carry_d[p.carryover] += 1
        if p.consecutive:
            with_consecutive += 1

    ordered_sums = sorted(sums)
    lo = ordered_sums[int(len(ordered_sums) * 0.10)]
    hi = ordered_sums[min(len(ordered_sums) - 1, int(len(ordered_sums) * 0.90))]
    return DrawProfileStats(
        count=len(ordered),
        mean_sum=sum(sums) / len(sums),
        sum_range_80=(lo, hi),
        odd_distribution=odd_d,
        low_distribution=low_d,
        ac_distribution=ac_d,
        end_sum_mean=sum(ends) / len(ends),
        consecutive_ratio=with_consecutive / len(ordered),
        carryover_distribution=carry_d,
    )
