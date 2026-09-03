"""채점(등수 판정)과 백테스트.

백테스트는 이 프로그램의 가장 정직한 부분이다: 과거 회차마다 '그 직전까지의 데이터'만
써서 추천을 만들고, 실제 당첨번호와 맞춰 본다. 결과는 순수 무작위 추첨과 구별되지
않아야 정상이고, 실제로 그렇다.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .data import Draw
from .metrics import NUMBER_POOL, PICK

RANK_LABEL = {1: "1등", 2: "2등", 3: "3등", 4: "4등", 5: "5등", 0: "낙첨"}
# 확률은 정확값, 상금은 대략적인 평균치(1~3등은 회차별 변동).
RANK_ODDS = {1: 1 / 8_145_060, 2: 6 / 8_145_060, 3: 228 / 8_145_060,
             4: 11_115 / 8_145_060, 5: 182_780 / 8_145_060}
RANK_PRIZE = {1: 2_000_000_000, 2: 55_000_000, 3: 1_500_000, 4: 50_000, 5: 5_000}
TICKET_PRICE = 1_000


def rank_of(nums: Sequence[int], draw: Draw) -> int:
    """등수: 1등 6개 / 2등 5개+보너스 / 3등 5개 / 4등 4개 / 5등 3개 / 0 낙첨."""
    hit = len(set(nums) & set(draw.numbers))
    if hit == 6:
        return 1
    if hit == 5:
        return 2 if draw.bonus in nums else 3
    if hit == 4:
        return 4
    if hit == 3:
        return 5
    return 0


@dataclass
class Graded:
    numbers: tuple[int, ...]
    hit: tuple[int, ...]
    bonus_hit: bool
    rank: int

    @property
    def label(self) -> str:
        return RANK_LABEL[self.rank]

    @property
    def prize(self) -> int:
        return RANK_PRIZE.get(self.rank, 0)


def grade(lines: Sequence[Sequence[int]], draw: Draw) -> list[Graded]:
    out = []
    for nums in lines:
        ordered = tuple(sorted(nums))
        out.append(
            Graded(
                numbers=ordered,
                hit=tuple(sorted(set(ordered) & set(draw.numbers))),
                bonus_hit=draw.bonus in ordered,
                rank=rank_of(ordered, draw),
            )
        )
    return out


# ---------------------------------------------------------------- 백테스트
Recommender = Callable[[Sequence[Draw], random.Random], list[tuple[int, ...]]]
"""(과거 회차들, 난수기) -> 추천 조합들. generator.recommend 를 감싼 클로저를 넘긴다."""


@dataclass
class BacktestResult:
    rounds: int
    lines_per_round: int
    model_ranks: dict[int, int] = field(default_factory=lambda: {r: 0 for r in range(6)})
    random_ranks: dict[int, int] = field(default_factory=lambda: {r: 0 for r in range(6)})
    model_prize: int = 0
    random_prize: int = 0
    best_model: list[tuple[int, int, tuple[int, ...]]] = field(default_factory=list)  # (회차, 등수, 조합)

    @property
    def tickets(self) -> int:
        return self.rounds * self.lines_per_round

    @property
    def spent(self) -> int:
        return self.tickets * TICKET_PRICE

    def expected_ranks(self) -> dict[int, float]:
        return {r: self.tickets * p for r, p in RANK_ODDS.items()}

    def summary_rows(self) -> list[dict]:
        exp = self.expected_ranks()
        rows = []
        for r in (1, 2, 3, 4, 5):
            rows.append(
                {
                    "rank": RANK_LABEL[r],
                    "model": self.model_ranks[r],
                    "random": self.random_ranks[r],
                    "expected": round(exp[r], 2),
                }
            )
        return rows

    def render(self) -> str:
        head = (
            f"백테스트 {self.rounds}회차 × {self.lines_per_round}줄 = {self.tickets}장 "
            f"(투입 {self.spent:,}원)"
        )
        lines = [head, f"{'등수':<6}{'모델':>8}{'무작위':>8}{'이론기대':>10}"]
        for row in self.summary_rows():
            lines.append(f"{row['rank']:<6}{row['model']:>8}{row['random']:>8}{row['expected']:>10}")
        lines.append(
            f"당첨금 합계  모델 {self.model_prize:,}원 (회수율 {self.model_prize / self.spent:.1%})"
            f"  /  무작위 {self.random_prize:,}원 (회수율 {self.random_prize / self.spent:.1%})"
        )
        if self.best_model:
            top = sorted(self.best_model, key=lambda t: t[1])[:5]
            lines.append("모델 최고 성적: " + ", ".join(
                f"{no}회 {RANK_LABEL[r]} {list(c)}" for no, r, c in top
            ))
        return "\n".join(lines)


def run(
    draws: Sequence[Draw],
    recommender: Recommender,
    rounds: int = 52,
    lines_per_round: int = 5,
    seed: int | None = None,
    end_no: int | None = None,
    min_history: int = 50,
) -> BacktestResult:
    """마지막 `rounds` 회차를 대상으로, 각 회차 직전까지의 데이터로 추천해 채점한다."""
    ordered = sorted(draws, key=lambda d: d.no)
    if end_no is not None:
        ordered = [d for d in ordered if d.no <= end_no]
    targets = ordered[-rounds:]
    rng = random.Random(seed)
    result = BacktestResult(rounds=0, lines_per_round=lines_per_round)

    by_index = {d.no: i for i, d in enumerate(ordered)}
    for target in targets:
        idx = by_index[target.no]
        history = ordered[:idx]
        if len(history) < min_history:
            continue
        result.rounds += 1

        model_lines = recommender(history, random.Random(rng.random()))[:lines_per_round]
        for g in grade(model_lines, target):
            result.model_ranks[g.rank] += 1
            result.model_prize += g.prize
            if g.rank:
                result.best_model.append((target.no, g.rank, g.numbers))

        random_lines = [tuple(sorted(rng.sample(NUMBER_POOL, PICK))) for _ in range(lines_per_round)]
        for g in grade(random_lines, target):
            result.random_ranks[g.rank] += 1
            result.random_prize += g.prize

    result.lines_per_round = lines_per_round
    return result
