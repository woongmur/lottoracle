"""정적 페이지와 사이트맵. 틀려도 아무것도 빨갛게 안 뜨는 곳이라 따로 지킨다.

사이트맵이 어긋나면 사이트는 멀쩡히 열리고 CI 도 초록인데, 검색엔진만 조용히
페이지를 못 찾는다. 색인 수가 이상하게 적을 때에야 알게 된다.
"""

import os
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://lottoracle.com"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class Sitemap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = cls.tmp.name
        subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "gen_pages.py"),
             "--base", BASE, "--out", cls.out],
            check=True, capture_output=True, cwd=ROOT)
        root = ET.parse(os.path.join(cls.out, "sitemap.xml")).getroot()
        cls.urls = [(u.find("s:loc", NS).text,
                     (u.find("s:lastmod", NS).text if u.find("s:lastmod", NS) is not None else None))
                    for u in root.findall("s:url", NS)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @staticmethod
    def path_of(loc: str) -> str:
        return unquote(urlparse(loc).path).lstrip("/") or "index.html"

    def test_주소에_한글이_그대로_남지_않는다(self):
        """region-경기.html 이 그대로 들어가 있었다. 규약은 퍼센트 인코딩이다."""
        raw = [loc for loc, _ in self.urls if not loc.isascii()]
        self.assertEqual(raw, [], f"인코딩 안 된 주소 {len(raw)}개")

    def test_모든_주소가_실제_파일을_가리킨다(self):
        missing = [self.path_of(loc) for loc, _ in self.urls
                   if self.path_of(loc) != "index.html"
                   and not os.path.exists(os.path.join(self.out, self.path_of(loc)))]
        # index.html·about·privacy 는 gen_pages 가 아니라 배포 단계에서 복사된다
        missing = [m for m in missing if m not in ("about.html", "privacy.html")]
        self.assertEqual(missing, [])

    def test_canonical_이_사이트맵과_같은_글자다(self):
        """같은 페이지를 두 가지 글자로 부르면 크롤러에겐 다른 주소일 수 있다."""
        for loc, _ in self.urls:
            p = self.path_of(loc)
            if not p.startswith(("region-", "draw-")):
                continue
            head = open(os.path.join(self.out, p), encoding="utf-8").read(3000)
            canon = re.search(r'rel="canonical" href="([^"]+)"', head).group(1)
            og = re.search(r'property="og:url" content="([^"]+)"', head).group(1)
            self.assertEqual(canon, loc, p)
            self.assertEqual(og, loc, p)

    def test_lastmod_는_확실한_곳에만(self):
        """구글은 lastmod 가 맞는다고 확인될 때만 믿는다. 모르는 날짜는 안 적는다."""
        mods = {self.path_of(loc): mod for loc, mod in self.urls}
        for p in ("about.html", "privacy.html"):
            self.assertIsNone(mods[p], f"{p} 는 수정일을 모른다")
        for p, mod in mods.items():
            if p in ("about.html", "privacy.html"):
                continue
            self.assertIsNotNone(mod, p)
            self.assertRegex(mod, DATE, p)

    def test_회차_페이지는_그_회차_날짜다(self):
        """지난 회차 페이지는 추첨 뒤로 안 바뀐다. 최신 날짜를 붙이면 거짓말이 된다."""
        draws = {self.path_of(loc): mod for loc, mod in self.urls
                 if self.path_of(loc).startswith("draw-")}
        self.assertGreater(len(set(draws.values())), 100, "회차마다 날짜가 달라야 한다")
        latest = max(draws.values())
        hubs = {self.path_of(loc): mod for loc, mod in self.urls
                if self.path_of(loc) in ("index.html", "draws.html", "regions.html")}
        for p, mod in hubs.items():
            self.assertEqual(mod, latest, f"{p} 는 매주 갱신되므로 최신 회차 날짜")


if __name__ == "__main__":
    unittest.main()
