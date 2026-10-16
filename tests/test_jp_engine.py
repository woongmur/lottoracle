"""일본 로또 엔진(파이썬 쪽) — 지표 · 필터 기본값 · 보정 · 전형성 · 설명 문장.

이 모듈들은 JS(web/src/jp/)의 정답지다. JS 와의 대조는 tools/gen_golden.py →
web/test/jp_golden.test.js 가 하고, 여기서는 정답지 자체가 맞는지를 본다.
"""

from __future__ import annotations

import unittest
from itertools import combinations

from lottoracle.jp import data, explain, filters, folklore, metrics, model, stats, strategies
from lottoracle.jp.games import GAMES

L6, L7, MINI = GAMES["loto6"], GAMES["loto7"], GAMES["miniloto"]
DRAWS = {k: data.load(k) for k in GAMES}


class Metrics(unittest.TestCase):
    def test_파생값(self):
        self.assertEqual([metrics.low_max(g) for g in (L6, L7, MINI)], [21, 18, 15])
        self.assertEqual([metrics.expected_sum(g) for g in (L6, L7, MINI)], [132, 133, 80])
        self.assertEqual(metrics.zone_bounds(L6), ((1, 9), (10, 19), (20, 29), (30, 39), (40, 43)))
        self.assertEqual(metrics.zone_bounds(MINI), ((1, 9), (10, 19), (20, 29), (30, 31)))
        self.assertEqual(metrics.twin_numbers(L6), (11, 22, 33))
        self.assertEqual(metrics.twin_numbers(MINI), (11, 22))
        self.assertEqual([metrics.max_ac(g) for g in (L6, L7, MINI)], [10, 15, 6])

    def test_AC_최댓값은_실제로_닿는다(self):
        """max_ac 가 상한일 뿐 아니라 실제로 나올 수 있는 값인지 (미니로또는 전수 확인)."""
        best = max(metrics.profile(MINI, c).ac for c in combinations(range(1, 32), 5))
        self.assertEqual(best, metrics.max_ac(MINI))

    def test_구간_가짓수가_전수와_같다(self):
        for game in (MINI,):
            pats = {tuple(sorted(metrics.zone_counts(game, c)))
                    for c in combinations(range(1, game.pool + 1), game.pick)}
            self.assertEqual(len(pats), model.ZONE_PATTERNS[game.key])

    def test_프로필(self):
        p = metrics.profile(L7, (34, 10, 13, 21, 24, 28, 29), previous=(1, 6, 12, 23, 28, 32, 36))
        self.assertEqual(p.numbers, (10, 13, 21, 24, 28, 29, 34))
        self.assertEqual((p.total, p.odd, p.low, p.carryover), (159, 3, 2, 1))
        self.assertEqual(p.zones, (0, 2, 4, 1))
        self.assertEqual(p.max_run, 2)


class Rules(unittest.TestCase):
    def test_기본값_항목마다_실제_당첨조합_대부분이_통과한다(self):
        """주석에 적은 비율의 근거. 회차가 늘어도 크게 흔들리지 않게 75% 를 하한으로 본다."""
        for key, game in GAMES.items():
            draws = DRAWS[key]
            rules = filters.default_rules(game)
            fails: dict[str, int] = {}
            for i, d in enumerate(draws):
                prev = draws[i - 1].numbers if i else ()
                for v in filters.check(game, d.numbers, rules, prev).violations:
                    head = v.split()[0]
                    fails[head] = fails.get(head, 0) + 1
            for head, n in fails.items():
                with self.subTest(game=key, rule=head):
                    self.assertGreater(1 - n / len(draws), 0.75)

    def test_완화하면_넓어지고_상한을_넘지_않는다(self):
        for game in GAMES.values():
            base = filters.default_rules(game)
            r = filters.relaxed(game, base, 10)
            self.assertLessEqual(r.odd_range[1], game.pick)
            self.assertLessEqual(r.max_consecutive_pairs, game.pick - 1)
            self.assertLessEqual(r.end_sum_range[1], 9 * game.pick)
            self.assertEqual(r.min_zones, 1)
            self.assertLess(r.sum_range[0], base.sum_range[0])

    def test_전부_홀수는_게임_개수로_판단한다(self):
        odd7 = (1, 3, 5, 7, 9, 11, 13)
        self.assertIn("전부 홀수 또는 전부 짝수", filters.check(L7, odd7, filters.default_rules(L7)).violations)

    def test_보정은_기본값과_같은_모양(self):
        for key, game in GAMES.items():
            r = model.calibrate(game, DRAWS[key], 0.8)
            self.assertLess(r.sum_range[0], metrics.expected_sum(game))
            self.assertGreater(r.sum_range[1], metrics.expected_sum(game))
            self.assertLessEqual(r.odd_range[1], game.pick)
            self.assertEqual(model.calibrate(game, [], 0.8), filters.default_rules(game))


