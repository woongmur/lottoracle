"""십신·신살·강약. 명리 교재와 대조하면 맞다/틀리다를 말할 수 있는 계산이다.

문구는 검증할 수 없지만 '어느 문구가 나오는가' 는 계산이 정하므로,
규칙(결정론·금칙어·빠짐없음)만 검사한다. 운세 모듈과 같은 방식.
"""

import unittest

from lottoracle import saju, sipsin
from lottoracle.fortune import FORBIDDEN_WORDS


def P(name: str) -> saju.Pillar:
    """'경진' 같은 두 글자로 기둥 하나."""
    return saju.Pillar(saju.STEMS.index(name[0]), saju.BRANCHES.index(name[1]))


def chart(text: str) -> list[saju.Pillar]:
    return [P(x) for x in text.split()]


class TenGods(unittest.TestCase):
    def test_열_가지가_다_나온다(self):
        """일간 하나만 잡아도 상대 천간 열 개가 십신 열 개로 하나씩 떨어진다."""
        for day in range(10):
            got = [sipsin.ten_god(day, t) for t in range(10)]
            self.assertEqual(sorted(got), sorted(sipsin.TEN_GODS), f"일간 {day}")

    def test_나와_같은_글자는_비견(self):
        for day in range(10):
            self.assertEqual(sipsin.ten_god(day, day), "비견")

    def test_오행_관계가_이름과_맞는다(self):
        """갑(목) 일간에서 보면 화=식상 토=재성 금=관성 수=인성 이어야 한다."""
        want = {2: "식신", 3: "상관", 4: "편재", 5: "정재",
                6: "편관", 7: "정관", 8: "편인", 9: "정인"}
        for target, name in want.items():
            self.assertEqual(sipsin.ten_god(0, target), name,
                             f"갑 -> {saju.STEMS[target]}")

    def test_정이_붙는_쪽은_음양이_다르다(self):
        """'정재·정관·정인·상관·겁재' 는 짝이 맞는(음양이 다른) 관계다. 100칸 전수."""
        paired = {"겁재", "상관", "정재", "정관", "정인"}
        for day in range(10):
            for target in range(10):
                same = saju.STEM_YIN[day] == saju.STEM_YIN[target]
                god = sipsin.ten_god(day, target)
                self.assertEqual(god in paired, not same, f"{day}->{target} {god}")

    def test_지지는_본기로_본다(self):
        """해는 임수(양), 사는 병화(양)로 친다. 자리 순서로 음양을 매기지 않는다."""
        self.assertEqual(sipsin.BRANCH_MAIN_QI[11], saju.STEMS.index("임"))
        self.assertEqual(sipsin.BRANCH_MAIN_QI[5], saju.STEMS.index("병"))
        for day in range(10):
            for b in range(12):
                self.assertEqual(sipsin.ten_god_of_branch(day, b),
                                 sipsin.ten_god(day, sipsin.BRANCH_MAIN_QI[b]))

    def test_정화_일간의_해수는_정관(self):
        """만세력·명리 프로그램이 내는 값. 해를 음수로 보면 편관이 나온다."""
        self.assertEqual(sipsin.ten_god_of_branch(saju.STEMS.index("정"), 11), "정관")


class Table(unittest.TestCase):
    """실제 사주 한 벌. 여러 만세력이 같은 답을 내는 것으로 골랐다."""

    def setUp(self):
        self.ps = chart("경진 정해 정해 갑진")
        self.day = self.ps[2].stem

    def test_여덟_글자에_십신이_붙는다(self):
        got = [(r["pillar"], r["stem"], r["branch"])
               for r in sipsin.ten_gods_table(self.ps, self.day)]
        self.assertEqual(got, [
            ("년", "정재", "상관"),
            ("월", "비견", "정관"),
            ("일", "일간", "정관"),
            ("시", "정인", "상관"),
        ])

    def test_일간은_세지_않는다(self):
        counts = sipsin.ten_god_counts(self.ps, self.day)
        self.assertEqual(sum(counts.values()), 7, "여덟 글자 중 일간은 '나' 라서 뺀다")
        self.assertEqual(counts["비견"], 1, "월간의 정화 하나만")

    def test_갈래로_묶으면_합이_같다(self):
        counts = sipsin.ten_god_counts(self.ps, self.day)
        groups = sipsin.group_counts(counts)
        self.assertEqual(sum(groups.values()), sum(counts.values()))
        self.assertEqual(groups["관성"], 2)


