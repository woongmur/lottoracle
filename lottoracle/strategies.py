"""5줄을 서로 다른 성격으로 뽑기 위한 전략 정의.

커뮤니티에 도는 '로또 공식'(이월수 채포, 직전 보너스볼 징검다리, 쌍둥이수, 궁합수)을
가중치로 옮겨 놓은 것이다. 통계적 근거는 없고, 줄마다 다른 모양이 나오게 하는 장치다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .filters import Ruleset


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    concept: str
    w_frequency: float = 0.0   # 장기 출현 빈도 가중 (+면 다출현수 선호)
    w_recent: float = 0.0      # 최근 N회 출현 가중 (+면 '핫넘버')
    w_gap: float = 0.0         # 미출현 기간 가중 (+면 '콜드/장기미출현')
    w_companion: float = 0.0   # 이미 뽑힌 번호와의 궁합수 가중
    w_twin: float = 0.0        # 쌍둥이수(11·22·33·44) 가중
    carryover_target: int = 0  # 직전 회차 당첨번호에서 강제로 넣을 개수
    use_prev_bonus: bool = False  # 직전 보너스볼을 '징검다리'로 고정
    rules: Ruleset = field(default_factory=Ruleset)


BALANCED_RULES = Ruleset()
# 이월수를 강제로 넣는 전략은 이월수 상한을 풀어줘야 한다.
CARRYOVER_RULES = Ruleset(carryover_range=(1, 3))
# 공격형은 평균에서 벗어난 조합도 허용한다.
AGGRESSIVE_RULES = Ruleset(
    sum_range=(90, 190), ac_min=8, end_sum_range=(12, 40), carryover_range=(0, 0)
)


DEFAULT_STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        key="balance",
        name="안정형 밸런스",
        concept="평균치 정중앙 조준 — 합계·홀짝·고저·구간을 모두 최빈값에 맞춘 기본형",
        w_frequency=0.5,
        w_recent=0.2,
        w_companion=0.5,
        rules=BALANCED_RULES,
    ),
    Strategy(
        key="carryover",
        name="이월수 채포형",
        concept="직전 회차 당첨수 2개를 이월수로 채포하고 중심 구간으로 묶는 조합",
        w_frequency=0.4,
        w_recent=0.4,
        w_companion=0.7,
        carryover_target=2,
        rules=CARRYOVER_RULES,
    ),
    Strategy(
        key="bridge",
        name="징검다리 저격형",
        concept="직전 보너스볼을 징검다리로 끌어오고 쌍둥이수(11·22·33·44)를 얹은 그물망",
        w_frequency=0.3,
        w_recent=0.3,
        w_companion=0.6,
        w_twin=1.2,
        carryover_target=1,
        use_prev_bonus=True,
        rules=CARRYOVER_RULES,
    ),
    Strategy(
        key="variant",
        name="변칙 조준형",
        concept="이월 파동 1개를 고정하고 장기 미출현수로 허리를 채운 변칙 조합",
        w_frequency=-0.2,
        w_recent=-0.3,
        w_gap=0.9,
        w_companion=0.3,
        carryover_target=1,
        rules=CARRYOVER_RULES,
    ),
    Strategy(
        key="aggressive",
        name="공격형 라인업",
        concept="이월수를 완전히 끊고 장기 미출현·저빈도 번호로 구성한 롱샷",
        w_frequency=-0.5,
        w_recent=-0.6,
        w_gap=1.2,
        w_companion=0.2,
        carryover_target=0,
        rules=AGGRESSIVE_RULES,
    ),
)


def by_key(key: str) -> Strategy:
    for s in DEFAULT_STRATEGIES:
        if s.key == key:
            return s
    raise KeyError(f"알 수 없는 전략: {key} (사용 가능: {[s.key for s in DEFAULT_STRATEGIES]})")
