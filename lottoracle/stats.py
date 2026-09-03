"""과거 회차에서 번호별 통계를 뽑아낸다."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from .data import Draw
from .metrics import NUMBER_POOL, profile


@dataclass
class NumberStats:
    """번호 1~45에 대한 출현 통계."""

    draws_used: int = 0
    frequency: Counter = field(default_factory=Counter)      # 전체 출현 횟수
    recent: Counter = field(default_factory=Counter)         # 최근 N회 출현 횟수
    recent_window: int = 0
    gap: dict[int, int] = field(default_factory=dict)        # 미출현 회차 수
    pairs: Counter = field(default_factory=Counter)          # 동반 출현(궁합수)
    bonus_frequency: Counter = field(default_factory=Counter)

    @property
    def mean_frequency(self) -> float:
        return (self.draws_used * 6) / 45 if self.draws_used else 0.0

    def hot(self, n: int = 10) -> list[tuple[int, int]]:
        return self.recent.most_common(n)

    def cold(self, n: int = 10) -> list[tuple[int, int]]:
        return sorted(self.gap.items(), key=lambda kv: -kv[1])[:n]

    def companions(self, number: int, n: int = 6) -> list[tuple[int, int]]:
        """해당 번호와 같이 나온 적 많은 번호(궁합수)."""
        scored = [
            (other, self.pairs[frozenset((number, other))])
            for other in NUMBER_POOL
            if other != number
        ]
        return sorted(scored, key=lambda kv: -kv[1])[:n]


def build(draws: Sequence[Draw], recent_window: int = 30) -> NumberStats:
    st = NumberStats(draws_used=len(draws), recent_window=recent_window)
    if not draws:
        st.gap = {n: 0 for n in NUMBER_POOL}
        return st

    ordered = sorted(draws, key=lambda d: d.no)
    for draw in ordered:
        st.frequency.update(draw.numbers)
        st.bonus_frequency[draw.bonus] += 1
        for pair in combinations(sorted(draw.numbers), 2):
            st.pairs[frozenset(pair)] += 1

    for draw in ordered[-recent_window:]:
        st.recent.update(draw.numbers)

    last_seen = {n: -1 for n in NUMBER_POOL}
    for idx, draw in enumerate(ordered):
        for n in draw.numbers:
            last_seen[n] = idx
    total = len(ordered)
    st.gap = {n: (total - 1 - idx if idx >= 0 else total) for n, idx in last_seen.items()}
    return st


# ----------------------------------------------------------- 회차 전체의 평균치

@dataclass
class DrawProfileStats:
    """당첨조합들이 실제로 어떤 모양이었는지 요약 (= '대한민국 로또 평균치')."""

    count: int
    mean_sum: float
    sum_range_80: tuple[int, int]
    odd_distribution: Counter
    low_distribution: Counter
    ac_distribution: Counter
    end_sum_mean: float
    consecutive_ratio: float
    carryover_distribution: Counter

    def render(self) -> str:
        def dist(counter: Counter) -> str:
            total = sum(counter.values()) or 1
            return "  ".join(
                f"{k}:{v}회({v / total:.0%})" for k, v in sorted(counter.items())
            )

        return "\n".join(
            [
                f"분석 회차 수      : {self.count}",
                f"당첨번호 합 평균  : {self.mean_sum:.1f} (이론 기대값 138)",
                f"합계 80% 구간     : {self.sum_range_80[0]} ~ {self.sum_range_80[1]}",
                f"홀수 개수 분포    : {dist(self.odd_distribution)}",
                f"저구간(1~22) 분포 : {dist(self.low_distribution)}",
                f"AC값 분포         : {dist(self.ac_distribution)}",
                f"끝수합 평균       : {self.end_sum_mean:.1f}",
                f"연속수 포함 비율  : {self.consecutive_ratio:.1%}",
                f"이월수 분포       : {dist(self.carryover_distribution)}",
            ]
        )


def profile_stats(draws: Sequence[Draw]) -> DrawProfileStats:
    ordered = sorted(draws, key=lambda d: d.no)
    if not ordered:
        raise ValueError("분석할 회차 데이터가 없습니다.")

    sums, ends = [], []
    odd_d, low_d, ac_d, carry_d = Counter(), Counter(), Counter(), Counter()
    with_consecutive = 0

    for idx, draw in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        p = profile(draw.numbers, prev)
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