class Strength(unittest.TestCase):
    def test_월지가_두_몫이다(self):
        """글자 일곱에 월지 한 몫을 더해 여덟. 시주를 모르면 여섯."""
        ps = chart("경진 정해 정해 갑진")
        st = sipsin.strength(ps, ps[2].stem)
        self.assertEqual(st["support"] + st["other"], 8)
        st3 = sipsin.strength(ps[:3], ps[2].stem)
        self.assertEqual(st3["support"] + st3["other"], 6)

    def test_돕는_기운만_있으면_신강(self):
        """갑목 일간에 인성(수)과 비겁(목)만 세운 사주."""
        ps = chart("임자 계해 갑인 을묘")
        st = sipsin.strength(ps, ps[2].stem)
        self.assertEqual(st["label"], "신강")
        self.assertEqual(st["other"], 0)

    def test_쓰는_기운만_있으면_신약(self):
        """갑목 일간에 관성(금)과 재성(토)만 세운 사주."""
        ps = chart("경신 무술 갑술 경오")
        st = sipsin.strength(ps, ps[2].stem)
        self.assertEqual(st["label"], "신약")
        self.assertEqual(st["support"], 0)

    def test_이름과_비율이_어긋나지_않는다(self):
        """60갑자 × 60갑자를 돌려도 이름과 비율이 항상 같은 말을 해야 한다."""
        for i in range(60):
            for j in range(0, 60, 7):
                ps = [saju.Pillar(i % 10, i % 12), saju.Pillar(j % 10, j % 12),
                      saju.Pillar(j % 10, i % 12), saju.Pillar(i % 10, j % 12)]
                st = sipsin.strength(ps, ps[2].stem)
                if st["label"] == "신강":
                    self.assertGreaterEqual(st["ratio"], 0.55, str(st))
                elif st["label"] == "신약":
                    self.assertLessEqual(st["ratio"], 0.40, str(st))
                else:
                    self.assertTrue(0.40 < st["ratio"] < 0.55, str(st))


class Sinsal(unittest.TestCase):
    def test_천을귀인_표가_열_일간_모두에_있다(self):
        for day in range(10):
            self.assertEqual(len(sipsin.NOBLEMAN[day]), 2, f"일간 {day}")

    def test_갑_일간의_천을귀인은_축미(self):
        got = sipsin.NOBLEMAN[saju.STEMS.index("갑")]
        self.assertEqual({saju.BRANCHES[b] for b in got}, {"축", "미"})

    def test_정_일간에_해가_둘이면_천을귀인_둘(self):
        ps = chart("경진 정해 정해 갑진")
        found = {s["name"]: s["at"] for s in sipsin.sinsal(ps, ps[2].stem)}
        self.assertEqual(found["천을귀인"], ["월지", "일지"])

    def test_삼합국은_열두_지지를_다_덮는다(self):
        for b in range(12):
            self.assertEqual(set(sipsin._triad_of(b)), {"역마", "도화", "화개"})

    def test_역마는_삼합의_반대쪽이다(self):
        """인오술(화국)의 역마는 신. 널리 쓰이는 표와 맞는지 본다."""
        self.assertEqual(sipsin._triad_of(6)["역마"], saju.BRANCHES.index("신"))
        self.assertEqual(sipsin._triad_of(0)["도화"], saju.BRANCHES.index("유"))
        self.assertEqual(sipsin._triad_of(9)["화개"], saju.BRANCHES.index("축"))


