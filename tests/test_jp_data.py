"""일본 로또 당첨번호 — 파싱 · 원본 대조 · 저장본 잇기 · 저장된 데이터 검사.

네트워크를 타지 않는다. 원본 표본은 2026-10 실제 파일에서 몇 줄씩 잘라 왔다.
"""

from __future__ import annotations

import os
import tempfile
import unittest

from lottoracle.jp import data
from lottoracle.jp.data import JpDraw, SourceError
from lottoracle.jp.games import GAMES

THEKYO_LOTO6 = """開催回,日付,第1数字,第2数字,第3数字,第4数字,第5数字,第6数字,BONUS数字,1等口数,2等口数,3等口数,4等口数,5等口数,1等賞金,2等賞金,3等賞金,4等賞金,5等賞金,キャリーオーバー
2144,2026/10/8,5,6,11,25,31,32,15,1,4,259,11833,177579,200000000,15029600,250600,5700,1000,388848
2145,2026/10/12,4,6,8,11,24,27,36,10,9,621,20410,249138,17661500,5874400,91900,2900,1000,0
"""
LIFE_LOTO6 = """開催回,開催日,第1数字,第2数字,第3数字,第4数字,第5数字,第6数字,ボーナス数字,1等口数,1等賞金,2等口数,2等賞金,3等口数,3等賞金,4等口数,4等賞金,5等口数,5等賞金,キャリーオーバー
2144,2026-10-08,5,6,11,25,31,32,15,1,200000000,4,15029600,259,250600,11833,5700,177579,1000,388848
2145,2026-10-12,4,6,8,11,24,27,36,10,17661500,9,5874400,621,91900,20410,2900,249138,1000,0
"""
# 미니로또 thekyo 는 머리줄 끝에 'EOF' 라는 빈 열이 있고 줄은 하나 짧다. 이월도 없다.
THEKYO_MINI = """開催回,日付,第1数字,第2数字,第3数字,第4数字,第5数字,BONUS数字,1等口数,2等口数,3等口数,4等口数,1等賞金,2等賞金,3等賞金,4等賞金,EOF
1407,2026/10/6,7,13,15,26,28,4,22,104,2135,51954,7213100,109600,9200,900
1408,2026/10/13,2,5,6,24,28,19,11,72,1752,48659,13855500,152000,10800,1000
"""
LIFE_MINI = """開催回,開催日,第1数字,第2数字,第3数字,第4数字,第5数字,ボーナス数字,1等口数,1等賞金,2等口数,2等賞金,3等口数,3等賞金,4等口数,4等賞金
1407,2026-10-06,7,13,15,26,28,4,22,7213100,104,109600,2135,9200,51954,900
1408,2026-10-13,2,5,6,24,28,19,11,13855500,72,152000,1752,10800,48659,1000
"""
THEKYO_LOTO7 = """開催回,日付,第1数字,第2数字,第3数字,第4数字,第5数字,第6数字,第7数字,BONUS数字1,BONUS数字2,1等口数,2等口数,3等口数,4等口数,5等口数,6等口数,1等賞金,2等賞金,3等賞金,4等賞金,5等賞金,6等賞金,キャリーオーバー
698,2026/10/9,10,13,21,24,28,29,34,1,26,1,4,90,5238,88083,148228,919963300,14579100,746300,7700,1500,1100,0
"""
RAKUTEN_LOTO6 = """<table class="loto-popup-table"><tbody>
        <tr>
          <td><span>第2145回</span>2026/10/12</td>
          <td><ul class="loto-popup-number">
              <li>4</li> <li>6</li> <li>8</li> <li>11</li> <li>24</li> <li>27</li>
          </ul></td>
          <td><ul class="loto-popup-number num-bonus">
              <li>36</li>
          </ul></td>
        </tr>
        <tr>
          <td><span>第2144回</span>2026/10/08</td>
          <td><ul class="loto-popup-number">
              <li>5</li> <li>6</li> <li>11</li> <li>25</li> <li>31</li> <li>32</li>
          </ul></td>
          <td><ul class="loto-popup-number num-bonus"><li>15</li></ul></td>
        </tr>
</tbody></table>"""
RAKUTEN_LOTO7 = """<tr><td><span>第0698回</span>2026/10/09</td>
<td><ul class="loto-popup-number"><li>10</li><li>13</li><li>21</li><li>24</li><li>28</li><li>29</li><li>34</li></ul></td>
<td><ul class="loto-popup-number num-bonus"><li>1</li><li>26</li></ul></td></tr>"""

