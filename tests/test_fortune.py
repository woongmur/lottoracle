"""운세 · 프로필 · 저장소 · 새 웹 API 테스트. 운세는 재미이므로 여기서 검사하는 건 규칙(결정론·금칙어)이다."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from unittest import mock

from lottoracle import fortune
from lottoracle.data import Draw
from lottoracle.engine import Engine
from lottoracle.fortune import Profile, daily_fortune, zodiac_table
from lottoracle.store import UserStore
from lottoracle.web import make_server


class ProfileTest(unittest.TestCase):
    def test_normalizes_and_derives(self):
        p = Profile(name="  홍길동  ", birth_date="1990.5.21", birth_hour="4")
        self.assertEqual(p.name, "홍길동")
        self.assertEqual(p.birth_date, "1990-05-21")
        self.assertEqual(p.birth_hour, 4)
        self.assertEqual(p.zodiac, "말")
        self.assertEqual(p.hour_animal, "호랑이")
        self.assertIn(7, p.personal_numbers())    # 말띠수
        self.assertIn(21, p.personal_numbers())   # 생일수(일)
        self.assertIn(3, p.personal_numbers())    # 인시 → 호랑이띠수

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            Profile(birth_date="1990-13-40")
        with self.assertRaises(ValueError):
            Profile(birth_date="어제")
        with self.assertRaises(ValueError):
            Profile(birth_date="1990-05-21", birth_hour=25)

    def test_round_trip(self):
        p = Profile(name="a", birth_date="2000-01-01", birth_hour=None)
        self.assertEqual(Profile.from_dict(p.to_dict()), p)
        self.assertTrue(Profile().is_empty)

    def test_branch_of_time_uses_30min_correction(self):
        b = fortune.branch_of_time
        self.assertEqual(b(23, 30), "자")
        self.assertEqual(b(0, 0), "자")
        self.assertEqual(b(1, 29), "자")
        self.assertEqual(b(1, 30), "축")
        self.assertEqual(b(7, 30), "진")
        self.assertEqual(b(9, 29), "진")
        self.assertEqual(b(9, 30), "사")
        self.assertEqual(b(23, 0), "해")
        self.assertEqual(b(None), "")
        self.assertEqual(fortune.hour_branch(12), "오")
        # 표시 범위와 계산이 일치하는지: 각 구간 시작 시각이 그 지지로 떨어져야 한다
        for br, rng in fortune.BRANCH_RANGE.items():
            h, m = (int(x) for x in rng.split("~")[0].split(":"))
            self.assertEqual(b(h, m), br, rng)

    def test_branch_input_forms(self):
        self.assertEqual(Profile(birth_date="1990-05-21", birth_branch="진시").birth_branch, "진")
        self.assertEqual(Profile(birth_date="1990-05-21", birth_branch="용").hour_label, "진시(용)")
        self.assertEqual(Profile(birth_date="1990-05-21", birth_hour=4).birth_branch, "인")   # 구버전 profile.json 호환
        with self.assertRaises(ValueError):
            Profile(birth_date="1990-05-21", birth_branch="갑")
        self.assertEqual(len(fortune.branch_choices()), 12)
        self.assertIn("07:30~09:30", fortune.branch_choices()[4]["label"])


class FortuneTest(unittest.TestCase):
    P = Profile(name="홍길동", birth_date="1990-05-21", birth_hour=4)

    def test_deterministic_per_day(self):
        a = daily_fortune(self.P, date(2026, 9, 3))
        b = daily_fortune(self.P, date(2026, 9, 3))
        self.assertEqual(a, b)
        c = daily_fortune(self.P, date(2026, 9, 4))
        self.assertNotEqual((a.grade, a.sentence, a.numbers, a.keyword), (c.grade, c.sentence, c.numbers, c.keyword))

    def test_shape(self):
        for d in range(1, 60):
            f = daily_fortune(self.P, date(2026, 1, 1 + d % 28))
            self.assertIn(f.grade, range(1, 6))
            self.assertEqual(f.label, fortune.GRADE_LABELS[f.grade])
            self.assertEqual(len(f.numbers), 3)
            self.assertEqual(len(set(f.numbers)), 3)
            self.assertTrue(all(1 <= n <= 45 for n in f.numbers))
            self.assertEqual(tuple(sorted(f.numbers)), f.numbers)

    def test_no_forbidden_words_anywhere(self):
        for text in fortune.all_sentences():
            self.assertEqual(fortune.forbidden_hits(text), [], text)
        # 실제 생성 결과도 한 번 더
        for d in range(1, 29):
            f = daily_fortune(self.P, date(2026, 3, d))
            for text in (f.label, f.sentence, f.tip, f.keyword):
                self.assertEqual(fortune.forbidden_hits(text), [], text)

    def test_low_grade_points_to_tomorrow_or_elsewhere(self):
        """나쁜 날 문장은 겁주지 않고 내일·다른 곳으로 이어 준다."""
        for s in fortune.SENTENCES[1] + fortune.SENTENCES[2]:
            self.assertTrue(any(w in s for w in ("내일", "오늘", "천천히", "쉬어")), s)
            self.assertNotIn("없", s.split("입니다")[0][:6])  # '운이 없는' 류 금지

    def test_works_without_profile(self):
        f = daily_fortune(None, date(2026, 9, 3))
        self.assertEqual(len(f.numbers), 3)
        self.assertEqual(f.zodiac, "")

    def test_zodiac_table(self):
        table = zodiac_table(date(2026, 9, 3))
        self.assertEqual([z["zodiac"] for z in table],
                         ["쥐", "소", "호랑이", "토끼", "용", "뱀", "말", "양", "원숭이", "닭", "개", "돼지"])
        for z in table:
            self.assertIn(z["grade"], range(1, 6))
            self.assertEqual(len(z["numbers"]), 2)
            self.assertEqual(fortune.forbidden_hits(z["short"]), [])

    def test_recommend_inputs(self):
        i = self.P.recommend_inputs(date(2026, 9, 3))
        self.assertEqual(i["birthday"], "1990-05-21")
        self.assertEqual(i["zodiac"], "말")
        self.assertEqual(i["lucky"], list(daily_fortune(self.P, date(2026, 9, 3)).numbers))


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = UserStore(os.path.join(self.tmp.name, "data"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_profile_roundtrip_and_clear(self):
        self.assertTrue(self.store.load_profile().is_empty)
        self.store.save_profile(Profile(name="a", birth_date="1990-05-21"))
        self.assertEqual(self.store.load_profile().zodiac, "말")
        self.store.clear_profile()
        self.assertTrue(self.store.load_profile().is_empty)

    def test_picks(self):
        rec = self.store.add_pick([[1, 2, 3, 4, 5, 6], [45, 44, 43, 42, 41, 40]], 1240, "메모")
        self.assertEqual(rec["lines"][1], [40, 41, 42, 43, 44, 45])
        self.assertEqual(len(self.store.list_picks()), 1)
        with self.assertRaises(ValueError):
            self.store.add_pick([[1, 1, 2, 3, 4, 5]], 1240)
        with self.assertRaises(ValueError):
            self.store.add_pick([], 1240)
        self.assertTrue(self.store.delete_pick(rec["id"]))
        self.assertFalse(self.store.delete_pick(rec["id"]))
        self.assertEqual(self.store.list_picks(), [])

    def test_settings_whitelist(self):
        s = self.store.save_settings({"kakao_js_key": "abc", "evil": 1, "auto_refresh": False})
        self.assertEqual(s, {"kakao_js_key": "abc", "auto_refresh": False})
        s = self.store.save_settings({"kakao_js_key": ""})
        self.assertNotIn("kakao_js_key", s)

    def test_corrupt_file_is_ignored(self):
        os.makedirs(self.store.dir, exist_ok=True)
        with open(os.path.join(self.store.dir, "picks.json"), "w") as fp:
            fp.write("{not json")
        self.assertEqual(self.store.list_picks(), [])


class EnginePicksTest(unittest.TestCase):
    def test_auto_grading(self):
        with tempfile.TemporaryDirectory() as tmp:
            eng = Engine.load()
            eng.store = UserStore(os.path.join(tmp, "data"))
            eng.store.add_pick([[11, 13, 22, 32, 36, 45]], 1239)   # 1239회 3등
            eng.store.add_pick([[1, 2, 3, 4, 5, 6]], 1240)          # 미추첨
            picks = eng.picks_payload()
            self.assertEqual(picks[0]["target_draw"], 1240)
            self.assertIsNone(picks[0]["results"])
            self.assertEqual(picks[1]["best_rank"], 3)
            self.assertEqual(picks[1]["results"][0]["hit"], [11, 13, 22, 32, 36])

    def test_refresh_uses_cache_path(self):
        eng = Engine.load()
        eng.store = UserStore(tempfile.mkdtemp())
        fake = list(eng.draws) + [Draw(no=1240, numbers=(1, 2, 3, 4, 5, 6), bonus=7, draw_date="2026-09-05")]
        with mock.patch("lottoracle.engine.data.update_cache", return_value=fake) as m:
            r = eng.refresh()
        m.assert_called_once()
        self.assertEqual((r["before"], r["after"], r["added"]), (1239, 1240, 1))
        self.assertEqual(eng.previous.no, 1240)


class WebNewApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        eng = Engine.load()
        eng.store = UserStore(os.path.join(cls.tmp.name, "data"))
        cls.engine = eng
        cls.server = make_server(eng, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def _req(self, path, payload=None, headers=None):
        h = {"Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode() if payload is not None else None,
            headers=h,
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_meta_has_new_fields(self):
        status, m = self._req("/api/meta")
        self.assertEqual(status, 200)
        for key in ("version", "has_profile", "tagline", "disclaimer", "kakao_js_key", "online_refresh", "branch_choices"):
            self.assertIn(key, m)
        self.assertFalse(m["has_profile"])

    def test_origin_check(self):
        host = f"127.0.0.1:{self.port}"
        status, body = self._req("/api/grade", {"lines": [[1, 2, 3, 4, 5, 6]]}, {"Origin": "https://evil.example"})
        self.assertEqual(status, 403)
        status, body = self._req("/api/grade", {"lines": [[1, 2, 3, 4, 5, 6]]}, {"Origin": "null"})
        self.assertEqual(status, 403)
        status, body = self._req("/api/grade", {"lines": [[1, 2, 3, 4, 5, 6]]}, {"Origin": f"http://{host}"})
        self.assertEqual(status, 200)

    def test_profile_fortune_picks_flow(self):
        status, r = self._req("/api/fortune")
        self.assertEqual(status, 200)
        self.assertFalse(r["has_profile"])
        self.assertEqual(len(r["zodiac_table"]), 12)

        status, r = self._req("/api/profile", {"name": "홍길동", "birth_date": "1990-05-21", "birth_branch": "인"})
        self.assertEqual(status, 200)
        self.assertTrue(r["has_profile"])
        self.assertEqual(r["fortune"]["zodiac"], "말")
        self.assertEqual(r["profile"]["hour_label"], "인시(호랑이)")
        self.assertEqual(r["recommend_inputs"]["birthday"], "1990-05-21")
        self.assertEqual(len(r["recommend_inputs"]["lucky"]), 3)

        status, r = self._req("/api/profile", {"birth_date": ""})
        self.assertEqual(status, 400)

        status, r = self._req("/api/picks", {"lines": [[11, 13, 22, 32, 36, 45]], "target_draw": 1239})
        self.assertEqual(status, 200)
        self.assertEqual(r["picks"][0]["best_rank"], 3)
        pid = r["saved"]["id"]
        status, r = self._req("/api/picks", {"lines": [[1, 2, 3, 4, 5, 6]]})  # target 생략 → 다음 회차
        self.assertEqual(r["saved"]["target_draw"], 1240)
        status, r = self._req("/api/picks/delete", {"id": pid})
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["picks"]), 1)

        status, r = self._req("/api/settings", {"settings": {"kakao_js_key": "k", "auto_refresh": False}})
        self.assertEqual(r["settings"]["kakao_js_key"], "k")
        status, m = self._req("/api/meta")
        self.assertEqual(m["kakao_js_key"], "k")
        self.assertFalse(m["auto_refresh"])

        status, r = self._req("/api/profile/delete", {})
        self.assertTrue(r["ok"])
        status, m = self._req("/api/meta")
        self.assertFalse(m["has_profile"])

    def test_refresh_network_failure_is_502(self):
        with mock.patch("lottoracle.engine.data.update_cache", side_effect=OSError("boom")):
            status, r = self._req("/api/refresh", {})
        self.assertEqual(status, 502)
        self.assertIn("동행복권", r["error"])

    def test_refresh_success(self):
        fake = list(self.engine.draws)
        with mock.patch("lottoracle.engine.data.update_cache", return_value=fake):
            status, r = self._req("/api/refresh", {})
        self.assertEqual(status, 200)
        self.assertEqual(r["added"], 0)


if __name__ == "__main__":
    unittest.main()
