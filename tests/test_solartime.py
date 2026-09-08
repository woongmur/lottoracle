"""시각 보정과 태양황경. 사주·별자리가 전부 이 위에 얹힌다."""

import random
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from lottoracle import solartime as st

KST = ZoneInfo("Asia/Seoul")


class TimeCorrection(unittest.TestCase):
    def test_벽시계를_UTC로_되돌린다(self):
        """IANA tz 를 그대로 읽는 zoneinfo 와 같아야 한다."""
        rng = random.Random(1)
        for _ in range(2000):
            y = rng.randint(1900, 2050)
            mo, d = rng.randint(1, 12), rng.randint(1, 28)
            hh, mi = rng.randint(0, 23), rng.randint(0, 59)
            ref = datetime(y, mo, d, hh, mi, tzinfo=KST).timestamp()
            self.assertAlmostEqual(st.wall_to_utc(y, mo, d, hh, mi), ref, delta=0.5,
                                   msg=f"{y}-{mo:02d}-{d:02d} {hh:02d}:{mi:02d}")

    def test_시기별_보정량(self):
        """표준 자오선이 바뀌면 보정량도 바뀐다. 여기가 이 모듈의 존재 이유다."""
        cases = [
            ((1905, 6, 1, 12, 0), 0.0),      # 서울 지방시 — 시계가 곧 태양시
            ((1910, 6, 1, 12, 0), -2.1),     # 동경 127.5도
            ((1930, 6, 1, 12, 0), -32.1),    # 동경 135도
            ((1958, 6, 1, 12, 0), -62.1),    # 127.5도 + 서머타임 1시간
            ((1987, 7, 1, 12, 0), -92.1),    # 135도 + 서머타임 1시간
            ((2026, 9, 7, 12, 0), -32.1),
        ]
        for args, want in cases:
            self.assertAlmostEqual(st.correction_minutes(*args), want, delta=0.15, msg=str(args))

    def test_서머타임을_빼먹지_않는다(self):
        """1987 여름은 UTC+10. 이걸 놓치면 한 시간이 통째로 밀린다."""
        self.assertEqual(st.utc_offset_at(st.wall_to_utc(1987, 7, 1, 12, 0)), 36000)
        self.assertEqual(st.utc_offset_at(st.wall_to_utc(1986, 7, 1, 12, 0)), 32400)

    def test_1954년_자오선_변경(self):
        """1954~61 은 동경 127.5도라 보정이 32분이 아니라 2분이다."""
        self.assertEqual(st.utc_offset_at(st.wall_to_utc(1953, 6, 1, 12, 0)), 32400)
        self.assertEqual(st.utc_offset_at(st.wall_to_utc(1955, 1, 1, 12, 0)), 30600)
        self.assertEqual(st.utc_offset_at(st.wall_to_utc(1962, 6, 1, 12, 0)), 32400)

    def test_전환에서_멀면_왕복한다(self):
        """전환에서 하루 이상 떨어진 시각은 벽시계 -> UTC -> 벽시계가 제자리로 온다."""
        from lottoracle.tzhistory import KST_TRANSITIONS
        for epoch, _ in KST_TRANSITIONS[1:]:
            for delta in (-86400 * 3, 86400 * 3):
                e = epoch + delta
                parts = st.epoch_to_parts(e + st.utc_offset_at(e))
                back = st.wall_to_utc(*parts[:5])
                self.assertAlmostEqual(back, e - parts[5], delta=1.0,
                                       msg=f"전환 {epoch} 에서 {delta}초")

    def test_겹치는_시각은_이른_쪽을_고른다(self):
        """서머타임이 끝나면 같은 벽시계 시각이 두 번 온다.

        1948-09-12 은 24시가 되며 한 시간 되돌아가, 23:00~24:00 이 두 번 지나간다.
        어느 쪽을 고를지는 정책이고, 여기서는 이른 쪽(아직 서머타임인 쪽)으로 정했다.
        """
        chosen = st.wall_to_utc(1948, 9, 12, 23, 30)
        self.assertEqual(st.utc_offset_at(chosen), 36000)      # 서머타임 쪽
        later = chosen + 3600                                  # 해제 뒤 같은 벽시계 시각
        self.assertEqual(st.utc_offset_at(later), 32400)
        self.assertEqual(st.epoch_to_parts(later + 32400)[3:5], (23, 30))


class CivilCalendar(unittest.TestCase):
    def test_날짜와_일수가_왕복한다(self):
        rng = random.Random(2)
        for _ in range(3000):
            y, m, d = rng.randint(1800, 2200), rng.randint(1, 12), rng.randint(1, 28)
            self.assertEqual(st.civil_from_days(st._days_from_civil(y, m, d)), (y, m, d))

    def test_기준일(self):
        self.assertEqual(st._days_from_civil(1970, 1, 1), 0)
        self.assertEqual(st.civil_from_days(0), (1970, 1, 1))


class SolarLongitude(unittest.TestCase):
    def test_절기는_정확히_15도_배수에서_잡힌다(self):
        for year in (1900, 1954, 1987, 2000, 2026, 2050):
            for i, (name, epoch) in enumerate(st.solar_term_times(year)):
                lon = st.solar_longitude_at(epoch)
                want = (i * 15) % 360
                gap = (lon - want + 180) % 360 - 180
                self.assertLess(abs(gap), 1e-4, msg=f"{year} {name} 황경 {lon}")

    def test_절기는_시간순이고_간격이_그럴듯하다(self):
        times = [t for _, t in st.solar_term_times(2026)]
        self.assertEqual(times, sorted(times))
        gaps = [(b - a) / 86400 for a, b in zip(times, times[1:])]
        # 궤도가 타원이라 14.7~15.8일 사이에서 변한다
        self.assertGreater(min(gaps), 14.5)
        self.assertLess(max(gaps), 16.0)

    def test_중기가_별자리_경계와_같다(self):
        """24절기 중 짝수 번째(중기)가 12궁 시작점이다. 사주와 별자리가 만나는 지점."""
        for i, (name, epoch) in enumerate(st.solar_term_times(2026)):
            if i % 2:
                continue
            lon = st.solar_longitude_at(epoch)
            gap = (lon + 15) % 30 - 15        # 0 도 근처에서 감기지 않게
            self.assertLess(abs(gap), 1e-4, msg=f"{name} {lon}")

    def test_춘분이_양자리_시작(self):
        _, epoch = st.solar_term_times(2026)[0]
        y, m, d, *_ = st.epoch_to_parts(epoch + 9 * 3600)
        self.assertEqual((y, m), (2026, 3))
        self.assertIn(d, (20, 21))
        self.assertEqual(st.sign_of(st.solar_longitude_at(epoch + 60)), "양자리")

    def test_열두_별자리가_한_해를_덮는다(self):
        seen = {st.sign_of(st.solar_longitude_at(
            st._days_from_civil(2026, 1, 1) * 86400 + n * 86400)) for n in range(0, 365, 3)}
        self.assertEqual(seen, set(st.ZODIAC_SIGNS))

    def test_황경은_0에서_360_사이(self):
        rng = random.Random(3)
        for _ in range(2000):
            e = rng.uniform(-2.3e9, 2.6e9)
            lon = st.solar_longitude_at(e)
            self.assertGreaterEqual(lon, 0.0)
            self.assertLess(lon, 360.0)


if __name__ == "__main__":
    unittest.main()