L6, L7, MINI = GAMES["loto6"], GAMES["loto7"], GAMES["miniloto"]


def draw(no, nums, bonus, date="2026-01-01", prizes=()):
    return JpDraw(no, date, tuple(nums), tuple(bonus), tuple(prizes))


class Parse(unittest.TestCase):
    def test_두_CSV_는_열_순서가_달라도_같은_값(self):
        a = data.parse_csv(L6, THEKYO_LOTO6)
        b = data.parse_csv(L6, LIFE_LOTO6)
        self.assertEqual(a, b)
        self.assertEqual(a[0].date, "2026-10-08")
        self.assertEqual(a[1].numbers, (4, 6, 8, 11, 24, 27))
        self.assertEqual(a[1].bonus, (36,))
        self.assertEqual(a[0].prizes[0], (1, 200000000))
        self.assertEqual(a[0].prizes[4], (177579, 1000))
        self.assertEqual(a[0].carryover, 388848)

    def test_미니로또는_EOF_열과_짧은_줄을_견딘다(self):
        a = data.parse_csv(MINI, THEKYO_MINI)
        self.assertEqual(a, data.parse_csv(MINI, LIFE_MINI))
        self.assertEqual(a[1].numbers, (2, 5, 6, 24, 28))
        self.assertEqual(len(a[1].prizes), 4)
        self.assertEqual(a[1].carryover, -1, "미니로또에는 이월이 없다")

    def test_로또7_보너스는_둘(self):
        (d,) = data.parse_csv(L7, THEKYO_LOTO7)
        self.assertEqual(d.bonus, (1, 26))
        self.assertEqual(len(d.numbers), 7)
        self.assertEqual(len(d.prizes), 6)

    def test_Shift_JIS_로_와도_읽는다(self):
        self.assertEqual(data.decode(THEKYO_LOTO6.encode("cp932")), THEKYO_LOTO6)
        self.assertEqual(data.decode(THEKYO_LOTO6.encode("utf-8")), THEKYO_LOTO6)

    def test_열이_바뀌면_멈춘다(self):
        broken = THEKYO_LOTO6.replace("第6数字", "第6番号", 1)
        with self.assertRaises(SourceError):
            data.parse_csv(L6, broken)
        with self.assertRaises(SourceError, msg="로또6 CSV 를 로또7 로 읽으면 열이 모자란다"):
            data.parse_csv(L7, THEKYO_LOTO6)

    def test_당첨금이_아직_비어_있는_줄(self):
        text = THEKYO_LOTO6 + "2146,2026/10/15,1,2,3,4,5,6,7,,,,,,,,,,,\n"
        d = data.parse_csv(L6, text)[-1]
        self.assertEqual(d.no, 2146)
        self.assertEqual(d.prizes, ())

    def test_라쿠텐(self):
        a = data.parse_rakuten(L6, RAKUTEN_LOTO6)
        self.assertEqual([d.no for d in a], [2145, 2144])
        self.assertEqual(a[0].key(), data.parse_csv(L6, THEKYO_LOTO6)[1].key())
        (d,) = data.parse_rakuten(L7, RAKUTEN_LOTO7)
        self.assertEqual((d.no, d.bonus), (698, (1, 26)), "앞자리 0 을 떼고 보너스 둘")

    def test_라쿠텐_형식이_바뀌면_멈춘다(self):
        with self.assertRaises(SourceError):
            data.parse_rakuten(L6, "<html>점검 중</html>")


