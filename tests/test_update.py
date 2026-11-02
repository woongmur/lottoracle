"""추첨일 밤 갱신 — 번호가 먼저 나오고 당첨금·배출점이 늦게 붙는 경우.

갱신은 토요일 밤에 여러 번 돈다. 첫 실행이 '집계 전' 값을 저장하고 다음 실행들이
그걸 다시 받지 않으면, 그 회차는 영영 0원·배출점 없음으로 남는다.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

from lottoracle import data
from lottoracle.data import Draw, Prize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import fetch_stores  # noqa: E402

NUMS = (16, 18, 27, 36, 38, 42)


def draw(no: int, settled: bool) -> Draw:
    w = (15, 91, 3265, 167745, 2723467) if settled else (15, 0, 0, 0, 0)
    a = (1933658450, 53122485, 1480597, 50000, 5000) if settled else (1933658450, 0, 0, 0, 0)
    return Draw(no=no, numbers=NUMS, bonus=22, draw_date="2026-10-31",
                prizes=tuple(Prize(r, w[r - 1], a[r - 1]) for r in range(1, 6)))


class PrizesSettled(unittest.TestCase):
    def test_2등부터_0이면_집계_전(self):
        self.assertTrue(data.prizes_settled(draw(1248, True)))
        self.assertFalse(data.prizes_settled(draw(1248, False)))
        self.assertFalse(data.prizes_settled(Draw(no=1, numbers=NUMS, bonus=22)))

    def test_1등_0명은_정상(self):
        d = draw(1248, True)
        d = Draw(no=d.no, numbers=d.numbers, bonus=d.bonus, draw_date=d.draw_date,
                 prizes=(Prize(1, 0, 0),) + d.prizes[1:])
        self.assertTrue(data.prizes_settled(d))


class UpdateCache(unittest.TestCase):
    def run_update(self, cached, latest, by_no):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "draws.json")
            data.save_draws(cached, path)
            with mock.patch.object(data, "fetch_latest", return_value=latest), \
                 mock.patch.object(data, "fetch_draw", side_effect=lambda no, timeout=10.0: by_no.get(no)):
                return data.update_cache(path)

    def test_집계_전이던_최신_회차를_다시_받는다(self):
        got = self.run_update([draw(1247, True), draw(1248, False)], draw(1248, True),
                              {1248: draw(1248, True)})
        self.assertTrue(data.prizes_settled(max(got, key=lambda d: d.no)))

    def test_다시_받아도_아직이면_그대로(self):
        got = self.run_update([draw(1248, False)], draw(1248, False), {1248: draw(1248, False)})
        self.assertEqual(len(got), 1)
        self.assertFalse(data.prizes_settled(got[0]))

    def test_집계가_끝난_회차는_다시_부르지_않는다(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "draws.json")
            data.save_draws([draw(1248, True)], path)
            with mock.patch.object(data, "fetch_latest", return_value=draw(1248, True)), \
                 mock.patch.object(data, "fetch_draw") as fd:
                data.update_cache(path)
            fd.assert_not_called()


class StoresPending(unittest.TestCase):
    def test_2등_배출점이_비면_받은_것으로_적지_않는다(self):
        db = {"stores": {}, "draws": []}
        saved = []
        with mock.patch.object(fetch_stores.data, "load_draws", return_value=[draw(1248, True)]), \
             mock.patch.object(fetch_stores, "load_existing", return_value=db), \
             mock.patch.object(fetch_stores, "fetch", return_value=[]), \
             mock.patch.object(fetch_stores, "save", side_effect=lambda d: saved.append(list(d["draws"]))), \
             mock.patch("sys.argv", ["fetch_stores.py", "--recent", "1"]):
            self.assertEqual(fetch_stores.main(), 0)
        self.assertNotIn(1248, db["draws"])

    def test_발표되면_받은_것으로_적는다(self):
        db = {"stores": {}, "draws": []}
        row = {"ltShpId": "1", "shpNm": "가게", "shpAddr": "서울 종로구", "region": "서울"}
        with mock.patch.object(fetch_stores.data, "load_draws", return_value=[draw(1248, True)]), \
             mock.patch.object(fetch_stores, "load_existing", return_value=db), \
             mock.patch.object(fetch_stores, "fetch", return_value=[row]), \
             mock.patch.object(fetch_stores, "save"), \
             mock.patch("sys.argv", ["fetch_stores.py", "--recent", "1"]):
            fetch_stores.main()
        self.assertIn(1248, db["draws"])


if __name__ == "__main__":
    unittest.main()
