"""추천 한 줄에 '분석 핵심' 코멘트를 붙인다 (사진 속 그 말투)."""

from __future__ import annotations

from typing import Sequence

from .data import Draw
from .folklore import Folklore, color_signature, neighbor_numbers, same_ending_groups
from .generator import Line
from .metrics import TWIN_NUMBERS, ZONE_BOUNDS

ZONE_LABELS = ("한 자리", "10번대", "20번대", "30번대", "40번대")


def zone_phrase(numbers: Sequence[int]) -> str:
    parts = []
    for (lo, hi), label in zip(ZONE_BOUNDS, ZONE_LABELS):
        hit = [n for n in numbers if lo <= n <= hi]
        if hit:
            parts.append(f"{label} {'·'.join(str(n) for n in hit)}")
    return ", ".join(parts)


def analysis_note(line: Line, previous: Draw | None, folklore: Folklore | None) -> str:
    """[분석 핵심] 문장을 조립한다. 사실 관계(어떤 규칙이 걸렸는지)만 담는다."""
    nums = line.numbers
    bits: list[str] = []

    if previous:
        carry = sorted(set(nums) & set(previous.numbers))
        if carry:
            bits.append(
                f"직전 {previous.no}회차 당첨수 {'·'.join(map(str, carry))}번을 이월수로 채포"
            )
        if previous.bonus in nums:
            bits.append(f"직전 보너스볼 {previous.bonus}번을 징검다리로 연결")
        neighbors = sorted(set(nums) & neighbor_numbers(previous))
        if neighbors:
            bits.append(f"이웃수 {'·'.join(map(str, neighbors))}번으로 파동 확장")
        if not carry and previous:
            bits.append("이월수를 끊고 새 흐름으로 전환")

    twins = sorted(set(nums) & set(TWIN_NUMBERS))
    if twins:
        bits.append(f"쌍둥이수 {'·'.join(map(str, twins))}번을 축으로 배치")

    endings = same_ending_groups(nums)
    if endings:
        pairs = ", ".join("·".join(map(str, g)) for g in endings.values())
        bits.append(f"동형수 {pairs} 라인을 융합")

    if folklore and folklore.enabled:
        wish = sorted(set(nums) & set(folklore.wish_numbers()))
        if wish:
            bits.append(f"행운·꿈수 {'·'.join(map(str, wish))}번을 고정")

    p = line.profile
    fit = "평균치 안에 안착" if line.relaxed_step == 0 else "완화된 기준으로 통과"
    bits.append(f"합계 {p.total}(평균 138)·홀짝 {p.odd}:{p.even}·AC {p.ac}로 {fit}")
    bits.append(f"볼 색상 배분 {color_signature(nums)}")
    return ", ".join(bits) + "."


def render_line(
    index: int, line: Line, previous: Draw | None, folklore: Folklore | None
) -> str:
    head = f"{index}조합 [{line.strategy.name}] : {line.render_numbers()}"
    relaxed = f"  (규칙 {line.relaxed_step}단계 완화)" if line.relaxed_step else ""
    return "\n".join(
        [
            head + relaxed,
            f"   [분석 핵심] {analysis_note(line, previous, folklore)}",
            f"   [지 표] {line.profile.summary()}",
            f"   [구 간] {zone_phrase(line.numbers)}",
            f"   [속 설] {' / '.join(line.omens)}  · 기분점수 {line.luck}/100",
        ]
    )
