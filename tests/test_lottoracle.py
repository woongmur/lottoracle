"""단위 테스트. 여기 쓰인 회차 데이터는 실제 당첨결과가 아니라 합성 데이터다."""

from __future__ import annotations

import random
import unittest

from lottoracle import filters, folklore, generator, metrics, stats
from lottoracle.data import Draw
from lottoracle.strategies import DEFAULT_STRATEGIES, by_key


def synthetic_draws(count: int = 120, seed: int = 7) -> list[Draw]:
    """테스트용 합성 회차. 진짜 당첨번호가 아니다."""
    rng = random.Random(seed)
    out: list[Draw] = []
    for i in range(1, count + 1):
        picked = sorted(rng.sample(range(1, 46), 7))
        out.append(Draw(no=i, numbers=tuple(picked[:6]), bonus=picked[6]))
    return out


class MetricsTest(unittest.TestCase):
    def test_ac_value_bounds(self):
        self.assertEqual(metrics.ac_value((1, 2, 3, 4, 5, 6)), 0)
        self.assertEqual(metrics.ac_value((1, 2, 3, 4, 5, 45)), 4)
        for _ in range(200):
            nums = random.sample(range(1, 46), 6)
            self.assertTrue(0 <= metrics.ac_value(nums) <= 10)

    def test_sum_expectation(self):
        self.assertEqual(filters.EXPECTED_SUM, 138)
        self.assertEqual(metrics.total_sum((1, 2, 3, 4, 5, 6)), 21)

    def test_runs_and_endings(self):
        self.assertEqual(metrics.max_consecutive_run((3, 4, 5, 20, 31, 44)), 3)
        self.assertEqual(metrics.consecutive_pairs((3, 4, 5, 20, 31, 44)), 2)
        self.assertEqual(metrics.ending_sum((3, 13, 23, 33, 43, 5)), 3 * 5 + 5)
        self.assertEqual(metrics.max_same_ending((3, 13, 23, 33, 43, 5)), 5)

    def test_zone_counts_cover_all(self):
        for _ in range(100):
            nums = random.sample(range(1, 46), 6)
            self.assertEqual(sum(metrics.zone_counts(nums)), 6)


class FilterTest(unittest.TestCase):
    def test_obvious_bad_combo_rejected(self):
        verdict = filters.check((1, 2, 3, 4, 5, 6), filters.Ruleset())
        self.assertFalse(verdict.ok)
        self.assertIn("합계", " ".join(verdict.violations))

    def test_evenly_spaced_combo_rejected_by_ac(self):
        # 등간격 조합은 차이값 종류가 적어 AC값이 낮다 — 당첨조합에서 드문 모양.
        verdict = filters.check((4, 11, 18, 25, 32, 39), filters.Ruleset())
        self.assertFalse(verdict.ok)
        self.assertTrue(any("AC" in v for v in verdict.violations))

    def test_average_shaped_combo_accepted(self):
        verdict = filters.check((3, 10, 18, 25, 34, 44), filters.Ruleset())
        self.assertTrue(verdict.ok, verdict.violations)

    def test_relaxation_widens_bounds(self):
        base = filters.Ruleset()
        loose = base.relaxed(2)
        self.assertLess(loose.sum_range[0], base.sum_range[0])
        self.assertGreater(loose.sum_range[1], base.sum_range[1])
        self.assertLessEqual(loose.ac_min, base.ac_min)


class FolkloreTest(unittest.TestCase):
    def test_ball_colors_match_official_zones(self):
        self.assertEqual(folklore.ball_color(1), "노랑")
        self.assertEqual(folklore.ball_color(20), "파랑")
        self.assertEqual(folklore.ball_color(30), "빨강")
        self.assertEqual(folklore.ball_color(40), "회색")
        self.assertEqual(folklore.ball_color(45), "초록")

    def test_slip_line_detection(self):
        self.assertTrue(folklore.is_slip_line((1, 2, 3, 4, 5, 6)))     # 같은 행
        self.assertTrue(folklore.is_slip_line((1, 8, 15, 22, 29, 36)))  # 같은 열
        self.assertFalse(folklore.is_slip_line((3, 11, 20, 27, 34, 42)))

    def test_zodiac_and_birthday(self):
        self.assertEqual(folklore.zodiac_of_year(1990), "말")
        self.assertIn(7, folklore.zodiac_numbers("1990"))
        self.assertEqual(folklore.birthday_numbers("1990-05-21"), (3, 5, 21))

    def test_dream_keyword_partial_match(self):
        self.assertEqual(folklore.dream_numbers("돼지꿈"), folklore.DREAM_NUMBERS["돼지"])
        self.assertEqual(folklore.dream_numbers("아무것도"), ())

    def test_avoid_numbers_excluded(self):
        fl = folklore.Folklore(avoid=(4, 44))
        mult = folklore.multipliers(fl, None)
        self.assertEqual(mult[4], 0.0)
        self.assertEqual(mult[44], 0.0)


