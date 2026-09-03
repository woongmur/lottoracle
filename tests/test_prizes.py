"""1~5등 당첨 현황 — 파싱 · 저장 · 실제 당첨금 채점 · 회차 상세.

네트워크를 타지 않는다. 지연 수집 경로는 fetch_draw 를 대역으로 바꿔 검사한다.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest import mock

from lottoracle import data
from lottoracle.data import Draw, Prize
from lottoracle.engine import Engine

# 1239회 실제 응답을 줄인 것
PAYLOAD = {
    "data": {"list": [{
        "ltEpsd": 1239, "tm1WnNo": 11, "tm2WnNo": 13, "tm3WnNo": 22,
        "tm4WnNo": 32, "tm5WnNo": 33, "tm6WnNo": 36, "bnsWnNo": 8,
        "ltRflYmd": "20260829",
        "rnk1WnNope": 13, "rnk1WnAmt": 2214789375, "rnk1SumWnAmt": 28792261875,
        "rnk2WnNope": 71, "rnk2WnAmt": 67587470, "rnk2SumWnAmt": 4798710370,
        "rnk3WnNope": 3081, "rnk3WnAmt": 1557518, "rnk3SumWnAmt": 4798712958,
        "rnk4WnNope": 152825, "rnk4WnAmt": 50000, "rnk4SumWnAmt": 7641250000,
        "rnk5WnNope": 2570542, "rnk5WnAmt": 5000, "rnk5SumWnAmt": 12852710000,
        "rlvtEpsdSumNtslAmt": 58883645203,
    }]}
}


class ParsePrizeTest(unittest.TestCase):
    def test_parses_all_five_ranks(self):
        d = data._parse_payload(PAYLOAD)
        self.assertTrue(d.has_prizes)
        self.assertEqual([p.rank for p in d.prizes], [1, 2, 3, 4, 5])
        self.assertEqual(d.prize_of(1), Prize(1, 13, 2214789375, 28792261875))
        self.assertEqual(d.prize_of(5).amount, 5000)
        self.assertEqual(d.total_sales, 58883645203)

    def test_first_fields_follow_prizes(self):
        d = data._parse_payload(PAYLOAD)
        self.assertEqual(d.first_winners, 13)
        self.assertEqual(d.first_prize, 2214789375)

    def test_totals_are_consistent(self):
        for p in data._parse_payload(PAYLOAD).prizes:
            self.assertEqual(p.winners * p.amount, p.total, f"{p.rank}등")

    def test_round_trip(self):
        d = data._parse_payload(PAYLOAD)
        self.assertEqual(Draw.from_dict(d.to_dict()), d)

    def test_old_cache_without_prizes(self):
        old = Draw.from_dict({"no": 1, "numbers": [1, 2, 3, 4, 5, 6], "bonus": 7,
                              "first_winners": 0, "first_prize": 0})
        self.assertFalse(old.has_prizes)
        self.assertIsNone(old.prize_of(1))
        self.assertEqual(old.first_winners, 0)
        self.assertNotIn("prizes", old.to_dict())


class GradeWithRealPrizeTest(unittest.TestCase):
    DRAW = data._parse_payload(PAYLOAD)

    def _engine(self, draw):
        return Engine(draws=[draw], path=tempfile.mktemp(suffix=".json"))

    def test_uses_actual_prize_amounts(self):
        eng = self._engine(self.DRAW)
        r = eng.grade_payload([[11, 13, 22, 32, 33, 36], [11, 13, 22, 32, 33, 45]], 1239)
        self.assertTrue(r["actual_prize"])
        self.assertEqual(r["results"][0]["prize"], 2214789375)   # 1등 실제 금액
        self.assertEqual(r["results"][1]["prize"], 1557518)      # 3등 실제 금액
        self.assertEqual(r["total_prize"], 2214789375 + 1557518)

    def test_second_rank_uses_bonus_amount(self):
        eng = self._engine(self.DRAW)
        r = eng.grade_payload([[11, 13, 22, 32, 33, 8]], 1239)   # 5개 + 보너스
        self.assertEqual(r["results"][0]["rank"], 2)
        self.assertEqual(r["results"][0]["prize"], 67587470)

    def test_falls_back_to_average_without_prizes(self):
        bare = Draw(no=1239, numbers=self.DRAW.numbers, bonus=self.DRAW.bonus)
        eng = self._engine(bare)
        with mock.patch("lottoracle.engine.data.fetch_draw", side_effect=OSError("offline")):
            r = eng.grade_payload([[11, 13, 22, 32, 33, 36]], 1239)
        self.assertFalse(r["actual_prize"])
        self.assertEqual(r["results"][0]["prize"], 2_000_000_000)   # backtest 평균치

    def test_qr_payload_uses_actual_prize(self):
        eng = self._engine(self.DRAW)
        r = eng.qr_payload("1239m111322323336")
        self.assertTrue(r["actual_prize"])
        self.assertEqual(r["total_prize"], 2214789375)


class EnsurePrizesTest(unittest.TestCase):
    def setUp(self):
        self.bare = Draw(no=1239, numbers=(11, 13, 22, 32, 33, 36), bonus=8)
        self.full = data._parse_payload(PAYLOAD)
        self.path = tempfile.mktemp(suffix=".json")

    def test_fetches_once_then_caches(self):
        eng = Engine(draws=[self.bare], path=self.path)
        with mock.patch("lottoracle.engine.data.fetch_draw", return_value=self.full) as m:
            first = eng.ensure_prizes(1239)
            second = eng.ensure_prizes(1239)     # 이미 채워졌으니 다시 부르지 않는다
        m.assert_called_once()
        self.assertTrue(first.has_prizes)
        self.assertTrue(second.has_prizes)
        with open(self.path, encoding="utf-8") as fp:
            self.assertIn("prizes", json.load(fp)[0])

    def test_network_failure_keeps_existing(self):
        eng = Engine(draws=[self.bare], path=self.path)
        with mock.patch("lottoracle.engine.data.fetch_draw", side_effect=urllib.error.URLError("down")):
            got = eng.ensure_prizes(1239)
        self.assertFalse(got.has_prizes)

    def test_unknown_draw_returns_none(self):
        eng = Engine(draws=[self.bare], path=self.path)
        with mock.patch("lottoracle.engine.data.fetch_draw", return_value=None):
            self.assertIsNone(eng.ensure_prizes(9999))

    def test_detail_payload(self):
        eng = Engine(draws=[self.full], path=self.path)
        d = eng.draw_detail_payload(1239)
        self.assertTrue(d["has_prizes"])
        self.assertEqual(len(d["draw"]["prizes"]), 5)
        self.assertEqual(d["draw"]["total_sales"], 58883645203)


class DrawApiTest(unittest.TestCase):
    """GET /api/draw 가 등수별 현황을 돌려준다."""

    @classmethod
    def setUpClass(cls):
        import threading
        from lottoracle.web import make_server
        cls.engine = Engine(draws=[data._parse_payload(PAYLOAD)], path=tempfile.mktemp(suffix=".json"))
        cls.server = make_server(cls.engine, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _get(self, path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_draw_detail(self):
        status, body = self._get("/api/draw?no=1239")
        self.assertEqual(status, 200)
        self.assertTrue(body["has_prizes"])
        self.assertEqual(body["draw"]["prizes"][0]["amount"], 2214789375)

    def test_draws_list_carries_prizes(self):
        status, rows = self._get("/api/draws?limit=1")
        self.assertEqual(status, 200)
        self.assertTrue(rows[0]["has_prizes"])
        self.assertEqual(len(rows[0]["prizes"]), 5)

    def test_missing_draw_is_400(self):
        with mock.patch("lottoracle.engine.data.fetch_draw", return_value=None):
            status, body = self._get("/api/draw?no=9999")
        self.assertEqual(status, 400)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
