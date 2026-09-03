"""동행복권 용지 QR 파싱 테스트. (웹 GUI 는 번호 직접 입력을 쓰고, 이 파서는 앱 연동용이다.)"""

from __future__ import annotations

import unittest

from lottoracle import qr
from lottoracle.engine import Engine

URL = "https://m.dhlottery.co.kr/qr.do?method=winQr&v=1239m111322323336q010203040506"


class ParseTest(unittest.TestCase):
    def test_url_form(self):
        t = qr.parse(URL)
        self.assertEqual(t.draw_no, 1239)
        self.assertEqual(t.lines, ((11, 13, 22, 32, 33, 36), (1, 2, 3, 4, 5, 6)))
        self.assertEqual(t.kinds, ("수동", "자동"))

    def test_bare_value_and_leading_zero_round(self):
        self.assertEqual(qr.parse("0843m192130333442").draw_no, 843)
        self.assertEqual(qr.parse("v=1239q111322323336").lines[0], (11, 13, 22, 32, 33, 36))

    def test_numbers_are_sorted(self):
        self.assertEqual(qr.parse("1239m363332221311").lines[0], (11, 13, 22, 32, 33, 36))

    def test_five_games_ok_six_rejected(self):
        game = "m010203040506"
        self.assertEqual(len(qr.parse("1239" + game * 5).lines), 5)
        with self.assertRaises(ValueError):
            qr.parse("1239" + game * 6)

    def test_rejects_bad_input(self):
        for bad, why in [
            ("", "빈 문자열"),
            ("   ", "공백"),
            ("https://example.com/?v=1239m010203040506", "다른 사이트"),
            ("https://m.dhlottery.co.kr/qr.do?method=winQr", "v 없음"),
            ("1239", "게임 없음"),
            ("1239m111322323346", "46번"),
            ("1239m000102030405", "0번"),
            ("1239m111111111111", "중복"),
            ("1239m01020304050", "자릿수 부족"),
            ("1239m010203040506ZZ", "쓰레기 문자"),
        ]:
            with self.assertRaises(ValueError, msg=why):
                qr.parse(bad)

    def test_unknown_marker_is_kept_as_unclear(self):
        self.assertEqual(qr.parse("1239x010203040506").kinds, ("확인불가",))

    def test_to_dict(self):
        self.assertEqual(
            qr.parse("1239m111322323336").to_dict(),
            {"draw_no": 1239, "lines": [[11, 13, 22, 32, 33, 36]], "kinds": ["수동"]},
        )


class EngineQrTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Engine.load()

    def test_graded_ticket(self):
        r = self.engine.qr_payload(URL)
        self.assertEqual(r["status"], "graded")
        self.assertEqual(r["draw"]["no"], 1239)
        self.assertEqual(r["best_rank"], 1)                    # 1239회 당첨번호 그대로
        self.assertEqual(r["results"][0]["label"], "1등")
        self.assertEqual(r["results"][1]["rank"], 0)
        self.assertEqual(len(r["colors"][0]), 6)

    def test_future_draw_is_pending(self):
        r = self.engine.qr_payload("1250m010203040506")
        self.assertEqual(r["status"], "pending")
        self.assertEqual(r["latest_draw"], 1239)
        self.assertNotIn("results", r)

    def test_missing_old_draw(self):
        engine = Engine(draws=[d for d in self.engine.draws if d.no >= 100])
        self.assertEqual(engine.qr_payload("50m010203040506")["status"], "missing")


if __name__ == "__main__":
    unittest.main()
