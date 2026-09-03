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
from .model import Empirical, ScoreWeights, typicality, typicality_percentile
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
    typicality: float = 0.0     # 전형성 로그가능도 (높을수록 흔한 모양)
    percentile: float = 50.0    # 과거 당첨조합 대비 전형성 백분위
    pool_size: int = 1          # 이 줄을 고를 때 비교한 후보 수

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
    emp: Empirical | None = None,
    reference: Sequence[float] = (),
    candidates: int = 40,
    temperature: float = 1.0,
    max_overlap: int = 3,
    rules_override: Ruleset | None = None,
    score_weights: ScoreWeights = ScoreWeights(),
) -> Line:
    """한 줄을 만든다.

    1) 가중 추첨으로 규칙을 통과하는 후보를 `candidates`개 모은다 (못 모으면 규칙 완화).
    2) 실데이터 경험분포(`emp`)가 있으면 전형성 점수로 소프트맥스 선택한다.
       temperature 가 낮을수록 가장 흔한 모양을, 높을수록 다양하게 고른다.
    3) 이미 뽑힌 줄과 `max_overlap`개 넘게 겹치는 후보는 버린다.
    """
    rng = rng or random.Random()
    weights = base_weights(strategy, stats, folklore, previous)
    prev_numbers = previous.numbers if previous else ()
    excluded = set(exclude) | (folklore.excluded() if folklore else set())
    banned = set(banned_sets)
    base_rules = rules_override or strategy.rules
    found: list[tuple[tuple[int, ...], Profile, int, int]] = []  # (조합, 프로필, 완화단계, 시도)
    seen: set[frozenset[int]] = set()
    if emp is None:
        candidates = 1  # 점수화할 근거가 없으면 첫 통과 후보를 그대로 쓴다

    for attempt in range(1, max_attempts + 1):
        step = attempt // max(1, max_attempts // 6)  # 실패가 쌓이면 규칙 완화
        rules: Ruleset = base_rules if step == 0 else base_rules.relaxed(step)
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
        key = frozenset(nums)
        if len(nums) < PICK or key in banned or key in seen:
            continue
        overlap_limit = max_overlap if step < 3 else PICK
        if any(len(key & b) > overlap_limit for b in banned):
            continue
        if not accepts(folklore, nums, lenient=step >= 3):
            continue

        verdict = check(nums, rules, prev_numbers)
        if not verdict.ok:
            continue
        seen.add(key)
        found.append((nums, verdict.profile, step, attempt))
        if len(found) >= candidates:
            break

    if not found:
        raise RuntimeError(
            f"[{strategy.name}] 조건을 만족하는 조합을 찾지 못했습니다. 규칙을 완화하세요."
        )

    # ---- 전형성으로 선택 ----
    scores = [
        typicality(nums, emp, prev_numbers, score_weights) if emp else 0.0
        for nums, _, _, _ in found
    ]
    if emp is not None and len(found) > 1:
        t = max(0.05, temperature)
        top = max(scores)
        ws = [math.exp((sc - top) / t) for sc in scores]
        chosen = rng.choices(range(len(found)), weights=ws, k=1)[0]
    else:
        chosen = 0
    nums, prof, step, attempt = found[chosen]
    score = scores[chosen]
    return Line(
        strategy=strategy,
        numbers=nums,
        bonus=_pick_bonus(nums, weights, rng),
        profile=prof,
        relaxed_step=step,
        attempts=attempt,
        luck=luck_score(folklore, nums, previous),
        omens=luck_tags(folklore, nums, previous),
        typicality=score,
        percentile=typicality_percentile(score, reference) if emp else 50.0,
        pool_size=len(found),
    )


def recommend(
    stats: NumberStats,
    previous: Draw | None = None,
    strategies: Sequence[Strategy] = DEFAULT_STRATEGIES,
    lines: int = 5,
    seed: int | None = None,
    exclude: Sequence[int] = (),
    folklore: Folklore | None = None,
    emp: Empirical | None = None,
    reference: Sequence[float] = (),
    candidates: int = 40,
    temperature: float = 1.0,
    max_overlap: int = 3,
    rules_override: Ruleset | None = None,
    score_weights: ScoreWeights = ScoreWeights(),
) -> list[Line]:
    """서로 다른 전략으로 `lines`줄을 뽑는다. 줄끼리 조합이 겹치지 않게 한다.

    rules_override 를 주면(예: model.calibrate 결과) 전략별 규칙 대신 그것을 쓰되,
    이월수 범위만은 전략이 요구하는 값을 유지한다.
    """
    rng = random.Random(seed)
    out: list[Line] = []
    used: list[frozenset[int]] = []
    for i in range(lines):
        strategy = strategies[i % len(strategies)]
        rules = None
        if rules_override is not None:
            rules = _replace(rules_override, carryover_range=strategy.rules.carryover_range)
        line = generate_line(
            strategy,
            stats,
            previous,
            rng,
            exclude=exclude,
            banned_sets=used,
            folklore=folklore,
            emp=emp,
            reference=reference,
            candidates=candidates,
            temperature=temperature,
            max_overlap=max_overlap,
            rules_override=rules,
            score_weights=score_weights,
        )
        used.append(frozenset(line.numbers))
        out.append(line)
    return out
