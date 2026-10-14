"""일본 로또용 속설 가중 — 한국판 folklore.py 에서 번호 범위와 무관한 것만 옮겼다.

  행운수   사용자가 넣은 번호(운세 번호 포함) — 가중 ×1.6. 범위 밖 번호는 버린다
  기피수   사용자가 뺀 번호 — 가중 0 (절대 안 나온다)
  이웃수   직전 회차 번호(보너스 포함) ±1, 본숫자 자신은 빼고 — 가중 ×1.25
  쌍둥이수 11·22·33 — 가중 ×1.15

꿈해몽·띠 번호·볼 색상·용지 모양은 한국 로또(1~45, 동행복권 용지)에 묶인 속설이라
일본 쪽에는 넣지 않는다. 운세 탭의 행운 번호는 '행운수' 로 들어온다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .data import JpDraw
from .games import Game
from .metrics import number_pool, twin_numbers

LUCKY_WEIGHT = 1.6
NEIGHBOR_WEIGHT = 1.25
TWIN_WEIGHT = 1.15


@dataclass(frozen=True)
class Wishes:
    lucky: tuple[int, ...] = ()
    avoid: tuple[int, ...] = ()
    enabled: bool = True


def in_pool(game: Game, nums: Sequence[int]) -> tuple[int, ...]:
    """범위 안 번호만, 중복 없이 오름차순."""
    return tuple(sorted({n for n in nums if 1 <= n <= game.pool}))


def neighbor_numbers(game: Game, previous: JpDraw | None) -> set[int]:
    if previous is None:
        return set()
    out: set[int] = set()
    for n in previous.numbers + previous.bonus:
        out.update(m for m in (n - 1, n + 1) if 1 <= m <= game.pool)
    return out - set(previous.numbers)


def multipliers(game: Game, wishes: Wishes | None, previous: JpDraw | None) -> dict[int, float]:
    base = {n: 1.0 for n in number_pool(game)}
    if wishes is None or not wishes.enabled:
        return base
    for n in in_pool(game, wishes.lucky):
        base[n] *= LUCKY_WEIGHT
    for n in neighbor_numbers(game, previous):
        base[n] *= NEIGHBOR_WEIGHT
    for n in twin_numbers(game):
        base[n] *= TWIN_WEIGHT
    for n in in_pool(game, wishes.avoid):
        base[n] = 0.0
    return base
