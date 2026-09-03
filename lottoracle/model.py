"""실데이터로 필터를 보정하고, 조합의 '전형성'을 점수화한다.

전형성(typicality) = 이 조합의 모양이 과거 당첨조합들의 모양 분포에서 얼마나 흔한가.
확률과는 무관하다 — 모든 조합은 똑같이 1/8,145,060 이다. 다만 '흔한 모양'을 고르면
1·2·3·4·5·6 같은 조합이 배제되고, 당첨 시 인기 조합과 상금을 나눌 위험이 줄어든다.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from .data import Draw
from .filters import Ruleset
from .metrics import PICK, profile


def _quantile(sorted_values: Sequence[int], q: float) -> int:
    if not sorted_values:
        return 0
    idx = int(round((len(sorted_values) - 1) * q))
    return sorted_values[max(0, min(len(sorted_values) - 1, idx))]


@dataclass
class Empirical:
    """지표별 경험 분포. 각 Counter는 값 → 관측 횟수."""

    count: int = 0
    total: Counter = field(default_factory=Counter)
    odd: Counter = field(default_factory=Counter)
    low: Counter = field(default_factory=Counter)
    ac: Counter = field(default_factory=Counter)
    end_sum: Counter = field(default_factory=Counter)
    consecutive: Counter = field(default_factory=Counter)
    zone_pattern: Counter = field(default_factory=Counter)   # 정렬한 구간 분포, 예 (0,1,1,2,2)
    carryover: Counter = field(default_factory=Counter)
    spread: Counter = field(default_factory=Counter)
    position: tuple[Counter, ...] = field(default_factory=lambda: tuple(Counter() for _ in range(PICK)))
    sums_sorted: list[int] = field(default_factory=list)
    end_sums_sorted: list[int] = field(default_factory=list)
    spreads_sorted: list[int] = field(default_factory=list)

    # ---- 확률 조회 (라플라스 평활) ----
    def _p(self, counter: Counter, key, support: int) -> float:
        return (counter.get(key, 0) + 1.0) / (self.count + support)

    def p_total(self, v: int) -> float:
        return self._p(self.total, v // 5, 60)  # 5단위 구간

    def p_odd(self, v: int) -> float:
        return self._p(self.odd, v, 7)

    def p_low(self, v: int) -> float:
        return self._p(self.low, v, 7)

    def p_ac(self, v: int) -> float:
        return self._p(self.ac, v, 11)

    def p_end_sum(self, v: int) -> float:
        return self._p(self.end_sum, v // 3, 20)

    def p_consecutive(self, v: int) -> float:
        return self._p(self.consecutive, v, 6)

    def p_zone(self, zones: Sequence[int]) -> float:
        return self._p(self.zone_pattern, tuple(sorted(zones)), 40)

    def p_carryover(self, v: int) -> float:
        return self._p(self.carryover, v, 7)

    def p_spread(self, v: int) -> float:
        return self._p(self.spread, v // 4, 12)

    def p_position(self, idx: int, number: int) -> float:
        return self._p(self.position[idx], number, 45)


def fit(draws: Sequence[Draw]) -> Empirical:
    """과거 회차에서 지표 분포를 집계한다."""
    emp = Empirical()
    ordered = sorted(draws, key=lambda d: d.no)
    emp.count = len(ordered)
    sums, ends, spreads = [], [], []
    for idx, draw in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        p = profile(draw.numbers, prev)
        emp.total[p.total // 5] += 1
        emp.odd[p.odd] += 1
        emp.low[p.low] += 1
        emp.ac[p.ac] += 1
        emp.end_sum[p.end_sum // 3] += 1
        emp.consecutive[p.consecutive] += 1
        emp.zone_pattern[tuple(sorted(p.zones))] += 1
        if idx:
            emp.carryover[p.carryover] += 1
        emp.spread[p.spread // 4] += 1
        for pos, n in enumerate(p.numbers):
            emp.position[pos][n] += 1
        sums.append(p.total)
        ends.append(p.end_sum)
        spreads.append(p.spread)
    emp.sums_sorted = sorted(sums)
    emp.end_sums_sorted = sorted(ends)
    emp.spreads_sorted = sorted(spreads)
    return emp


def calibrate(draws: Sequence[Draw], coverage: float = 0.90, base: Ruleset | None = None) -> Ruleset:
    """실데이터 백분위로 Ruleset 범위를 자동 보정한다.

    coverage=0.90 이면 합계·끝수합·번호폭은 과거 당첨조합의 가운데 90%를 덮는 범위,
    홀짝·고저·AC·연속수는 누적 비율이 (1-coverage) 미만인 꼬리를 잘라낸 범위가 된다.
    """
    base = base or Ruleset()
    if not draws:
        return base
    emp = fit(draws)
    tail = (1.0 - coverage) / 2.0

    def trimmed(counter: Counter, lo_default: int, hi_default: int) -> tuple[int, int]:
        keys = sorted(counter)
        n = sum(counter.values())
        acc, lo = 0, keys[0]
        for k in keys:
            acc += counter[k]
            if acc / n > tail:
                lo = k
                break
        acc, hi = 0, keys[-1]
        for k in reversed(keys):
            acc += counter[k]
            if acc / n > tail:
                hi = k
                break
        return (min(lo, lo_default), max(hi, hi_default)) if lo > hi else (lo, hi)

    odd_lo, odd_hi = trimmed(emp.odd, 3, 3)
    low_lo, low_hi = trimmed(emp.low, 3, 3)
    ac_lo, _ = trimmed(emp.ac, 8, 8)
    _, cons_hi = trimmed(emp.consecutive, 0, 0)
    _, carry_hi = trimmed(emp.carryover, 0, 1)

    return Ruleset(
        sum_range=(_quantile(emp.sums_sorted, tail), _quantile(emp.sums_sorted, 1 - tail)),
        odd_range=(odd_lo, odd_hi),
        low_range=(low_lo, low_hi),
        ac_min=ac_lo,
        max_run=base.max_run,
        max_consecutive_pairs=max(1, cons_hi),
        max_per_zone=base.max_per_zone,
        min_zones=base.min_zones,
        end_sum_range=(_quantile(emp.end_sums_sorted, tail), _quantile(emp.end_sums_sorted, 1 - tail)),
        max_same_ending=base.max_same_ending,
        mult3_range=base.mult3_range,
        spread_min=_quantile(emp.spreads_sorted, tail),
        carryover_range=(0, max(2, carry_hi)),
        forbid_all_same_parity=base.forbid_all_same_parity,
    )


# ------------------------------------------------------------------ 점수화
@dataclass(frozen=True)
class ScoreWeights:
    """지표별 로그가능도 가중. 0이면 그 지표는 무시."""

    total: float = 1.0
    odd: float = 1.0
    low: float = 1.0
    ac: float = 1.0
    end_sum: float = 0.6
    consecutive: float = 0.6
    zone: float = 1.0
    carryover: float = 0.5
    spread: float = 0.5
    position: float = 0.8


def typicality(
    nums: Sequence[int],
    emp: Empirical,
    previous: Sequence[int] = (),
    weights: ScoreWeights = ScoreWeights(),
) -> float:
    """가중 로그가능도. 높을수록 '흔한 모양'. 데이터가 없으면 0."""
    if emp.count == 0:
        return 0.0
    p = profile(nums, previous)
    score = 0.0
    score += weights.total * math.log(emp.p_total(p.total))
    score += weights.odd * math.log(emp.p_odd(p.odd))
    score += weights.low * math.log(emp.p_low(p.low))
    score += weights.ac * math.log(emp.p_ac(p.ac))
    score += weights.end_sum * math.log(emp.p_end_sum(p.end_sum))
    score += weights.consecutive * math.log(emp.p_consecutive(p.consecutive))
    score += weights.zone * math.log(emp.p_zone(p.zones))
    if previous:
        score += weights.carryover * math.log(emp.p_carryover(p.carryover))
    score += weights.spread * math.log(emp.p_spread(p.spread))
    score += weights.position * sum(
        math.log(emp.p_position(i, n)) for i, n in enumerate(p.numbers)
    ) / PICK
    return score


def typicality_percentile(score: float, reference: Sequence[float]) -> float:
    """참조 점수 분포(과거 당첨조합들의 점수) 안에서의 백분위 (0~100)."""
    if not reference:
        return 50.0
    below = sum(1 for r in reference if r <= score)
    return 100.0 * below / len(reference)


def reference_scores(draws: Sequence[Draw], emp: Empirical, weights: ScoreWeights = ScoreWeights()) -> list[float]:
    """과거 당첨조합 각각의 전형성 점수 — 새 조합의 점수를 비교할 기준."""
    ordered = sorted(draws, key=lambda d: d.no)
    out = []
    for idx, d in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        out.append(typicality(d.numbers, emp, prev, weights))
    return sorted(out)
