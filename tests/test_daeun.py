"""대운. 방향·시작 나이·간지 순서는 만세력과 대조하면 맞다/틀리다를 말할 수 있다."""

import unittest
from datetime import date

from lottoracle import daeun, saju
from lottoracle.fortune import Profile, normalize_gender
from lottoracle.solartime import epoch_to_parts


def kst(epoch: float) -> str:
    y, mo, d, hh, mi, _ = epoch_to_parts(epoch + 9 * 3600)
    return f"{y}-{mo:02d}-{d:02d} {hh:02d}:{mi:02d}"


class Jeol(unittest.TestCase):
    """절(節)은 달을 가르는 열두 마디. 대운수를 재는 자다."""

    def test_열두_절만_나온다(self):
        """중기(춘분·곡우 ...)는 달을 가르지 않으므로 절로 잡히면 안 된다."""
        jeol = {"입춘", "경칩", "청명", "입하", "망종", "소서",
                "입추", "백로", "한로", "입동", "대설", "소한"}
        base = saju.four_pillars(2000, 1, 1, 12, 0).utc_epoch
        for k in range(400):
            name, _ = saju.next_jeol(base + k * 86400 * 3)
            self.assertIn(name, jeol, f"{k}번째")

    def test_다음_절이_앞에_지난_절이_뒤에_있다(self):
        for args in [(1990, 5, 21, 4, 30), (2000, 11, 25, 8, 30), (2026, 2, 4, 12, 0)]:
            e = saju.four_pillars(*args).utc_epoch
            _, nxt = saju.next_jeol(e)
            _, prv = saju.prev_jeol(e)
            self.assertGreater(nxt, e, str(args))
            self.assertLessEqual(prv, e, str(args))
            self.assertLess((nxt - prv) / 86400, 32, "절 간격은 30일 언저리다")
            self.assertGreater((nxt - prv) / 86400, 28, str(args))

    def test_알려진_절입_시각(self):
        """2000년 대설은 12월 7일, 2026년 입춘은 2월 4일이다."""
        e = saju.four_pillars(2000, 11, 25, 8, 30).utc_epoch
        name, when = saju.next_jeol(e)
        self.assertEqual(name, "대설")
        self.assertTrue(kst(when).startswith("2000-12-07"), kst(when))

        e = saju.four_pillars(2026, 2, 10, 12, 0).utc_epoch
        name, when = saju.prev_jeol(e)
        self.assertEqual(name, "입춘")
        self.assertTrue(kst(when).startswith("2026-02-04"), kst(when))

    def test_절입_직후에는_지난_절이_그날이다(self):
        """입춘 시각 바로 뒤에 태어나면 지난 절이 그 입춘이어야 한다."""
        lichun = saju.lichun_epoch(2026)
        name, when = saju.prev_jeol(lichun + 600)
        self.assertEqual(name, "입춘")
        self.assertLess(abs(when - lichun), 60, "같은 순간을 가리켜야 한다")


class Direction(unittest.TestCase):
    def test_양년_남자와_음년_여자가_순행(self):
        for stem in range(10):
            yang = not saju.STEM_YIN[stem]
            self.assertEqual(daeun.is_forward(stem, True), yang, f"{saju.STEMS[stem]} 남")
            self.assertEqual(daeun.is_forward(stem, False), not yang, f"{saju.STEMS[stem]} 여")

    def test_같은_사주도_성별로_방향이_갈린다(self):
        s = saju.four_pillars(2000, 11, 25, 8, 30)      # 년간 경(양)
        m = daeun.daeun(s.year, s.month, s.day.stem, s.utc_epoch, "남")
        f = daeun.daeun(s.year, s.month, s.day.stem, s.utc_epoch, "여")
        self.assertTrue(m["forward"])
        self.assertFalse(f["forward"])
        self.assertNotEqual(m["list"][0]["name"], f["list"][0]["name"])

    def test_성별을_모르면_세우지_않는다(self):
        s = saju.four_pillars(2000, 11, 25, 8, 30)
        for g in ("", "몰라", None):
            self.assertIsNone(daeun.daeun(s.year, s.month, s.day.stem, s.utc_epoch, g))