class Typicality(unittest.TestCase):
    def test_흔한_모양이_극단보다_높다(self):
        for key, game in GAMES.items():
            emp = model.fit(game, DRAWS[key])
            extreme = model.typicality(tuple(range(1, game.pick + 1)), emp)
            common = model.typicality(DRAWS[key][len(DRAWS[key]) // 2].numbers, emp)
            self.assertGreater(common, extreme, key)

    def test_평활_확률의_합은_1(self):
        """지표마다 '나올 수 있는 값의 개수' 를 제대로 셌다면 확률을 다 더해 1 이 된다."""
        for key, game in GAMES.items():
            emp = model.fit(game, DRAWS[key])
            k = game.pick
            self.assertAlmostEqual(sum(emp.p_odd(v) for v in range(k + 1)), 1.0)
            self.assertAlmostEqual(sum(emp.p_ac(v) for v in range(metrics.max_ac(game) + 1)), 1.0)
            self.assertAlmostEqual(sum(emp.p_consecutive(v) for v in range(k)), 1.0)
            self.assertAlmostEqual(sum(emp.p_position(0, n) for n in range(1, game.pool + 1)), 1.0)
            self.assertAlmostEqual(sum(emp.p_total(v) for v in range(0, metrics.max_sum(game) + 1, 5)), 1.0)
            self.assertAlmostEqual(sum(emp.p_spread(v) for v in range(0, game.pool, 4)), 1.0)

    def test_데이터가_없으면_0점(self):
        self.assertEqual(model.typicality((1, 2, 3, 4, 5), model.fit(MINI, [])), 0.0)


class Words(unittest.TestCase):
    def test_전략_다섯(self):
        for game in GAMES.values():
            got = strategies.strategies(game)
            self.assertEqual([s.key for s in got], ["balance", "carryover", "bridge", "variant", "aggressive"])
            self.assertEqual(got[-1].rules.carryover_range, (0, 0))
        self.assertIn("(11·22)", strategies.by_key(MINI, "bridge").concept)

    def test_분석_문장(self):
        prev = data.JpDraw(698, "2026-10-09", (10, 13, 21, 24, 28, 29, 34), (1, 26))
        note = explain.analysis_note(L7, (2, 11, 21, 22, 26, 30, 37), 0, prev,
                                     folklore.Wishes(lucky=(37, 44)))
        # 이웃수: 직전 번호(보너스 1·26 포함) ±1 중 본숫자가 아닌 것 → 2·11·22·30 이 걸린다
        self.assertEqual(note, "직전 698회 당첨수 21번을 이월수로 채포, 직전 보너스 26번을 징검다리로 연결, "
                               "이웃수 2·11·22·30번으로 파동 확장, 쌍둥이수 11·22번을 축으로 배치, "
                               "동형수 2·22, 11·21 라인을 융합, 행운수 37번을 고정, "
                               "합계 149(평균 133)·홀짝 3:4·AC 10로 평균치 안에 안착.")
        self.assertNotIn("44", note, "범위 밖 행운수는 버린다")

    def test_구간_문장(self):
        self.assertEqual(explain.zone_phrase(L6, (43, 1, 20)), "한 자리 1, 20번대 20, 40번대 43")

    def test_이웃수는_범위와_보너스를_본다(self):
        prev = data.JpDraw(1, "2026-01-06", (1, 2, 15, 30, 31), (16,))
        # 본숫자 1·2·15·30·31 과 보너스 16 의 ±1. 0·32 는 범위 밖, 본숫자는 뺀다.
        # 16 은 보너스지만 15 의 이웃이라 남는다 (한국판과 같은 규칙).
        self.assertEqual(folklore.neighbor_numbers(MINI, prev), {3, 14, 16, 17, 29})


class NextDraw(unittest.TestCase):
    def test_다음_추첨일은_요일표대로(self):
        """JS nextDrawDate(web/test/jp_engine.test.js)와 같은 값."""
        from lottoracle.jp.games import next_draw_date
        self.assertEqual(next_draw_date(L6, "2026-10-12"), "2026-10-15")   # 월 → 목
        self.assertEqual(next_draw_date(L6, "2026-10-15"), "2026-10-19")   # 목 → 월
        self.assertEqual(next_draw_date(L7, "2026-10-09"), "2026-10-16")
        self.assertEqual(next_draw_date(MINI, "2026-10-13"), "2026-10-20")


class Stats(unittest.TestCase):
    def test_보너스_빈도는_보너스_개수만큼(self):
        st = stats.build(L7, DRAWS["loto7"])
        self.assertEqual(sum(st.bonus_frequency.values()), 2 * len(DRAWS["loto7"]))
        self.assertAlmostEqual(st.mean_frequency, len(DRAWS["loto7"]) * 7 / 37)


if __name__ == "__main__":
    unittest.main()