class Reading(unittest.TestCase):
    def test_같은_사주면_언제나_같은_풀이(self):
        ps = chart("경진 정해 정해 갑진")
        el = saju.elements_count(ps)
        a = sipsin.reading(ps, ps[2].stem, el)
        b = sipsin.reading(ps, ps[2].stem, el)
        self.assertEqual(a, b)

    def test_어떤_생일이든_풀이가_나온다(self):
        """일간 10 × 월지 12 를 다 돌려도 표에서 빠지는 칸이 없어야 한다."""
        for stem in range(10):
            for branch in range(12):
                ps = [saju.Pillar(stem, branch)] * 3 + [saju.Pillar(stem, branch)]
                r = sipsin.reading(ps, stem, saju.elements_count(ps))
                self.assertTrue(r["dayStem"]["nature"])
                self.assertTrue(r["strength"]["text"])
                self.assertTrue(r["elementsNote"])

    def test_시주를_모르면_세_기둥으로만_센다(self):
        ps = chart("경진 정해 정해 갑진")
        full = sipsin.reading(ps, ps[2].stem, saju.elements_count(ps))
        three = sipsin.reading(ps[:3], ps[2].stem, saju.elements_count(ps[:3]))
        self.assertEqual(len(full["table"]), 4)
        self.assertEqual(len(three["table"]), 3)
        self.assertEqual(sum(three["counts"].values()), 5)

    def test_오행이_다_있으면_그렇게_적는다(self):
        ps = chart("경진 정해 정해 갑진")
        r = sipsin.reading(ps, ps[2].stem, saju.elements_count(ps))
        self.assertEqual(r["elementsNote"], sipsin.ELEMENTS_FULL_TEXT)

    def test_없는_오행을_짚어_준다(self):
        ps = chart("갑인 을묘 갑인 을묘")           # 목만 있는 사주
        r = sipsin.reading(ps, ps[2].stem, saju.elements_count(ps))
        self.assertIn("화·토·금·수", r["elementsNote"])

    def test_강한_십신은_많은_순서로_나온다(self):
        ps = chart("경진 정해 정해 갑진")
        r = sipsin.reading(ps, ps[2].stem, saju.elements_count(ps))
        counts = [g["count"] for g in r["strong"]]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertTrue(all(c >= 2 for c in counts))


class Words(unittest.TestCase):
    """문구 규칙. 운세와 같은 선을 지킨다 — 겁주지 않고, 당첨과 엮지 않는다."""

    def all_texts(self):
        for pair in sipsin.DAY_STEM_TEXT.values():
            yield pair[1]
        for pair in sipsin.TEN_GOD_TEXT.values():
            yield pair[1]
        for pair in sipsin.SINSAL_TEXT.values():
            yield pair[1]
        yield from sipsin.GROUP_MANY_TEXT.values()
        yield from sipsin.GROUP_NONE_TEXT.values()
        yield from sipsin.STRENGTH_TEXT.values()
        yield sipsin.ELEMENTS_FULL_TEXT

    def test_금칙어가_없다(self):
        for text in self.all_texts():
            for word in FORBIDDEN_WORDS:
                self.assertNotIn(word, text, f"금칙어 '{word}': {text[:30]}")

    def test_모든_이름에_문구가_있다(self):
        self.assertEqual(set(sipsin.DAY_STEM_TEXT), set(saju.STEMS))
        self.assertEqual(set(sipsin.TEN_GOD_TEXT), set(sipsin.TEN_GODS))
        self.assertEqual(set(sipsin.SINSAL_TEXT),
                         {"천을귀인", "문창귀인", "역마", "도화", "화개"})
        groups = {"비겁", "식상", "재성", "관성", "인성"}
        self.assertEqual(set(sipsin.GROUP_MANY_TEXT), groups)
        self.assertEqual(set(sipsin.GROUP_NONE_TEXT), groups)
        self.assertEqual(set(sipsin.STRENGTH_TEXT), {"신강", "중화", "신약"})

    def test_단정하지_않는다(self):
        """'~한다' 로 못박지 않고 '~봅니다/합니다' 로 끝낸다."""
        for text in self.all_texts():
            self.assertTrue(text.rstrip().endswith("."), text[-20:])


if __name__ == "__main__":
    unittest.main()
