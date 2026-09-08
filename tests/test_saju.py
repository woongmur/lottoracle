"""사주팔자. 만세력과 대조하면 맞다/틀리다를 말할 수 있는 계산이다."""

import unittest

from lottoracle import saju
from lottoracle.solartime import _days_from_civil, epoch_to_parts


class Pillars(unittest.TestCase):
    def test_육십갑자가_한_바퀴_돈다(self):
        names = [saju.Pillar(i % 10, i % 12).name for i in range(60)]
        self.assertEqual(len(set(names)), 60, "60갑자가 겹치면 안 된다")
        self.assertEqual(names[0], "갑자")
        self.assertEqual(names[59], "계해")

    def test_일주_기준일(self):
        """2000-01-01 은 무오일이다. sxtwl 로 확인한 값."""
        epoch = _days_from_civil(2000, 1, 1) * 86400.0 + 12 * 3600
        self.assertEqual(saju.day_pillar(epoch).name, "무오")

    def test_일주는_하루마다_하나씩_넘어간다(self):
        base = _days_from_civil(2000, 1, 1) * 86400.0 + 12 * 3600
        for k in range(1, 200):
            a = saju.day_pillar(base + (k - 1) * 86400)
            b = saju.day_pillar(base + k * 86400)
            self.assertEqual((a.stem + 1) % 10, b.stem, f"{k}일째 천간")
            self.assertEqual((a.branch + 1) % 12, b.branch, f"{k}일째 지지")

    def test_시지_경계(self):
        """23~01시가 자시, 01~03시가 축시."""
        self.assertEqual(saju.hour_branch_of(23), 0)
        self.assertEqual(saju.hour_branch_of(0), 0)
        self.assertEqual(saju.hour_branch_of(1), 1)
        self.assertEqual(saju.hour_branch_of(2), 1)
        self.assertEqual(saju.hour_branch_of(12), 6)   # 오시

    def test_오호둔_월간(self):
        """갑기년 인월은 병인, 을경년은 무인, 병신년은 경인, 정임년은 임인, 무계년은 갑인."""
        want = {0: "병인", 5: "병인", 1: "무인", 6: "무인", 2: "경인",
                7: "경인", 3: "임인", 8: "임인", 4: "갑인", 9: "갑인"}
        for year_stem, name in want.items():
            first = (year_stem % 5) * 2 + 2
            self.assertEqual(saju.Pillar(first % 10, 2).name, name, f"년간 {year_stem}")

    def test_오자둔_시간(self):
        """갑기일 자시는 갑자, 을경일은 병자, 병신일은 무자, 정임일은 경자, 무계일은 임자."""
        want = {0: "갑자", 5: "갑자", 1: "병자", 6: "병자", 2: "무자",
                7: "무자", 3: "경자", 8: "경자", 4: "임자", 9: "임자"}
        for day_stem, name in want.items():
            first = (day_stem % 5) * 2
            self.assertEqual(saju.Pillar(first % 10, 0).name, name, f"일간 {day_stem}")


class YearBoundary(unittest.TestCase):
    def test_입춘_앞뒤로_년주가_갈린다(self):
        """설날이 아니라 입춘이 기준이다. 이 프로젝트의 띠 계산과 다른 지점."""
        before = saju.four_pillars(1998, 2, 1, 12, 0)
        after = saju.four_pillars(1998, 2, 10, 12, 0)
        self.assertEqual(before.year.name, "정축")     # 아직 1997년
        self.assertEqual(after.year.name, "무인")      # 1998년

    def test_띠와_년주가_어긋나는_구간(self):
        """1990-02-01 은 설날(1/27) 뒤라 말띠지만, 입춘(2/4) 앞이라 사주로는 뱀 해다."""
        from lottoracle.folklore import zodiac_of_birth
        self.assertEqual(zodiac_of_birth("1990-02-01"), "말")
        self.assertEqual(saju.four_pillars(1990, 2, 1, 12, 0).year.animal, "뱀")

    def test_입춘_시각이_2월_초에_있다(self):
        for year in (1900, 1990, 2026, 2050):
            y, mo, d, *_ = epoch_to_parts(saju.lichun_epoch(year) + 9 * 3600)
            self.assertEqual((y, mo), (year, 2), f"{year} 입춘")
            self.assertIn(d, (3, 4, 5), f"{year} 입춘 {d}일")


