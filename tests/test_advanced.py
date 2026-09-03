"""고도화 모듈 테스트: xlsx 입력, 보정/전형성 모델, 채점/백테스트, 엔진, 웹 API.

실데이터(data/draws.json, 1~1239회차)를 그대로 쓴다.
"""

from __future__ import annotations

import json
import os
import random
import threading
import unittest
import urllib.request

from lottoracle import backtest, data, model, stats
from lottoracle.data import Draw
from lottoracle.engine import Engine, Options, draw_date_of
from lottoracle.web import make_server

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "source", "lotto_1-1239.xlsx")


class XlsxTest(unittest.TestCase):
    def test_reads_full_history(self):
        draws = data.load_xlsx(XLSX)
        self.assertEqual(len(draws), 1239)
        self.assertEqual(draws[0].no, 1)
        self.assertEqual(draws[0].numbers, (10, 23, 29, 33, 37, 40))
        self.assertEqual(draws[0].bonus, 16)
        self.assertEqual(draws[-1].no, 1239)
        self.assertEqual(draws[-1].numbers, (11, 13, 22, 32, 33, 36))
        self.assertEqual(draws[-1].bonus, 8)
        self.assertEqual(draws[-1].first_winners, 13)
        self.assertEqual(draws[-1].first_prize, 2_214_789_375)

    def test_cache_matches_xlsx(self):
        cached = data.load_draws()
        fresh = data.load_xlsx(XLSX)
        self.assertEqual([d.numbers for d in cached], [d.numbers for d in fresh])

    def test_merge_prefers_incoming(self):
        a = [Draw(no=1, numbers=(1, 2, 3, 4, 5, 6), bonus=7)]
        b = [Draw(no=1, numbers=(10, 20, 30, 40, 41, 42), bonus=7), Draw(no=2, numbers=(1, 2, 3, 4, 5, 6), bonus=7)]
        merged = data.merge(a, b)
        self.assertEqual([d.no for d in merged], [1, 2])
        self.assertEqual(merged[0].numbers, (10, 20, 30, 40, 41, 42))

    def test_draw_date_formula(self):
        self.assertEqual(draw_date_of(1), "2002-12-07")
        self.assertEqual(draw_date_of(2), "2002-12-14")


class ModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draws = data.load_draws()
        cls.emp = model.fit(cls.draws)

    def test_real_data_averages(self):
        ps = stats.profile_stats(self.draws)
        self.assertAlmostEqual(ps.mean_sum, 138, delta=3)
        self.assertEqual(max(ps.ac_distribution, key=ps.ac_distribution.get), 8)
        self.assertEqual(max(ps.odd_distribution, key=ps.odd_distribution.get), 3)

    def test_calibrated_rules_widen_with_coverage(self):
        tight = model.calibrate(self.draws, 0.6)
        loose = model.calibrate(self.draws, 0.95)
        self.assertLess(loose.sum_range[0], tight.sum_range[0])
        self.assertGreater(loose.sum_range[1], tight.sum_range[1])
        self.assertLessEqual(loose.ac_min, tight.ac_min)

    def test_typicality_ranks_degenerate_combo_last(self):
        ref = model.reference_scores(self.draws, self.emp)
        worst = model.typicality((1, 2, 3, 4, 5, 6), self.emp)
        normal = model.typicality((3, 10, 18, 25, 34, 44), self.emp)
        self.assertLess(worst, normal)
        self.assertEqual(model.typicality_percentile(worst, ref), 0.0)
        self.assertGreater(model.typicality_percentile(normal, ref), 50.0)

    def test_empty_history_scores_zero(self):
        self.assertEqual(model.typicality((1, 2, 3, 4, 5, 6), model.fit([])), 0.0)


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.draw = Draw(no=1239, numbers=(11, 13, 22, 32, 33, 36), bonus=8)

    def test_rank_table(self):
        self.assertEqual(backtest.rank_of((11, 13, 22, 32, 33, 36), self.draw), 1)
        self.assertEqual(backtest.rank_of((11, 13, 22, 32, 33, 8), self.draw), 2)
        self.assertEqual(backtest.rank_of((11, 13, 22, 32, 36, 45), self.draw), 3)  # 사진 속 3조합
        self.assertEqual(backtest.rank_of((11, 13, 22, 32, 1, 2), self.draw), 4)
        self.assertEqual(backtest.rank_of((11, 13, 22, 1, 2, 3), self.draw), 5)
        self.assertEqual(backtest.rank_of((1, 2, 3, 4, 5, 6), self.draw), 0)

    def test_grade_reports_hits(self):
        g = backtest.grade([(11, 13, 22, 32, 36, 45)], self.draw)[0]
        self.assertEqual(g.hit, (11, 13, 22, 32, 36))
        self.assertFalse(g.bonus_hit)
        self.assertEqual(g.prize, backtest.RANK_PRIZE[3])

    def test_backtest_counts_add_up(self):
        draws = data.load_draws()

        def recommender(history, rng):
            return [tuple(sorted(rng.sample(range(1, 46), 6))) for _ in range(5)]

        r = backtest.run(draws, recommender, rounds=8, lines_per_round=5, seed=1)
        self.assertEqual(r.rounds, 8)
        self.assertEqual(sum(r.model_ranks.values()), 40)
        self.assertEqual(sum(r.random_ranks.values()), 40)
        self.assertIn("백테스트 8회차", r.render())


class EngineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine.load()

    def test_options_parse_and_clamp(self):
        o = Options.from_dict({"lines": "99", "seed": "", "lucky": "7, 13", "coverage": "2"})
        self.assertEqual(o.lines, 20)
        self.assertIsNone(o.seed)
        self.assertEqual(o.lucky, (7, 13))
        self.assertEqual(o.coverage, 0.99)
        with self.assertRaises(ValueError):
            Options.from_dict({"avoid": "46"})

    def test_recommend_payload(self):
        p = self.engine.recommend_payload(Options(seed=11, lines=3))
        self.assertEqual(len(p["lines"]), 3)
        self.assertEqual(p["next_draw_no"], 1240)
        for ln in p["lines"]:
            self.assertEqual(len(ln["numbers"]), 6)
            self.assertNotIn(ln["bonus"], ln["numbers"])
            self.assertEqual(len(ln["colors"]), 6)
            self.assertTrue(0 <= ln["percentile"] <= 100)

    def test_calibrated_lines_pass_calibrated_rules(self):
        from lottoracle.filters import check
        rules = model.calibrate(self.engine.draws, 0.8)
        for ln in self.engine.recommend(Options(seed=5, lines=5)):
            if ln.relaxed_step == 0:
                v = check(ln.numbers, rules.__class__(**{**rules.__dict__, "carryover_range": (0, 6)}))
                self.assertTrue(v.ok, (ln.numbers, v.violations))

    def test_stats_payload(self):
        s = self.engine.stats_payload()
        self.assertEqual(s["draws_used"], 1239)
        self.assertEqual(len(s["frequency"]), 45)
        self.assertEqual(sum(f["count"] for f in s["frequency"]), 1239 * 6)

    def test_grade_payload_screenshot_combos(self):
        p = self.engine.grade_payload([(11, 13, 22, 32, 36, 45), (2, 13, 20, 33, 36, 42)], 1239)
        self.assertEqual([r["rank"] for r in p["results"]], [3, 5])

    def test_backtest_payload_small(self):
        p = self.engine.backtest_payload(Options(seed=1, lines=2, candidates=5), rounds=5, seed=1)
        self.assertEqual(p["rounds"], 5)
        self.assertEqual(p["tickets"], 10)
        self.assertEqual(len(p["rows"]), 5)


class WebTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(Engine.load(), "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return r.status, r.read()

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_index_and_meta(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"lotto", body)
        status, body = self._get("/api/meta")
        self.assertEqual(json.loads(body)["previous"]["no"], 1239)

    def test_recommend_and_grade(self):
        status, body = self._post("/api/recommend", {"seed": 3, "lines": 2})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["lines"]), 2)
        status, body = self._post("/api/grade", {"lines": [[11, 13, 22, 32, 36, 45]], "draw_no": 1239})
        self.assertEqual(body["results"][0]["rank"], 3)

    def test_bad_input_returns_400(self):
        status, body = self._post("/api/grade", {"lines": [[1, 1, 2, 3, 4, 5]]})
        self.assertEqual(status, 400)
        self.assertIn("error", body)
        status, _ = self._get("/api/stats")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