class Check(unittest.TestCase):
    def test_규칙에_어긋나는_회차(self):
        data.check_draw(L6, draw(1, [1, 2, 3, 4, 5, 43], [7]))
        bad = [
            draw(1, [1, 2, 3, 4, 5], [7]),              # 개수
            draw(1, [1, 1, 3, 4, 5, 6], [7]),           # 중복
            draw(1, [1, 2, 3, 4, 5, 44], [7]),          # 범위 (로또6 은 43까지)
            draw(1, [1, 2, 3, 4, 5, 6], [6]),           # 보너스가 본숫자와 겹침
            draw(1, [1, 2, 3, 4, 5, 6], [7, 8]),        # 보너스 개수
        ]
        for d in bad:
            with self.subTest(d=d), self.assertRaises(SourceError):
                data.check_draw(L6, d)
        with self.assertRaises(SourceError):
            data.check_draw(L7, draw(1, [1, 2, 3, 4, 5, 6, 7], [8]))  # 로또7 은 보너스 둘

    def test_빠진_회차와_거꾸로_간_날짜(self):
        ok = [draw(1, [1, 2, 3, 4, 5, 6], [7], "2026-01-01"),
              draw(2, [1, 2, 3, 4, 5, 6], [7], "2026-01-05")]
        data.check_series(L6, ok)
        with self.assertRaises(SourceError):
            data.check_series(L6, [ok[1]])
        with self.assertRaises(SourceError):
            data.check_series(L6, [ok[0], draw(2, [1, 2, 3, 4, 5, 6], [7], "2025-12-31")])


class Combine(unittest.TestCase):
    def setUp(self):
        self.a = data.parse_csv(L6, THEKYO_LOTO6)
        self.b = data.parse_csv(L6, LIFE_LOTO6)
        self.r = data.parse_rakuten(L6, RAKUTEN_LOTO6)

    def test_셋이_같으면_받는다(self):
        out, notes = data.combine(L6, {"thekyo": self.a, "loto-life": self.b, "rakuten": self.r})
        self.assertEqual(out, self.a)
        self.assertEqual(len(notes), 3)

    def test_하나라도_다르면_멈춘다(self):
        wrong = [self.b[0], draw(2145, [4, 6, 8, 11, 24, 28], [36], "2026-10-12")]
        with self.assertRaises(SourceError):
            data.combine(L6, {"thekyo": self.a, "loto-life": wrong})
        wrong_date = [self.r[0], draw(2144, [5, 6, 11, 25, 31, 32], [15], "2026-10-09")]
        with self.assertRaises(SourceError):
            data.combine(L6, {"thekyo": self.a, "rakuten": wrong_date})

    def test_원본_하나로는_받지_않는다(self):
        with self.assertRaises(SourceError):
            data.combine(L6, {"thekyo": self.a})
        with self.assertRaises(SourceError, msg="라쿠텐은 최근 10회뿐이라 전체 이력이 될 수 없다"):
            data.combine(L6, {"rakuten": self.r})

    def test_먼저_갱신된_쪽의_새_회차도_받는다(self):
        newer = self.a + [draw(2146, [1, 2, 3, 4, 5, 6], [7], "2026-10-15")]
        out, _ = data.combine(L6, {"thekyo": newer, "loto-life": self.b})
        self.assertEqual(out[-1].no, 2146)