class Correction(unittest.TestCase):
    def test_보정이_팔자에_반영된다(self):
        """1987 여름은 서머타임 + 경도로 92분 당겨진다. 시주가 바뀔 수 있는 크기."""
        s = saju.four_pillars(1987, 7, 1, 12, 0)
        self.assertAlmostEqual(s.correction_minutes, -92.1, delta=0.2)
        self.assertEqual(epoch_to_parts(s.solar_epoch)[3:5], (10, 27))

    def test_야자시_표시(self):
        """야자시 판정도 보정된 태양시로 한다. 벽시계 23:30 은 태양시로 22:57 이라 아니다."""
        self.assertFalse(saju.four_pillars(2026, 1, 5, 23, 30).late_night)
        self.assertTrue(saju.four_pillars(2026, 1, 5, 23, 40).late_night)

    def test_보정이_태양시_날짜를_되돌리기도_한다(self):
        """벽시계 00:10 은 서울 태양시로 전날 23:37 이다. 일주가 전날 것이 된다."""
        s = saju.four_pillars(2026, 1, 5, 0, 10)
        y, mo, d, hh, mi, _ = epoch_to_parts(s.solar_epoch)
        self.assertEqual((y, mo, d), (2026, 1, 4))
        self.assertEqual((hh, mi), (23, 37))
        self.assertEqual(s.day.name, saju.four_pillars(2026, 1, 4, 12, 0).day.name)

    def test_시주_경계까지_남은_분(self):
        """시지 경계는 홀수 시각에 있다. 홀수 시면 120-분, 짝수 시면 60-분."""
        for hh in range(0, 24):
            s = saju.four_pillars(2026, 6, 1, hh, 0)
            _, _, _, sh, sm, _ = epoch_to_parts(s.solar_epoch)
            want = (60 - sm) if sh % 2 == 0 else (120 - sm)
            self.assertEqual(s.hour_edge_minutes, want, f"{hh}시 (태양시 {sh}:{sm:02d})")
            self.assertGreater(s.hour_edge_minutes, 0)
            self.assertLessEqual(s.hour_edge_minutes, 120)

    def test_경계값이_말이_되는가(self):
        """태양시 07:57 이면 다음 경계(09:00)까지 63분이다. 3분이 아니다.

        경계 계산을 뒤집어 놔서 '시주가 바뀌기 3분 전' 이라는 엉뚱한 안내가 나갔었다.
        """
        s = saju.four_pillars(1990, 2, 1, 8, 30)      # 보정 -32분 -> 태양시 07:57
        self.assertEqual(epoch_to_parts(s.solar_epoch)[3:5], (7, 57))
        self.assertEqual(s.hour_edge_minutes, 63)


class Elements(unittest.TestCase):
    def test_여덟_글자를_센다(self):
        s = saju.four_pillars(1990, 5, 21, 4, 30)
        counts = saju.elements_count(s.pillars)
        self.assertEqual(sum(counts.values()), 8, "천간 4 + 지지 4")
        self.assertEqual(set(counts), set(saju.ELEMENTS))

    def test_어떤_생일이든_합이_8이다(self):
        for args in [(1900, 1, 1, 0, 0), (1954, 6, 15, 13, 20), (2026, 12, 31, 23, 59)]:
            s = saju.four_pillars(*args)
            self.assertEqual(sum(saju.elements_count(s.pillars).values()), 8, str(args))


class Payload(unittest.TestCase):
    def test_화면에_넘길_값이_다_있다(self):
        d = saju.four_pillars(1990, 5, 21, 4, 30).to_dict()
        for key in ("year", "month", "day", "hour", "eightChars", "hanja",
                    "elements", "sign", "solarTime", "correctionMinutes",
                    "lateNight", "hourEdgeMinutes"):
            self.assertIn(key, d)
        self.assertEqual(len(d["eightChars"]), 8)
        self.assertEqual(d["eightChars"], "경오신사병술경인")


if __name__ == "__main__":
    unittest.main()
