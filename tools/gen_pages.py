"""검색엔진이 읽을 정적 페이지를 만든다.

    python3 tools/gen_pages.py --base https://lottoracle.com --out dist

앱 본체는 JS 로 그려지므로 크롤러에게는 빈 껍데기나 다름없다. 사람들이 실제로
검색하는 것("1239회 당첨번호", "로또 명당", "1등 배출점")에 걸리려면 그 내용이
HTML 에 글자로 있어야 한다. 회차 데이터와 배출점 데이터는 이미 있으니 그것으로 만든다.

배포할 때 돌린다 (deploy.yml). 저장소에는 결과물을 두지 않는다.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle.metrics import profile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = html.escape


def won(n: int) -> str:
    return f"{n:,}원"


CSS = """
:root{color-scheme:dark}
body{margin:0;background:#0f1115;color:#e6ebf1;
  font-family:system-ui,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  line-height:1.65;font-size:15px}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 56px}
a{color:#7aa2ff}
h1{font-size:22px;margin:8px 0 4px}
h2{font-size:17px;margin:28px 0 8px;padding-top:14px;border-top:1px solid #232833}
.sub{color:#8b95a5;font-size:13.5px;margin:0 0 16px}
.balls{margin:10px 0 4px}
.b{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;
  border-radius:50%;font-weight:800;color:#111;margin-right:6px;font-size:15px}
.c1{background:#fbc400}.c2{background:#69c8f2}.c3{background:#ff7272}
.c4{background:#aaa}.c5{background:#b0d840}
.plus{color:#8b95a5;margin:0 6px;font-weight:700}
.bonus{outline:2px dashed #8b95a5;outline-offset:2px;margin-left:4px}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}
th,td{border-bottom:1px solid #232833;padding:7px 8px;text-align:left}
td.n,th.n{text-align:right}
th{color:#8b95a5;font-weight:600}
ul{padding-left:18px;margin:8px 0}
li{margin:4px 0}
.kv{color:#8b95a5;font-size:13.5px}
.cta{display:inline-block;margin:18px 0 0;padding:11px 16px;border-radius:10px;
  background:#7aa2ff;color:#0f1115;font-weight:700;text-decoration:none}
.nav{display:flex;justify-content:space-between;margin-top:26px;font-size:14px}
footer{margin-top:34px;padding-top:14px;border-top:1px solid #232833;color:#8b95a5;font-size:12.5px}
"""


def page(title: str, desc: str, canonical: str, body: str, base: str) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="{E(canonical)}">
<meta property="og:type" content="article">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:image" content="{E(base)}/icon-512.png">
<meta property="og:locale" content="ko_KR">
<link rel="icon" href="{E(base)}/icon.svg" type="image/svg+xml">
<style>{CSS}</style>
</head>
<body><div class="wrap">
{body}
<footer>
  <a href="{E(base)}/">lottoracle</a> · <a href="{E(base)}/about.html">소개 · 연락처</a>
  · <a href="{E(base)}/privacy.html">개인정보처리방침</a><br>
  당첨번호·판매점 자료 출처는 동행복권입니다. 모든 조합의 1등 확률은 1/8,145,060 으로 같습니다.
  이 사이트의 어떤 기능도 확률을 바꾸지 않습니다. 19세 미만 구매 불가 · 도박문제 상담 1336
</footer>
</div></body></html>
"""


def ball_html(nums, bonus=None) -> str:
    def cls(n):
        return f"c{1 if n <= 10 else 2 if n <= 20 else 3 if n <= 30 else 4 if n <= 40 else 5}"
    out = "".join(f'<span class="b {cls(n)}">{n}</span>' for n in nums)
    if bonus is not None:
        out += f'<span class="plus">+</span><span class="b {cls(bonus)} bonus">{bonus}</span>'
    return f'<div class="balls">{out}</div>'


def draw_page(d, prev_no, next_no, stores_for, base) -> tuple[str, str]:
    no, date = d["no"], d.get("draw_date") or ""
    nums, bonus = d["numbers"], d["bonus"]
    p = profile(nums)
    title = f"{no}회 로또 당첨번호 — {' · '.join(str(n) for n in nums)} + {bonus}"
    desc = (f"{no}회 로또 6/45 당첨번호는 {', '.join(str(n) for n in nums)} 이고 보너스는 {bonus} 입니다."
            + (f" {date} 추첨." if date else ""))

    rows = ""
    if d.get("prizes"):
        match = {1: "6개", 2: "5개+보너스", 3: "5개", 4: "4개", 5: "3개"}
        body = "".join(
            f'<tr><td>{pz["rank"]}등</td><td class="kv">{match.get(pz["rank"], "")}</td>'
            f'<td class="n">{pz["winners"]:,}게임</td><td class="n">{won(pz["amount"])}</td></tr>'
            for pz in d["prizes"])
        rows = ('<h2>등수별 당첨 현황</h2><table>'
                '<tr><th>등수</th><th>일치</th><th class="n">당첨 게임 수</th><th class="n">1게임당</th></tr>'
                + body + "</table>")
        if d.get("total_sales", -1) > 0:
            rows += f'<p class="kv">이 회차 총 판매금액 {won(d["total_sales"])}</p>'

    shops = ""
    first = [s for s in stores_for if no in s["r1"]]
    second = [s for s in stores_for if no in s["r2"]]
    if first or second:
        shops = "<h2>이 회차 당첨 판매점</h2>"
        if first:
            shops += f"<p><b>1등 배출점 {len(first)}곳</b></p><ul>" + "".join(
                f'<li>{E(s["name"])} — <span class="kv">{E(s["addr"])}'
                + (f' · {E(s["kind"])}' if s.get("kind") else "") + "</span></li>"
                for s in first) + "</ul>"
        if second:
            shown = second[:30]
            shops += f"<p><b>2등 배출점 {len(second)}곳</b></p><ul>" + "".join(
                f'<li>{E(s["name"])} — <span class="kv">{E(s["addr"])}</span></li>' for s in shown) + "</ul>"
            if len(second) > len(shown):
                shops += f'<p class="kv">외 {len(second) - len(shown)}곳</p>'

    nav = '<div class="nav">'
    nav += f'<a href="{base}/draw-{prev_no}.html">← {prev_no}회</a>' if prev_no else "<span></span>"
    nav += f'<a href="{base}/draw-{next_no}.html">{next_no}회 →</a>' if next_no else "<span></span>"
    nav += "</div>"

    body = f"""<p class="kv"><a href="{base}/">lottoracle</a> › <a href="{base}/draws.html">회차별 당첨번호</a></p>
<h1>{no}회 로또 당첨번호</h1>
<p class="sub">{E(date)} 추첨</p>
{ball_html(nums, bonus)}
<p class="kv">당첨번호 {', '.join(str(n) for n in nums)} · 보너스 {bonus}</p>
{rows}
<h2>조합 특징</h2>
<table>
<tr><th>번호 합계</th><td class="n">{p.total}</td><th>홀수 개수</th><td class="n">{p.odd}개</td></tr>
<tr><th>저구간(1~22)</th><td class="n">{p.low}개</td><th>AC값</th><td class="n">{p.ac}</td></tr>
<tr><th>끝수 합</th><td class="n">{p.end_sum}</td><th>연속 번호쌍</th><td class="n">{p.consecutive}</td></tr>
</table>
{shops}
<a class="cta" href="{base}/">번호 뽑아보기 · 내 주변 복권방 찾기</a>
{nav}"""
    return f"draw-{no}.html", page(title, desc, f"{base}/draw-{no}.html", body, base)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="예: https://lottoracle.com")
    ap.add_argument("--out", required=True, help="산출 디렉터리 (dist)")
    ap.add_argument("--draws", type=int, default=120, help="최근 N회차만 페이지로")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    draws = json.load(open(os.path.join(ROOT, "web", "data", "draws.json"), encoding="utf-8"))
    raw = json.load(open(os.path.join(ROOT, "web", "data", "stores.json"), encoding="utf-8"))
    stores = [s for s in raw["stores"].values()
              if s.get("lat") is not None and "인터넷" not in s.get("name", "")]

    draws.sort(key=lambda d: d["no"])
    targets = draws[-args.draws:]
    nos = [d["no"] for d in targets]
    os.makedirs(args.out, exist_ok=True)

    written = []
    for i, d in enumerate(targets):
        prev_no = nos[i - 1] if i else None
        next_no = nos[i + 1] if i + 1 < len(nos) else None
        rel = [s for s in stores if d["no"] in s["r1"] or d["no"] in s["r2"]]
        name, text = draw_page(d, prev_no, next_no, rel, base)
        open(os.path.join(args.out, name), "w", encoding="utf-8").write(text)
        written.append(name)

    # ---- 회차 목록 허브
    items = "".join(
        f'<li><a href="{base}/draw-{d["no"]}.html">{d["no"]}회</a> '
        f'<span class="kv">{E(d.get("draw_date") or "")} · '
        f'{", ".join(str(n) for n in d["numbers"])} + {d["bonus"]}</span></li>'
        for d in reversed(targets))
    body = (f'<p class="kv"><a href="{base}/">lottoracle</a> › 회차별 당첨번호</p>'
            f"<h1>로또 6/45 회차별 당첨번호</h1>"
            f'<p class="sub">{nos[0]}회부터 {nos[-1]}회까지. 회차를 누르면 등수별 당첨금과 그 회차 1·2등 배출점을 볼 수 있습니다.</p>'
            f"<ul>{items}</ul>"
            f'<a class="cta" href="{base}/">번호 뽑아보기</a>')
    open(os.path.join(args.out, "draws.html"), "w", encoding="utf-8").write(page(
        "로또 회차별 당첨번호 모음", f"{nos[0]}회~{nos[-1]}회 로또 6/45 당첨번호와 등수별 당첨금, 회차별 1·2등 배출점.",
        f"{base}/draws.html", body, base))
    written.append("draws.html")

    # ---- 명당(1등 다배출점)
    fame = sorted((s for s in stores if len(s["r1"]) >= 2),
                  key=lambda s: (-len(s["r1"]), -len(s["r2"])))
    rows = "".join(
        f'<tr><td>{E(s["name"])}</td><td class="kv">{E(s["addr"])}</td>'
        f'<td class="n">{len(s["r1"])}회</td><td class="n">{len(s["r2"])}회</td>'
        f'<td class="kv">{", ".join(str(n) for n in sorted(s["r1"], reverse=True)[:6])}</td></tr>'
        for s in fame)
    body = (f'<p class="kv"><a href="{base}/">lottoracle</a> › 로또 명당</p>'
            f"<h1>로또 명당 — 1등을 두 번 이상 배출한 판매점</h1>"
            f'<p class="sub">{min(raw["draws"])}회~{max(raw["draws"])}회 기준 {len(fame)}곳. '
            f'동행복권 당첨판매점 자료입니다.</p>'
            f'<table><tr><th>판매점</th><th>주소</th><th class="n">1등</th><th class="n">2등</th><th>배출 회차</th></tr>'
            f"{rows}</table>"
            f'<p class="kv">많이 배출한 곳은 그만큼 많이 팔린 곳이기도 합니다. 어느 판매점에서 사든 1등 확률은 1/8,145,060 으로 같습니다.</p>'
            f'<a class="cta" href="{base}/">지도에서 내 주변 배출점 보기</a>')
    open(os.path.join(args.out, "fame.html"), "w", encoding="utf-8").write(page(
        "로또 명당 — 1등 다배출 판매점 목록",
        f"1등을 두 번 이상 배출한 판매점 {len(fame)}곳의 이름·주소와 배출 회차. 지도에서 내 주변 배출점도 찾을 수 있습니다.",
        f"{base}/fame.html", body, base))
    written.append("fame.html")

    # ---- 사이트맵. 크롤러가 이 페이지들을 찾아가는 지도다.
    urls = ["", "draws.html", "fame.html", "about.html", "privacy.html"] + [f"draw-{n}.html" for n in reversed(nos)]
    def entry(u: str) -> str:
        prio = "1.0" if u == "" else "0.8" if u in ("draws.html", "fame.html") else "0.4" if u == "about.html" else "0.3" if u == "privacy.html" else "0.6"
        freq = "weekly" if u in ("", "draws.html", "fame.html") else "yearly"
        return f"  <url><loc>{base}/{u}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(entry(u) for u in urls) + "\n</urlset>\n")
    open(os.path.join(args.out, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)

    print(f"{len(written)}개 페이지 + sitemap.xml({len(urls)}개 주소) 생성 ({args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