class Cache(unittest.TestCase):
    def test_과거_회차가_바뀌어_오면_멈춘다(self):
        cached = data.parse_csv(L6, THEKYO_LOTO6)
        changed = [cached[0], draw(2145, [4, 6, 8, 11, 24, 28], [36], "2026-10-12")]
        with self.assertRaises(SourceError):
            data.merge_cache(L6, cached, changed)

    def test_당첨금은_나중에_채워진다(self):
        full = data.parse_csv(L6, THEKYO_LOTO6)
        early = data.parse_rakuten(L6, RAKUTEN_LOTO6)        # 번호만 있고 당첨금이 없다
        merged = data.merge_cache(L6, early, full)
        self.assertTrue(all(d.prizes for d in merged))
        again = data.merge_cache(L6, full, early)            # 거꾸로 와도 지우지 않는다
        self.assertTrue(all(d.prizes for d in again))


def fake_web(files: dict[str, str]):
    """원본 이름 -> 본문. 없는 원본은 접속 실패로 친다."""
    def fetch(url: str) -> bytes:
        for name, urls in data.SOURCES.items():
            if url in urls.values() and name in files:
                return files[name].encode("cp932")
        raise SourceError(f"접속 실패 {url}")
    return fetch


class Update(unittest.TestCase):
    """update() 를 임시 폴더에서 끝까지 돌린다. 1회부터가 아니라 검사를 피하려고
    표본 앞에 1~2143회를 채운 저장본을 깔아 둔다."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = os.path.join(self.tmp.name, "data")
        self.web_dir = os.path.join(self.tmp.name, "web")
        # 날짜는 앞으로만 가면 된다 (한 달에 한 회차씩)
        base = [draw(n, [1, 2, 3, 4, 5, 6], [7], f"{1800 + n // 12:04d}-{1 + n % 12:02d}-01")
                for n in range(1, 2144)]
        data.save(L6, base, self.data_dir)

    def tearDown(self):
        self.tmp.cleanup()

    def run_update(self, files):
        return data.update("loto6", fetch=fake_web(files), data_dir=self.data_dir, web_dir=self.web_dir)

    def test_둘이_맞으면_저장하고_웹_사본도_같다(self):
        rep = self.run_update({"thekyo": THEKYO_LOTO6, "loto-life": LIFE_LOTO6, "rakuten": RAKUTEN_LOTO6})
        self.assertEqual((rep.before, rep.after), (2143, 2145))
        with open(data.path_of("loto6", self.data_dir), encoding="utf-8") as a, \
                open(data.path_of("loto6", self.web_dir), encoding="utf-8") as b:
            self.assertEqual(a.read(), b.read())
        self.assertEqual(data.load("loto6", self.data_dir)[-1].numbers, (4, 6, 8, 11, 24, 27))

    def test_한_곳이_안_열려도_나머지_둘로_간다(self):
        rep = self.run_update({"loto-life": LIFE_LOTO6, "rakuten": RAKUTEN_LOTO6})
        self.assertEqual(rep.after, 2145)
        self.assertIn("thekyo", rep.line())

    def test_둘이_안_열리면_아무것도_쓰지_않는다(self):
        before = data.load("loto6", self.data_dir)
        with self.assertRaises(SourceError):
            self.run_update({"thekyo": THEKYO_LOTO6})
        self.assertEqual(data.load("loto6", self.data_dir), before)
        self.assertFalse(os.path.exists(data.path_of("loto6", self.web_dir)))


class Committed(unittest.TestCase):
    """저장소에 올라간 데이터 자체를 검사한다. 최신 회차 번호는 박지 않는다(매주 는다)."""

    def test_세_게임_모두_1회부터_규칙대로(self):
        for key, game in GAMES.items():
            with self.subTest(game=key):
                draws = data.load(key)
                self.assertGreater(len(draws), 100)
                data.check_series(game, draws)

    def test_웹_사본과_같다(self):
        for key in GAMES:
            with self.subTest(game=key), \
                    open(data.path_of(key), encoding="utf-8") as a, \
                    open(data.path_of(key, data.WEB_DATA_DIR), encoding="utf-8") as b:
                self.assertEqual(a.read(), b.read())


if __name__ == "__main__":
    unittest.main()
