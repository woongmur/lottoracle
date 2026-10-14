"""일본 로또 5줄을 서로 다른 성격으로 뽑기 위한 전략. 한국판 strategies.py 와 같은 다섯 가지.

통계적 근거는 없다. 줄마다 다른 모양이 나오게 하는 장치다. 규칙은 게임마다 기본값에서
끌어낸다(합계 범위·이월수 범위가 게임마다 다르다).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .filters import RELAX_STEP, Ruleset, default_rules
from .games import Game
from .metrics import twin_numbers


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    concept: str
    rules: Ruleset
    w_frequency: float = 0.0
    w_recent: float = 0.0
    w_gap: float = 0.0
    w_companion: float = 0.0
    w_twin: float = 0.0
    carryover_target: int = 0
    use_prev_bonus: bool = False


def carryover_rules(game: Game) -> Ruleset:
    """이월수를 강제로 넣는 전략은 이월수 하한을 1로 올린다."""
    return replace(default_rules(game), carryover_range=(1, 3))


def aggressive_rules(game: Game) -> Ruleset:
    """평균에서 벗어난 합계·끝수합도 받되 AC 는 더 깐깐하게, 이월은 끊는다."""
    r = default_rules(game)
    w = RELAX_STEP[game.key]["sum"]
    return replace(
        r,
        sum_range=(r.sum_range[0] - w, r.sum_range[1] + w),
        ac_min=r.ac_min + 1,
        end_sum_range=(r.end_sum_range[0] - 3, r.end_sum_range[1] + 5),
        carryover_range=(0, 0),
    )


def strategies(game: Game) -> tuple[Strategy, ...]:
    twins = "·".join(str(n) for n in twin_numbers(game))
    return (
        Strategy(
            key="balance", name="안정형 밸런스",
            concept="평균치 정중앙 조준 — 합계·홀짝·고저·구간을 모두 최빈값에 맞춘 기본형",
            w_frequency=0.5, w_recent=0.2, w_companion=0.5,
            rules=default_rules(game),
        ),
        Strategy(
            key="carryover", name="이월수 채포형",
            concept="직전 회차 당첨수 2개를 이월수로 채포하고 중심 구간으로 묶는 조합",
            w_frequency=0.4, w_recent=0.4, w_companion=0.7, carryover_target=2,
            rules=carryover_rules(game),
        ),
        Strategy(
            key="bridge", name="징검다리 저격형",
            concept=f"직전 보너스 숫자를 징검다리로 끌어오고 쌍둥이수({twins})를 얹은 그물망",
            w_frequency=0.3, w_recent=0.3, w_companion=0.6, w_twin=1.2,
            carryover_target=1, use_prev_bonus=True,
            rules=carryover_rules(game),
        ),
        Strategy(
            key="variant", name="변칙 조준형",
            concept="이월 파동 1개를 고정하고 장기 미출현수로 허리를 채운 변칙 조합",
            w_frequency=-0.2, w_recent=-0.3, w_gap=0.9, w_companion=0.3, carryover_target=1,
            rules=carryover_rules(game),
        ),
        Strategy(
            key="aggressive", name="공격형 라인업",
            concept="이월수를 완전히 끊고 장기 미출현·저빈도 번호로 구성한 롱샷",
            w_frequency=-0.5, w_recent=-0.6, w_gap=1.2, w_companion=0.2, carryover_target=0,
            rules=aggressive_rules(game),
        ),
    )


def by_key(game: Game, key: str) -> Strategy:
    for s in strategies(game):
        if s.key == key:
            return s
    raise KeyError(f"알 수 없는 전략: {key} (사용 가능: {[s.key for s in strategies(game)]})")