class StatsTest(unittest.TestCase):
    def setUp(self):
        self.draws = synthetic_draws()

    def test_frequency_totals(self):
        st = stats.build(self.draws)
        self.assertEqual(sum(st.frequency.values()), len(self.draws) * 6)
        self.assertEqual(st.draws_used, len(self.draws))

    def test_gap_is_zero_for_latest_draw_numbers(self):
        st = stats.build(self.draws)
        for n in self.draws[-1].numbers:
            self.assertEqual(st.gap[n], 0)

    def test_profile_stats_render(self):
        text = stats.profile_stats(self.draws).render()
        self.assertIn("당첨번호 합 평균", text)


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.draws = synthetic_draws()
        self.stats = stats.build(self.draws)
        self.previous = self.draws[-1]

    def test_recommend_shape(self):
        lines = generator.recommend(self.stats, self.previous, seed=1)
        self.assertEqual(len(lines), 5)
        for line in lines:
            self.assertEqual(len(line.numbers), 6)
            self.assertEqual(len(set(line.numbers)), 6)
            self.assertNotIn(line.bonus, line.numbers)
            self.assertTrue(all(1 <= n <= 45 for n in (*line.numbers, line.bonus)))

    def test_lines_are_distinct(self):
        lines = generator.recommend(self.stats, self.previous, seed=3)
        sets = {frozenset(l.numbers) for l in lines}
        self.assertEqual(len(sets), len(lines))

    def test_seed_is_reproducible(self):
        a = generator.recommend(self.stats, self.previous, seed=99)
        b = generator.recommend(self.stats, self.previous, seed=99)
        self.assertEqual([l.numbers for l in a], [l.numbers for l in b])

    def test_carryover_strategy_reuses_previous_numbers(self):
        line = generator.generate_line(
            by_key("carryover"), self.stats, self.previous, random.Random(5)
        )
        overlap = set(line.numbers) & set(self.previous.numbers)
        self.assertGreaterEqual(len(overlap), 1)

    def test_bridge_strategy_uses_previous_bonus(self):
        line = generator.generate_line(
            by_key("bridge"), self.stats, self.previous, random.Random(5)
        )
        self.assertIn(self.previous.bonus, line.numbers)

    def test_aggressive_strategy_breaks_carryover(self):
        line = generator.generate_line(
            by_key("aggressive"), self.stats, self.previous, random.Random(11)
        )
        self.assertEqual(set(line.numbers) & set(self.previous.numbers), set())

    def test_avoid_numbers_never_appear(self):
        fl = folklore.Folklore(avoid=(4, 13, 44))
        lines = generator.recommend(self.stats, self.previous, seed=8, folklore=fl)
        for line in lines:
            self.assertFalse(set(line.numbers) & {4, 13, 44})

    def test_exclude_argument_respected(self):
        lines = generator.recommend(
            self.stats, self.previous, seed=8, exclude=(1, 2, 3, 45)
        )
        for line in lines:
            self.assertFalse(set(line.numbers) & {1, 2, 3, 45})

    def test_all_strategies_produce_valid_lines(self):
        for strategy in DEFAULT_STRATEGIES:
            line = generator.generate_line(
                strategy, self.stats, self.previous, random.Random(21)
            )
            self.assertEqual(len(line.numbers), 6, strategy.key)

    def test_works_without_history(self):
        empty = stats.build([])
        lines = generator.recommend(empty, None, seed=2)
        self.assertEqual(len(lines), 5)

    def test_folklore_color_balance_respected(self):
        fl = folklore.Folklore(max_per_color=3)
        lines = generator.recommend(self.stats, self.previous, seed=6, folklore=fl)
        for line in lines:
            if line.relaxed_step < 3:
                self.assertLessEqual(max(folklore.color_counts(line.numbers).values()), 3)


class CliTest(unittest.TestCase):
    def test_recommend_runs_offline(self):
        from lottoracle.cli import main

        self.assertEqual(main(["recommend", "--offline", "--seed", "1"]), 0)

    def test_check_command(self):
        from lottoracle.cli import main

        self.assertEqual(
            main(["check", "--offline", "3", "10", "18", "25", "34", "44"]), 0
        )


if __name__ == "__main__":
    unittest.main()