class Start(unittest.TestCase):
    def test_삼일이_일년이다(self):
        s = saju.four_pillars(2000, 11, 25, 8, 30)
        st = daeun.start_at(s.utc_epoch, forward=True)
        self.assertEqual(st["jeol"], "대설")
        self.assertAlmostEqual(st["years"], st["days"] / 3, places=2)
        self.assertEqual(st["number"], round(st["days"] / 3))

    def test_순행과_역행이_다른_절을_본다(self):
        s = saju.four_pillars(2000, 11, 25, 8, 30)
        fwd = daeun.start_at(s.utc_epoch, True)
        bwd = daeun.start_at(s.utc_epoch, False)
        self.assertEqual((fwd["jeol"], bwd["jeol"]), ("대설", "입동"))
        self.assertNotEqual(fwd["number"], bwd["number"])

    def test_대운수는_영에서_열_사이다(self):
        """절 간격이 30일 언저리라 30/3 = 10 을 넘을 수 없다."""
        for y in range(1950, 2027, 7):
            for mo in (1, 4, 7, 10):
                s = saju.four_pillars(y, mo, 15, 12, 0)
                for fwd in (True, False):
                    n = daeun.start_at(s.utc_epoch, fwd)["number"]
                    self.assertTrue(0 <= n <= 10, f"{y}-{mo} {fwd} -> {n}")


class Table(unittest.TestCase):
    def setUp(self):
        self.s = saju.four_pillars(2000, 11, 25, 8, 30)      # 경진 정해 정해 갑진

    def test_월주에서_한_칸씩_옮긴다(self):
        """월주가 정해다. 순행이면 무자·기축·경인 ..., 역행이면 병술·을유·갑신 ..."""
        fwd = daeun.pillars(self.s.month, True)
        bwd = daeun.pillars(self.s.month, False)
        self.assertEqual([p.name for p in fwd[:3]], ["무자", "기축", "경인"])
        self.assertEqual([p.name for p in bwd[:3]], ["병술", "을유", "갑신"])

    def test_한_칸이_십년이다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem, self.s.utc_epoch, "남")
        for a, b in zip(d["list"], d["list"][1:]):
            self.assertEqual(a["to"], b["from"])
            self.assertEqual(b["from"] - a["from"], 10)
        self.assertEqual(d["list"][0]["from"], d["start"]["number"])

    def test_지금_어느_칸인지_짚는다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem,
                        self.s.utc_epoch, "남", age=25.8)
        self.assertEqual(d["current"]["name"], "경인")     # 대운수 4 -> 24~34
        self.assertEqual(sum(1 for r in d["list"] if r["now"]), 1, "한 칸만 표시된다")

    def test_첫_대운_전이면_비워_둔다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem,
                        self.s.utc_epoch, "남", age=2.0)
        self.assertIsNone(d["current"])
        self.assertTrue(d["beforeFirst"])

    def test_표를_넘어가면_비워_둔다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem,
                        self.s.utc_epoch, "남", age=95.0)
        self.assertIsNone(d["current"])
        self.assertFalse(d["beforeFirst"])

    def test_나이를_모르면_지금이_없다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem, self.s.utc_epoch, "남")
        self.assertIsNone(d["current"])
        self.assertFalse(any(r["now"] for r in d["list"]))

    def test_대운마다_십신이_붙는다(self):
        d = daeun.daeun(self.s.year, self.s.month, self.s.day.stem, self.s.utc_epoch, "남")
        first = d["list"][0]
        self.assertEqual(first["name"], "무자")
        self.assertEqual(first["stemGod"], "상관")     # 정화 일간에서 본 무토
        self.assertEqual(first["branchGod"], "편관")   # 자수의 본기 계수


class GzIndex(unittest.TestCase):
    def test_육십갑자를_한_바퀴_되짚는다(self):
        for i in range(60):
            self.assertEqual(daeun.gz_index(saju.Pillar(i % 10, i % 12)), i)


class ProfileGender(unittest.TestCase):
    def test_여러_표기를_받아들인다(self):
        for text in ("남", "남자", "male", "M"):
            self.assertEqual(normalize_gender(text), "남", text)
        for text in ("여", "여자", "female", "f"):
            self.assertEqual(normalize_gender(text), "여", text)

    def test_모르는_값은_빈_문자열(self):
        for text in ("", None, "몰라", "기타"):
            self.assertEqual(normalize_gender(text), "")

    def test_프로필에_실려_대운까지_간다(self):
        p = Profile(birth_date="2000-11-25", birth_branch="진", gender="남")
        r = saju.from_profile(p, date(2026, 9, 8))
        self.assertIsNotNone(r["daeun"])
        self.assertEqual(r["daeun"]["current"]["name"], "경인")

    def test_성별이_없어도_팔자는_그대로다(self):
        """성별은 대운 방향에만 쓴다. 여덟 글자와 십신이 흔들리면 안 된다."""
        a = saju.from_profile(Profile(birth_date="2000-11-25", birth_branch="진"),
                              date(2026, 9, 8))
        b = saju.from_profile(Profile(birth_date="2000-11-25", birth_branch="진", gender="남"),
                              date(2026, 9, 8))
        self.assertEqual(a["eightChars"], b["eightChars"])
        self.assertEqual(a["reading"], b["reading"])
        self.assertIsNone(a["daeun"])
        self.assertIsNotNone(b["daeun"])


if __name__ == "__main__":
    unittest.main()
