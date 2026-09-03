"""대한민국 로또 평균치에 기반한 조합 필터.

여기 들어있는 기본값은 1회차 이후 실제 당첨조합 분포에서 관찰되는 '흔한 구간'이다.
확률을 올려주지는 않는다. 지나치게 튀는 모양(1·2·3·4·5·6 같은)을 걸러낼 뿐이다.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

from .metrics import Profile, profile

# 6개 번호 합의 이론적 기대값 = 6 * 23 = 138. 실제 당첨조합의 약 70%가 100~175 안에 든다.
EXPECTED_SUM = 138


@dataclass(frozen=True)
class Ruleset:
    """조합이 통과해야 할 조건. 값을 넉넉히 잡을수록 후보가 늘어난다."""

    sum_range: tuple[int, int] = (100, 175)
    odd_range: tuple[int, int] = (2, 4)          # 홀수 개수, 3:3이 최빈
    low_range: tuple[int, int] = (2, 4)          # 1~22 개수, 3:3이 최빈
    ac_min: int = 7                              # 당첨조합 AC값 최빈 8
    max_run: int = 2                             # 연속수는 2연속까지 허용
    max_consecutive_pairs: int = 1
    max_per_zone: int = 3                        # 한 구간(예: 30번대)에 4개 이상 몰리지 않게
    min_zones: int = 3                           # 최소 3개 구간에 분산
    end_sum_range: tuple[int, int] = (15, 35)    # 끝수합
    max_same_ending: int = 2                     # 같은 끝수 3개 이상 금지
    mult3_range: tuple[int, int] = (0, 4)
    spread_min: int = 20                         # 최댓값-최솟값
    carryover_range: tuple[int, int] = (0, 2)    # 이월수(직전 회차 중복)
    forbid_all_same_parity: bool = True

    def relaxed(self, step: int = 1) -> "Ruleset":
        """후보를 못 찾을 때 단계적으로 완화한 규칙을 만든다."""
        s = max(0, step)
        return replace(
            self,
            sum_range=(self.sum_range[0] - 12 * s, self.sum_range[1] + 12 * s),
            odd_range=(max(0, self.odd_range[0] - s), min(6, self.odd_range[1] + s)),
            low_range=(max(0, self.low_range[0] - s), min(6, self.low_range[1] + s)),
            ac_min=max(0, self.ac_min - s),
            max_run=min(6, self.max_run + s),
            max_consecutive_pairs=min(5, self.max_consecutive_pairs + s),
            max_per_zone=min(6, self.max_per_zone + s),
            min_zones=max(1, self.min_zones - s),
            end_sum_range=(
                max(0, self.end_sum_range[0] - 5 * s),
                min(54, self.end_sum_range[1] + 5 * s),
            ),
            max_same_ending=min(6, self.max_same_ending + s),
            mult3_range=(max(0, self.mult3_range[0] - s), min(6, self.mult3_range[1] + s)),
            spread_min=max(0, self.spread_min - 6 * s),
            carryover_range=(0, min(6, self.carryover_range[1] + s)),
        )


@dataclass
class Verdict:
    """필터 결과와, 떨어졌다면 그 이유."""

    ok: bool
    profile: Profile
    violations: list[str] = field(default_factory=list)


def _in(value: int, bounds: tuple[int, int]) -> bool:
    return bounds[0] <= value <= bounds[1]


def check(nums: Sequence[int], rules: Ruleset, previous: Sequence[int] = ()) -> Verdict:
    p = profile(nums, previous)
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
    if rules.forbid_all_same_parity and p.odd in (0, 6):
        bad.append("전부 홀수 또는 전부 짝수")

    return Verdict(ok=not bad, profile=p, violations=bad)


def passes(nums: Sequence[int], rules: Ruleset, previous: Sequence[int] = ()) -> bool:
    return check(nums, rules, previous).ok
