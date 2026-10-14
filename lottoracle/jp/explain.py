"""일본 로또 추천 한 줄에 '분석 핵심' 문장을 붙인다. 한국판 explain.py 와 같은 말투.

한국판과 다른 점: 볼 색상 배분은 없다(일본 로또 공은 번호대별 색이 정해져 있지 않다).
합계 비교 기준은 게임마다 다른 이론 기대값(로또6 132 · 로또7 133 · 미니로또 80)이다.
"""

from __future__ import annotations

from typing import Sequence

from ..folklore import same_ending_groups
from .data import JpDraw
from .folklore import Wishes, in_pool, neighbor_numbers
from .games import Game
from .metrics import ZONE_LABELS, expected_sum, profile, twin_numbers, zone_bounds


def _dots(nums) -> str:
    return "·".join(str(n) for n in nums)


def zone_phrase(game: Game, numbers: Sequence[int]) -> str:
    parts = []
    for (lo, hi), label in zip(zone_bounds(game), ZONE_LABELS):
        hit = [n for n in sorted(numbers) if lo <= n <= hi]
        if hit:
            parts.append(f"{label} {_dots(hit)}")
    return ", ".join(parts)


def analysis_note(game: Game, numbers: Sequence[int], relaxed_step: int,
                  previous: JpDraw | None, wishes: Wishes | None) -> str:
    """[분석 핵심] 문장. 사실 관계(어떤 규칙이 걸렸는지)만 담는다."""
    nums = tuple(sorted(numbers))
    bits: list[str] = []

    if previous:
        carry = sorted(set(nums) & set(previous.numbers))
        if carry:
            bits.append(f"직전 {previous.no}회 당첨수 {_dots(carry)}번을 이월수로 채포")
        bridge = sorted(set(nums) & set(previous.bonus))
        if bridge:
            bits.append(f"직전 보너스 {_dots(bridge)}번을 징검다리로 연결")
        neighbors = sorted(set(nums) & neighbor_numbers(game, previous))
        if neighbors:
            bits.append(f"이웃수 {_dots(neighbors)}번으로 파동 확장")
        if not carry:
            bits.append("이월수를 끊고 새 흐름으로 전환")

    twins = sorted(set(nums) & set(twin_numbers(game)))
    if twins:
        bits.append(f"쌍둥이수 {_dots(twins)}번을 축으로 배치")

    endings = same_ending_groups(nums)
    if endings:
        bits.append(f"동형수 {', '.join(_dots(g) for g in endings.values())} 라인을 융합")

    if wishes and wishes.enabled:
        hit = sorted(set(nums) & set(in_pool(game, wishes.lucky)))
        if hit:
            bits.append(f"행운수 {_dots(hit)}번을 고정")

    p = profile(game, nums, previous.numbers if previous else ())
    fit = "평균치 안에 안착" if relaxed_step == 0 else "완화된 기준으로 통과"
    bits.append(f"합계 {p.total}(평균 {expected_sum(game)})·홀짝 {p.odd}:{p.even}·AC {p.ac}로 {fit}")
    return ", ".join(bits) + "."
