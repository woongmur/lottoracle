"""일본 로또 조합 필터. 한국판 filters.py 의 규칙을 게임별 값으로 바꾼 것.

기본값은 1회부터의 실제 당첨조합(2026-10 기준 로또6 2,145회 · 로또7 698회 ·
미니로또 1,408회)에서 정했다. 항목 하나하나는 실제 당첨조합의 80% 이상이 통과한다
(괄호 안 비율). 전부를 한꺼번에 통과하는 것은 38~48% 다(한국판 기본값은 36%).
화면에서는 보통 model.calibrate 가 최신 데이터로 다시 맞춘 값을 쓰고, 여기 값은 그 바탕과
보정에 쓰지 않는 항목(연속·구간·끝수·3배수)에 쓰인다. 확률을 올려 주지는 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

from .games import Game
from .metrics import Profile, profile


@dataclass(frozen=True)
class Ruleset:
    sum_range: tuple[int, int]
    odd_range: tuple[int, int]
    low_range: tuple[int, int]
    ac_min: int
    max_run: int
    max_consecutive_pairs: int
    max_per_zone: int
    min_zones: int
    end_sum_range: tuple[int, int]
    max_same_ending: int
    mult3_range: tuple[int, int]
    spread_min: int
    carryover_range: tuple[int, int]
    forbid_all_same_parity: bool = True


# 실제 분포(2026-10)에서 정한 값. 괄호는 그 범위에 드는 실제 당첨조합 비율.
DEFAULT_RULES: dict[str, Ruleset] = {
    "loto6": Ruleset(
        sum_range=(95, 170),          # 10~90%
        odd_range=(2, 4),             # 82%
        low_range=(2, 4),             # 81% (저구간 1~21)
        ac_min=6,                     # 95%
        max_run=2,                    # 93%
        max_consecutive_pairs=1,      # 86%
        max_per_zone=3,               # 92%
        min_zones=3,                  # 96%
        end_sum_range=(17, 35),       # 10~90%
        max_same_ending=2,            # 91%
        mult3_range=(0, 4),           # 99%
        spread_min=20,                # 95%
        carryover_range=(0, 2),       # 98%
    ),
    "loto7": Ruleset(
        sum_range=(101, 167),         # 10~90%
        odd_range=(2, 5),             # 92%
        low_range=(2, 5),             # 91% (저구간 1~18)
        ac_min=8,                     # 92%
        max_run=3,                    # 95% — 7개라 연속이 흔하다
        max_consecutive_pairs=2,      # 92%
        max_per_zone=4,               # 97%
        min_zones=3,                  # 98%
        end_sum_range=(23, 39),       # 10~90%
        max_same_ending=2,            # 88%
        mult3_range=(0, 4),           # 97%
        spread_min=20,                # 94%
        carryover_range=(0, 3),       # 98%
    ),
    "miniloto": Ruleset(
        sum_range=(56, 105),          # 10~90%
        odd_range=(1, 4),             # 95%
        low_range=(1, 4),             # 95% (저구간 1~15)
        ac_min=4,                     # 90%
        max_run=2,                    # 92%
        max_consecutive_pairs=1,      # 88%
        max_per_zone=3,               # 93%
        min_zones=2,                  # 99.7% — 30번대가 30·31 둘뿐이라 구간이 사실상 셋
        end_sum_range=(13, 29),       # 10~90%
        max_same_ending=2,            # 97%
        mult3_range=(0, 3),           # 98%
        spread_min=14,                # 92%
        carryover_range=(0, 2),       # 98%
    ),
}

# 후보를 못 찾을 때 한 단계에 풀어 주는 폭. 합계는 기대값의 약 1/11, 번호폭은 범위의 약 1/7.
RELAX_STEP: dict[str, dict[str, int]] = {
    "loto6": {"sum": 12, "end_sum": 5, "spread": 6},
    "loto7": {"sum": 12, "end_sum": 5, "spread": 5},
    "miniloto": {"sum": 7, "end_sum": 5, "spread": 4},
}


def default_rules(game: Game) -> Ruleset:
    return DEFAULT_RULES[game.key]


def relaxed(game: Game, rules: Ruleset, step: int = 1) -> Ruleset:
    """후보를 못 찾을 때 단계적으로 완화한 규칙."""
    s = max(0, step)
    k = game.pick
    w = RELAX_STEP[game.key]
    return replace(
        rules,
        sum_range=(rules.sum_range[0] - w["sum"] * s, rules.sum_range[1] + w["sum"] * s),
        odd_range=(max(0, rules.odd_range[0] - s), min(k, rules.odd_range[1] + s)),
        low_range=(max(0, rules.low_range[0] - s), min(k, rules.low_range[1] + s)),
        ac_min=max(0, rules.ac_min - s),
        max_run=min(k, rules.max_run + s),
        max_consecutive_pairs=min(k - 1, rules.max_consecutive_pairs + s),
        max_per_zone=min(k, rules.max_per_zone + s),
        min_zones=max(1, rules.min_zones - s),
        end_sum_range=(
            max(0, rules.end_sum_range[0] - w["end_sum"] * s),
            min(9 * k, rules.end_sum_range[1] + w["end_sum"] * s),
        ),
        max_same_ending=min(k, rules.max_same_ending + s),
        mult3_range=(max(0, rules.mult3_range[0] - s), min(k, rules.mult3_range[1] + s)),
        spread_min=max(0, rules.spread_min - w["spread"] * s),
        carryover_range=(0, min(k, rules.carryover_range[1] + s)),
    )


@dataclass
class Verdict:
    ok: bool
    profile: Profile
    violations: list[str] = field(default_factory=list)


def _in(value: int, bounds: tuple[int, int]) -> bool:
    return bounds[0] <= value <= bounds[1]


def check(game: Game, nums: Sequence[int], rules: Ruleset, previous: Sequence[int] = ()) -> Verdict:
    p = profile(game, nums, previous)
    bad: list[str] = []
    if not _in(p.total, rules.sum_range):
        bad.append(f"합계 {p.total} (허용 {rules.sum_range[0]}~{rules.sum_range[1]})")
    if not _in(p.odd, rules.odd_range):
        bad.append(f"홀짝 {p.odd}:{p.even}")
    if not _in(p.low, rules.low_range):
        bad.append(f"고저 {p.low}:{p.high}")
    if p.ac < rules.ac_min:
        bad.append(f"AC값 {p.ac} (최소 {rules.ac_min})")
    if p.max_run > rules.max_run:
        bad.append(f"{p.max_run}연속수")
    if p.consecutive > rules.max_consecutive_pairs:
        bad.append(f"연속쌍 {p.consecutive}개")
    if max(p.zones) > rules.max_per_zone:
        bad.append(f"한 구간에 {max(p.zones)}개 집중")
    if sum(1 for z in p.zones if z) < rules.min_zones:
        bad.append(f"분포 구간 {sum(1 for z in p.zones if z)}개")
    if not _in(p.end_sum, rules.end_sum_range):
        bad.append(f"끝수합 {p.end_sum}")
    if p.same_ending > rules.max_same_ending:
        bad.append(f"같은 끝수 {p.same_ending}개")
    if not _in(p.mult3, rules.mult3_range):
        bad.append(f"3배수 {p.mult3}개")
    if p.spread < rules.spread_min:
        bad.append(f"번호 폭 {p.spread}")
    if not _in(p.carryover, rules.carryover_range):
        bad.append(f"이월수 {p.carryover}개")
    if rules.forbid_all_same_parity and p.odd in (0, game.pick):
        bad.append("전부 홀수 또는 전부 짝수")
    return Verdict(ok=not bad, profile=p, violations=bad)


def passes(game: Game, nums: Sequence[int], rules: Ruleset, previous: Sequence[int] = ()) -> bool:
    return check(game, nums, rules, previous).ok
