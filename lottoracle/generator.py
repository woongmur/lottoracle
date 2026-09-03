"""가중 추첨 + 필터링으로 추천 조합을 만든다."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from .data import Draw
from dataclasses import replace as _replace

from .filters import Ruleset, check
from .folklore import Folklore, accepts, luck_score, luck_tags
from .folklore import multipliers as folklore_multipliers
from .metrics import NUMBER_POOL, PICK, TWIN_NUMBERS, Profile
from .stats import NumberStats
from .strategies import DEFAULT_STRATEGIES, Strategy

MIN_WEIGHT = 0.05  # 어떤 번호도 확률 0이 되지 않게 (모든 번호는 나올 수 있다)


@dataclass
class Line:
    """추천 한 줄."""

    strategy: Strategy
    numbers: tuple[int, ...]
    bonus: int
    profile: Profile
    relaxed_step: int = 0   # 규칙을 몇 단계 완화해서 찾았는지
    attempts: int = 0
    luck: int = 50          # 속설 기준 '기분 점수' (확률과 무관)
    omens: list[str] = field(default_factory=list)  # 걸린 속설 태그

    def render_numbers(self) -> str:
        body = ", ".join(f"{n:2d}" for n in self.numbers)
        return f"{body}  + 보너스 {self.bonus:2d}"


def _standardize(values: dict[int, float]) -> dict[int, float]:
    """번호별 값을 평균 0 / 표준편차 1로 정규화."""
    xs = list(values.values())
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    sd = math.sqrt(var)
    if sd < 1e-9:
        return {k: 0.0 for k in values}
    return {k: (v - mean) / sd for k, v in values.items()}


def base_weights(
    strategy: Strategy,
    stats: NumberStats,
    folklore: Folklore | None = None,
    previous: Draw | None = None,
) -> dict[int, float]:
    """전략 가중치 + 과거 통계 + 민간속설로 번호별 기본 가중치를 만든다."""
    if stats.draws_used:
        z_freq = _standardize({n: float(stats.frequency.get(n, 0)) for n in NUMBER_POOL})
        z_recent = _standardize({n: float(stats.recent.get(n, 0)) for n in NUMBER_POOL})
        z_gap = _standardize({n: float(stats.gap.get(n, 0)) for n in NUMBER_POOL})
    else:  # 데이터가 없으면 순수 균등 추첨 + 규칙 필터만 적용된다
        z_freq = z_recent = z_gap = {n: 0.0 for n in NUMBER_POOL}

    weights: dict[int, float] = {}
    for n in NUMBER_POOL:
        score = (
            strategy.w_frequency * z_freq[n]
            + strategy.w_recent * z_recent[n]
            + strategy.w_gap * z_gap[n]
            + (strategy.w_twin if n in TWIN_NUMBERS else 0.0)
        )
        weights[n] = max(MIN_WEIGHT, math.exp(score * 0.6))

    for n, factor in folklore_multipliers(folklore, previous).items():
        # 기피수(factor 0)는 0으로 두고, 나머지는 하한을 지킨다.
        weights[n] = 0.0 if factor == 0.0 else max(MIN_WEIGHT, weights[n] * factor)
    if not any(weights.values()):
        raise ValueError("기피수가 너무 많아 뽑을 번호가 남지 않았습니다.")
    return weights


def _companion_boost(
    candidate: int, chosen: Sequence[int], stats: NumberStats, strength: float
) -> float:
    """이미 뽑힌 번호들과의 궁합수(동반 출현) 가중."""
    if not chosen or not stats.pairs or strength == 0:
        return 1.0
    counts = [stats.pairs.get(frozenset((candidate, c)), 0) for c in chosen]
    avg = sum(counts) / len(counts)
    expected = stats.draws_used * (5 / 44) * (6 / 45) if stats.draws_used else 0
    if expected <= 0:
        return 1.0
    return max(MIN_WEIGHT, math.exp(strength * 0.5 * (avg - expected) / expected))


def _weighted_sample(
    pool: Sequence[int],
    k: int,
    weights: dict[int, float],
    stats: NumberStats,
    strategy: Strategy,
    chosen: list[int],
    rng: random.Random,
) -> list[int]:
    """비복원 가중 추출. 한 개 뽑을 때마다 궁합수 가중을 다시 계산한다."""
    remaining = list(pool)
    picked: list[int] = []
    for _ in range(k):
        if not remaining:
            break
        ws = [
            weights[n] * _companion_boost(n, chosen + picked, stats, strategy.w_companion)
            for n in remaining
        ]
        total = sum(ws)
        if total <= 0:
            choice = rng.choice(remaining)
        else:
            r = rng.random() * total
            acc = 0.0
            choice = remaining[-1]
            for n, w in zip(remaining, ws):
                acc += w
                if r <= acc:
                    choice = n
                    break
        picked.append(choice)
        remaining.remove(choice)
    return picked


def _forced_numbers(
    strategy: Strategy,
    previous: Draw | None,
    weights: dict[int, float],
    stats: NumberStats,
    rng: random.Random,
) -> list[int]:
    """전략이 요구하는 고정 번호(이월수 / 직전 보너스볼)를 정한다."""
    forced: list[int] = []
    if previous is None:
        return forced
    if strategy.use_prev_bonus:
        forced.append(previous.bonus)
    if strategy.carryover_target > 0:
        pool = [n for n in previous.numbers if n not in forced]
        forced.extend(
            _weighted_sample(
                pool,
                min(strategy.carryover_target, len(pool)),
                weights,
                stats,
                strategy,
                forced,
                rng,
            )
        )
    return forced


def _pick_bonus(
    numbers: Sequence[int], weights: dict[int, float], rng: random.Random
) -> int:
    pool = [n for n in NUMBER_POOL if n not in numbers]
    ws = [weights[n] for n in pool]
    if sum(ws) <= 0:  # 기피수 설정으로 후보가 모두 0이면 균등 추첨
        return rng.choice(pool)
    return rng.choices(pool, weights=ws, k=1)[0]


def generate_line(
    strategy: Strategy,
    stats: NumberStats,
    previous: Draw | None = None,
    rng: random.Random | None = None,
    exclude: Sequence[int] = (),
    banned_sets: Sequence[frozenset[int]] = (),
    max_attempts: int = 4000,
    folklore: Folklore | None = None,
) -> Line:
    """한 줄을 만든다. 규칙을 못 맞추면 단계적으로 완화한다."""
    rng = rng or random.Random()
    weights = base_weights(strategy, stats, folklore, previous)
    prev_numbers = previous.numbers if previous else ()
    excluded = set(exclude) | (folklore.excluded() if folklore else set())
    banned = set(banned_sets)

    for attempt in range(1, max_attempts + 1):
        step = attempt // max(1, max_attempts // 6)  # 실패가 쌓이면 규칙 완화
        rules: Ruleset = strategy.rules if step == 0 else strategy.rules.relaxed(step)
        if previous is None:
            # 직전 회차를 모르면 이월수 조건은 의미가 없다.
            rules = _replace(rules, carryover_range=(0, PICK))

        forced = [n for n in _forced_numbers(strategy, previous, weights, stats, rng)
                  if n not in excluded]
        if len(forced) > PICK:
            forced = forced[:PICK]
        pool = [n for n in NUMBER_POOL if n not in forced and n not in excluded]
        rest = _weighted_sample(
            pool, PICK - len(forced), weights, stats, strategy, forced, rng
        )
        nums = tuple(sorted(forced + rest))
        if len(nums) < PICK or frozenset(nums) in banned:
            continue

        if not accepts(folklore, nums, lenient=step >= 3):
            continue

        verdict = check(nums, rules, prev_numbers)
        if verdict.ok:
            return Line(
                strategy=strategy,
                numbers=nums,
                bonus=_pick_bonus(nums, weights, rng),
                profile=verdict.profile,
                relaxed_step=step,
                attempts=attempt,
                luck=luck_score(folklore, nums, previous),
                omens=luck_tags(folklore, nums, previous),
            )

    raise RuntimeError(
        f"[{strategy.name}] 조건을 만족하는 조합을 찾지 못했습니다. 규칙을 완화하세요."
    )


def recommend(
    stats: NumberStats,
    previous: Draw | None = None,
    strategies: Sequence[Strategy] = DEFAULT_STRATEGIES,
    lines: int = 5,
    seed: int | None = None,
    exclude: Sequence[int] = (),
    folklore: Folklore | None = None,
) -> list[Line]:
    """서로 다른 전략으로 `lines`줄을 뽑는다. 줄끼리 조합이 겹치지 않게 한다."""
    rng = random.Random(seed)
    out: list[Line] = []
    used: list[frozenset[int]] = []
    for i in range(lines):
        strategy = strategies[i % len(strategies)]
        line = generate_line(
            strategy,
            stats,
            previous,
            rng,
            exclude=exclude,
            banned_sets=used,
            folklore=folklore,
        )
        used.append(frozenset(line.numbers))
        out.append(line)
    return out
