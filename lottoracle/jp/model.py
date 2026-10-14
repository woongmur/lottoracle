"""일본 로또 실데이터로 필터를 보정하고 조합의 '전형성'을 점수화한다.

한국판 model.py 와 같은 방식이다. 다른 점은 평활(라플라스)에 쓰는 '나올 수 있는 값의
개수'를 게임마다 계산한다는 것 — 한국판은 6/45 에 맞춘 상수(합계 60칸, AC 11칸 …)다.
전형성은 확률과 무관하다. 모든 조합은 똑같은 확률로 나온다.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from ..model import _quantile
from .data import JpDraw
from .filters import Ruleset, default_rules
from .games import Game
from .metrics import max_ac, max_sum, profile

# 정렬한 구간 분포(예: 0-1-1-2-2)가 나올 수 있는 가짓수. 모든 조합을 세어 얻은 값.
ZONE_PATTERNS = {"loto6": 10, "loto7": 11, "miniloto": 6}


def supports(game: Game) -> dict[str, int]:
    """지표마다 나올 수 있는 값(또는 구간)의 개수 — 평활 분모에 더한다."""
    k = game.pick
    return {
        "total": max_sum(game) // 5 + 1,      # 5단위 구간
        "odd": k + 1,
        "low": k + 1,
        "ac": max_ac(game) + 1,
        "end_sum": (9 * k) // 3 + 1,          # 3단위 구간
        "consecutive": k,                     # 0 ~ k-1
        "zone": ZONE_PATTERNS[game.key],
        "carryover": k + 1,
        "spread": (game.pool - 1) // 4 + 1,   # 4단위 구간
        "position": game.pool,
    }


@dataclass
class Empirical:
    game: Game
    count: int = 0
    total: Counter = field(default_factory=Counter)
    odd: Counter = field(default_factory=Counter)
    low: Counter = field(default_factory=Counter)
    ac: Counter = field(default_factory=Counter)
    end_sum: Counter = field(default_factory=Counter)
    consecutive: Counter = field(default_factory=Counter)
    zone_pattern: Counter = field(default_factory=Counter)
    carryover: Counter = field(default_factory=Counter)
    spread: Counter = field(default_factory=Counter)
    position: tuple[Counter, ...] = ()
    sums_sorted: list[int] = field(default_factory=list)
    end_sums_sorted: list[int] = field(default_factory=list)
    spreads_sorted: list[int] = field(default_factory=list)

    def _p(self, counter: Counter, key, name: str) -> float:
        return (counter.get(key, 0) + 1.0) / (self.count + supports(self.game)[name])

    def p_total(self, v: int) -> float:
        return self._p(self.total, v // 5, "total")

    def p_odd(self, v: int) -> float:
        return self._p(self.odd, v, "odd")

    def p_low(self, v: int) -> float:
        return self._p(self.low, v, "low")

    def p_ac(self, v: int) -> float:
        return self._p(self.ac, v, "ac")

    def p_end_sum(self, v: int) -> float:
        return self._p(self.end_sum, v // 3, "end_sum")

    def p_consecutive(self, v: int) -> float:
        return self._p(self.consecutive, v, "consecutive")

    def p_zone(self, zones: Sequence[int]) -> float:
        return self._p(self.zone_pattern, tuple(sorted(zones)), "zone")

    def p_carryover(self, v: int) -> float:
        return self._p(self.carryover, v, "carryover")

    def p_spread(self, v: int) -> float:
        return self._p(self.spread, v // 4, "spread")

    def p_position(self, idx: int, number: int) -> float:
        return self._p(self.position[idx], number, "position")


def fit(game: Game, draws: Sequence[JpDraw]) -> Empirical:
    emp = Empirical(game=game, position=tuple(Counter() for _ in range(game.pick)))
    ordered = sorted(draws, key=lambda d: d.no)
    emp.count = len(ordered)
    sums, ends, spreads = [], [], []
    for idx, draw in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        p = profile(game, draw.numbers, prev)
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


def calibrate(game: Game, draws: Sequence[JpDraw], coverage: float = 0.90,
              base: Ruleset | None = None) -> Ruleset:
    """실데이터 백분위로 규칙 범위를 다시 맞춘다. 한국판 calibrate 와 같은 방식."""
    base = base or default_rules(game)
    if not draws:
        return base
    emp = fit(game, draws)
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

    odd_lo, odd_hi = trimmed(emp.odd, *base.odd_range)
    low_lo, low_hi = trimmed(emp.low, *base.low_range)
    ac_lo, _ = trimmed(emp.ac, base.ac_min, base.ac_min)
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


@dataclass(frozen=True)
class ScoreWeights:
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


def typicality(nums: Sequence[int], emp: Empirical, previous: Sequence[int] = (),
               weights: ScoreWeights = ScoreWeights()) -> float:
    """가중 로그가능도. 높을수록 '흔한 모양'. 데이터가 없으면 0."""
    if emp.count == 0:
        return 0.0
    p = profile(emp.game, nums, previous)
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
    ) / emp.game.pick
    return score


def typicality_percentile(score: float, reference: Sequence[float]) -> float:
    if not reference:
        return 50.0
    below = sum(1 for r in reference if r <= score)
    return 100.0 * below / len(reference)


def reference_scores(draws: Sequence[JpDraw], emp: Empirical,
                     weights: ScoreWeights = ScoreWeights()) -> list[float]:
    ordered = sorted(draws, key=lambda d: d.no)
    out = []
    for idx, d in enumerate(ordered):
        prev = ordered[idx - 1].numbers if idx else ()
        out.append(typicality(d.numbers, emp, prev, weights))
    return sorted(out)
