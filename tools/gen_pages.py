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
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle.engine import draw_date_of
from lottoracle.jp import data as jp_data
from lottoracle.jp import stats as jp_stats
from lottoracle.jp.games import GAMES as JP_GAMES, RANK_MATCH, next_draw_date
from lottoracle.jp.metrics import expected_sum, profile as jp_profile
from lottoracle.metrics import profile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = html.escape


def won(n: int) -> str:
    return f"{n:,}원"


CSS = """
:root{color-scheme:dark}
body{margin:0;background:#141311;color:#f2efe8;letter-spacing:-.01em;
  font-family:'Pretendard Variable',Pretendard,system-ui,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;
  line-height:1.65;font-size:15px;word-break:keep-all;overflow-wrap:anywhere}
.wrap{max-width:760px;margin:0 auto;padding:20px 16px 56px}
a{color:#ffc83d;text-underline-offset:3px}
/* 제목은 한 줄에: 좁은 화면에서는 글자를 줄이고, 긴 설명은 title·sub 로 보낸다 */
h1{font-size:clamp(18px,5.4vw,23px);margin:8px 0 4px;line-height:1.35;letter-spacing:-.03em}
h2{font-size:17px;margin:28px 0 8px;padding-top:14px;border-top:1px solid #34312b}
/* 소제목 앞 노란 막대 — 앱 화면과 같은 표시 */
h2::before{content:'';display:inline-block;width:4px;height:14px;background:#ffc83d;margin-right:8px;vertical-align:-1px}
.sub{color:#a29d92;font-size:13.5px;margin:0 0 16px}
.balls{margin:10px 0 4px}
.b{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;
  border-radius:50%;font-weight:800;color:#111;margin-right:6px;font-size:15px}
.c1{background:#fbc400}.c2{background:#69c8f2}.c3{background:#ff7272}
.c4{background:#aaa}.c5{background:#b0d840}
.plus{color:#a29d92;margin:0 6px;font-weight:700}
.b.s{width:27px;height:27px;font-size:12.5px;margin-right:4px}
/* 회차 목록: 글머리표 대신 줄로 나누고 당첨번호를 공으로 보여 준다 */
.dl{list-style:none;padding:0;margin:14px 0}
.dl li{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;
  padding:9px 0;margin:0;border-bottom:1px solid #34312b}
.dl .no{font-weight:700;min-width:58px}
.dl .balls{margin:0}
.bonus{outline:2px dashed #a29d92;outline-offset:2px;margin-left:4px}
table{border-collapse:collapse;width:100%;margin:10px 0;font-size:14px}
.tw{overflow-x:auto;margin:10px 0}
.tw>table{margin:0}
/* 칸이 많은 표는 좁은 화면에서 쭈그러들지 않고 가로로 스크롤되게 한다 */
.tw>table.wide{min-width:620px}
th,td{border-bottom:1px solid #34312b;padding:7px 8px;text-align:left}
td.n,th.n{text-align:right;white-space:nowrap}
th{color:#a29d92;font-weight:600;white-space:nowrap}
/* 표의 첫 칸(판매점·지역 이름, 등수)은 줄바꿈하지 않는다. 넘치면 .tw 가 가로로 스크롤한다 */
.tw td:first-child{white-space:nowrap}
ul{padding-left:18px;margin:8px 0}
li{margin:4px 0}
.kv{color:#a29d92;font-size:13.5px}
.cta{display:inline-block;margin:18px 0 0;padding:11px 16px;border-radius:6px;
  background:#ffc83d;color:#141311;font-weight:800;text-decoration:none;box-shadow:0 3px 0 #806418}
.nav{display:flex;justify-content:space-between;margin-top:26px;font-size:14px}
footer{margin-top:34px;padding-top:14px;border-top:1px solid #34312b;color:#a29d92;font-size:12.5px}
/* 일본 로또: 번호대별 색이 없어 한 가지 공에 게임 상징색 테두리(공식 로고 색) */
.b.j{background:#f4efe6;color:#1b2550}
.g-loto6{box-shadow:inset 0 0 0 3px #e4007f}.g-loto7{box-shadow:inset 0 0 0 3px #e60012}
.g-miniloto{box-shadow:inset 0 0 0 3px #f39800}
.chip{display:inline-block;border-radius:3px;padding:1px 9px;font-size:12.5px;font-weight:700;color:#fff;margin-right:6px}
.chip.loto6{background:#e4007f}.chip.loto7{background:#e60012}.chip.miniloto{background:#f39800}
.cta.jp{background:#ff6a3d;box-shadow:0 3px 0 #80351f}
/* 좁은 화면: 공 7개 + 보너스 2개(로또7)가 한 줄에 들어가게 */
@media(max-width:480px){.b{width:32px;height:32px;font-size:13.5px;margin-right:4px}
  .b.s{width:26px;height:26px;font-size:12px;margin-right:3px}.plus{margin:0 4px}}
"""

# Google AdSense. 손으로 쓴 페이지(web/public)와 앱(index.html)에도 같은 줄이 있다.
# 게시자 ID 를 바꾸면 web/public/ads.txt 도 함께 바꾼다.
ADSENSE = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
           '?client=ca-pub-2355882691173163"\n     crossorigin="anonymous"></script>')

FOOTER_KR = ("당첨번호·판매점 자료 출처는 동행복권입니다. 모든 조합의 1등 확률은 1/8,145,060 으로 같습니다.\n"
             "  이 사이트의 어떤 기능도 확률을 바꾸지 않습니다. 19세 미만 구매 불가 · 도박문제 상담 1336")
FOOTER_JP = ("일본 로또 당첨번호는 일본 집계 사이트 두 곳의 전체 이력을 라쿠텐 다카라쿠지 최근 결과와 맞춰 본 값입니다"
             " (공식 발표: 미즈호은행). 어떤 조합이든 1등 확률은 같고, 이 사이트의 어떤 기능도 확률을 바꾸지 않습니다."
             " 이 사이트는 복권을 팔거나 구매를 대신하지 않습니다.")


def encode_url(url: str) -> str:
    """주소의 한글을 퍼센트 인코딩한다.

    region-경기.html 처럼 한글이 그대로 든 주소는 사이트맵 규약 밖이다(RFC 3986).
    브라우저는 알아서 인코딩해 주지만 크롤러가 너그러울 거라고 기대할 이유는 없다.
    사이트맵·canonical·og:url 이 전부 같은 글자로 같은 주소를 가리키게 한다.
    """
    return quote(url, safe=":/")


def page(title: str, desc: str, canonical: str, body: str, base: str, footer: str = FOOTER_KR) -> str:
    canonical = encode_url(canonical)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{ADSENSE}
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
<link rel="stylesheet" href="{E(base)}/fonts/pretendard/pretendard.css">
<style>{CSS}</style>
</head>
<body><div class="wrap">
{body}
<footer>
  <a href="{E(base)}/">lottoracle</a> · <a href="{E(base)}/about.html">소개 · 연락처</a>
  · <a href="{E(base)}/jp.html">일본 로또</a> · <a href="{E(base)}/privacy.html">개인정보처리방침</a><br>
  {footer}
</footer>
</div></body></html>
"""


def ball_html(nums, bonus=None, small=False) -> str:
    def cls(n):
        return f"c{1 if n <= 10 else 2 if n <= 20 else 3 if n <= 30 else 4 if n <= 40 else 5}"
    sz = " s" if small else ""
    out = "".join(f'<span class="b{sz} {cls(n)}">{n}</span>' for n in nums)
    if bonus is not None:
        out += f'<span class="plus">+</span><span class="b{sz} {cls(bonus)} bonus">{bonus}</span>'
    return f'<div class="balls">{out}</div>'


def draw_page(d, prev_no, next_no, stores_for, base) -> tuple[str, str]:
    no = d["no"]
    date = d.get("draw_date") or draw_date_of(no)
    nums, bonus = d["numbers"], d["bonus"]
    p = profile(nums)
    title = f"{no}회 로또 당첨번호 — {' · '.join(str(n) for n in nums)} + {bonus}"
    desc = (f"{no}회 로또 6/45 당첨번호는 {', '.join(str(n) for n in nums)} 이고 보너스는 {bonus} 입니다."
            f" {date} 추첨.")

    rows = ""
    if d.get("prizes"):
        match = {1: "6개", 2: "5개+보너스", 3: "5개", 4: "4개", 5: "3개"}
        body = "".join(
            f'<tr><td>{pz["rank"]}등</td><td class="kv">{match.get(pz["rank"], "")}</td>'
            f'<td class="n">{pz["winners"]:,}게임</td><td class="n">{won(pz["amount"])}</td></tr>'
            for pz in d["prizes"])
        rows = ('<h2>등수별 당첨 현황</h2><div class="tw"><table>'
                '<tr><th>등수</th><th>일치</th><th class="n">당첨</th><th class="n">1게임당</th></tr>'
                + body + "</table></div>")
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
<div class="tw"><table>
<tr><th>번호 합계</th><td class="n">{p.total}</td><th>홀수 개수</th><td class="n">{p.odd}개</td></tr>
<tr><th>저구간(1~22)</th><td class="n">{p.low}개</td><th>AC값</th><td class="n">{p.ac}</td></tr>
<tr><th>끝수 합</th><td class="n">{p.end_sum}</td><th>연속 번호쌍</th><td class="n">{p.consecutive}</td></tr>
</table></div>
{shops}
<a class="cta" href="{base}/">번호 뽑아보기 · 내 주변 복권방 찾기</a>
{nav}"""
    return f"draw-{no}.html", page(title, desc, f"{base}/draw-{no}.html", body, base)


# 동행복권 주소의 시·도 표기가 한 군데 뭉쳐 있다. '전남광주' 는 오타가 아니라
# 전남과 광주를 묶은 라벨이어서, 뒤에 오는 시·군·구로 갈라야 한다.
GWANGJU_GU = {"동구", "서구", "남구", "북구", "광산구"}


def sido_of(addr: str) -> str:
    w = addr.split()
    if not w:
        return ""
    if w[0] == "전남광주":
        return "광주" if len(w) > 1 and w[1] in GWANGJU_GU else "전남"
    return w[0]


def sgg_of(addr: str) -> str:
    """시·군·구 이름. 세종은 시·군·구 체계가 없어 두 번째 단어가 도로명이므로
    걸러 낸다 — 안 그러면 '세종 한누리대로' 같은 지역이 생긴다."""
    w = addr.split()
    if len(w) < 2 or not w[1].endswith(("시", "군", "구")):
        return ""
    return w[1]


def region_file(sido: str, sgg: str = "") -> str:
    return f"region-{sido}-{sgg}.html" if sgg else f"region-{sido}.html"


def tally(group) -> dict:
    """한 지역의 배출 실적. r1/r2 는 그 판매점이 1·2등을 낸 회차 목록이다."""
    return {
        "shops": len(group),
        "r1": sum(len(s["r1"]) for s in group),
        "r2": sum(len(s["r2"]) for s in group),
        "winners": sum(1 for s in group if s["r1"]),
    }


def rank_table(rows, base, note_col="") -> str:
    """지역 순위 표. rows = [(이름, 파일명 또는 None, 통계)]"""
    body = ""
    for i, (name, fname, t) in enumerate(rows, 1):
        label = f'<a href="{base}/{fname}">{E(name)}</a>' if fname else E(name)
        per = t["r1"] / t["shops"] if t["shops"] else 0
        body += (f'<tr><td class="n">{i}</td><td>{label}</td>'
                 f'<td class="n">{t["r1"]}회</td><td class="n">{t["r2"]}회</td>'
                 f'<td class="n">{t["shops"]}곳</td><td class="n">{per:.2f}</td></tr>')
    return ('<div class="tw"><table class="wide">'
            '<tr><th class="n">순위</th><th>지역</th><th class="n">1등</th><th class="n">2등</th>'
            '<th class="n">판매점</th><th class="n">판매점당 1등</th></tr>'
            + body + "</table></div>")


def shop_table(shops, base) -> str:
    body = ""
    for s in sorted(shops, key=lambda x: (-len(x["r1"]), -len(x["r2"])))[:60]:
        eps = ", ".join(str(n) for n in sorted(s["r1"], reverse=True)[:6])
        body += (f'<tr><td>{E(s["name"])}</td>'
                 f'<td class="n">{len(s["r1"])}회</td><td class="n">{len(s["r2"])}회</td>'
                 f'<td class="kv">{E(s["addr"])}</td><td class="kv">{eps}</td></tr>')
    return ('<div class="tw"><table class="wide">'
            '<tr><th>판매점</th><th class="n">1등</th><th class="n">2등</th>'
            '<th>주소</th><th>배출 회차</th></tr>' + body + "</table></div>")


def region_title(name: str, stat: dict) -> str:
    if not stat["r1"]:
        return f"{name} 로또 판매점 — 아직 1등이 나오지 않았습니다"
    return f"{name} 로또 명당 — 1등 배출 판매점"


def region_desc(name: str, stat: dict, span: str) -> str:
    if not stat["r1"]:
        return (f"{name} 로또 판매점 {stat['shops']}곳. {span} 기준 아직 1등이 나오지 않았고 "
                f"2등은 {stat['r2']}회 나왔습니다.")
    return (f"{name}에서 로또 1등이 나온 판매점 {stat['winners']}곳의 이름·주소와 배출 회차. "
            f"{span} 기준 1등 {stat['r1']}회, 2등 {stat['r2']}회.")


CAVEAT = ('<p class="kv">1등이 많이 나온 지역은 그만큼 복권이 많이 팔린 지역입니다. '
          '실제로 전국 시·도를 놓고 보면 판매점 수와 1등 배출 횟수의 상관계수가 0.997 로, '
          '거의 그대로 비례합니다. 판매점이 적은 지역은 표본이 작아 \'판매점당 1등\' 이 크게 흔들립니다. '
          '어느 판매점에서 사든 1등 확률은 1/8,145,060 으로 같습니다.</p>')


# ---------------------------------------------------------------- 일본 로또
# 앱의 일본 모드는 JS 로 그려져 주소가 따로 없다. "일본 로또7 당첨번호" 처럼 한국어로
# 찾는 사람에게 걸리도록 게임마다 글자로 된 페이지와 최근 회차별 페이지를 두고, 앱으로
# 바로 들어가는 버튼(?mode=jp&game=…)을 단다. 구매 안내는 넣지 않는다. 등수별 당첨금은
# 집계 사이트 두 곳이 일치한 공식 집계값을 옮긴다.

JP_ODDS = {"loto6": "6,096,454", "loto7": "10,295,472", "miniloto": "169,911"}
JP_PRICE = {"loto6": 200, "loto7": 300, "miniloto": 200}
JP_DAYS = {"loto6": "월·목", "loto7": "금", "miniloto": "화"}
JP_DRAW_PAGES = 100               # 게임마다 최근 몇 회차를 회차 페이지로 만들까


def jp_draw_file(key: str, no: int) -> str:
    return f"jp-{key}-{no}.html"


def jp_prize_table(key: str, d) -> str:
    """한 회차의 등수별 당첨 구수와 1구당 금액, 이월금."""
    if not d.prizes:
        return '<p class="kv">당첨금은 집계 중입니다. 보통 추첨 다음 날 아침까지 올라옵니다.</p>'
    rows = "".join(
        f'<tr><td>{i}등</td><td class="kv">{m}</td>'
        + (f'<td class="n">{w:,}구</td><td class="n">{a:,}엔</td>' if w else
           '<td class="n">0구</td><td class="n kv">해당 없음</td>')
        + "</tr>"
        for i, ((w, a), m) in enumerate(zip(d.prizes, RANK_MATCH[key]), 1))
    out = ('<div class="tw"><table><tr><th>등수</th><th>일치</th><th class="n">당첨</th>'
           f'<th class="n">1구당</th></tr>{rows}</table></div>')
    if d.carryover > 0:
        out += f'<p class="kv">다음 회차로 넘어가는 1등 이월금 <b>{d.carryover:,}엔</b></p>'
    return out


def jp_first_prize(d) -> str:
    """목록에 붙일 1등 한 줄."""
    if not d.prizes:
        return ""
    w, a = d.prizes[0]
    return f"1등 {w:,}구 · {a:,}엔" if w else "1등 없음 (이월)"


WEEKDAY_KO = "월화수목금토일"


def jp_day(iso: str) -> str:
    from datetime import date
    return f"{iso} ({WEEKDAY_KO[date.fromisoformat(iso).weekday()]})"


def jp_balls(key: str, nums, bonus=(), small=False) -> str:
    sz = " s" if small else ""
    out = "".join(f'<span class="b j{sz} g-{key}">{n}</span>' for n in nums)
    if bonus:
        out += '<span class="plus">+</span>' + "".join(
            f'<span class="b j{sz} g-{key} bonus">{n}</span>' for n in bonus)
    return f'<div class="balls">{out}</div>'


def jp_draw_page(key: str, draws, i: int, base: str, paged: set) -> tuple[str, str]:
    """회차 하나. draws[i] 가 그 회차. paged 는 페이지가 있는 회차 번호(앞뒤 이동용)."""
    g = JP_GAMES[key]
    d = draws[i]
    prev = draws[i - 1] if i > 0 else None
    p = jp_profile(g, d.numbers, prev.numbers if prev else ())
    name = jp_draw_file(key, d.no)
    nav = '<div class="nav">'
    nav += (f'<a href="{base}/{jp_draw_file(key, d.no - 1)}">← {d.no - 1}회</a>'
            if d.no - 1 in paged else "<span></span>")
    nav += (f'<a href="{base}/{jp_draw_file(key, d.no + 1)}">{d.no + 1}회 →</a>'
            if d.no + 1 in paged else "<span></span>")
    nav += "</div>"
    body = (
        f'<p class="kv"><a href="{base}/">lottoracle</a> › <a href="{base}/jp.html">일본 로또</a> › '
        f'<a href="{base}/jp-{key}.html">{E(g.name)}</a> › {d.no}회</p>'
        f"<h1>일본 {E(g.name)} {d.no}회 당첨번호</h1>"
        f'<p class="sub">{jp_day(d.date)} 추첨</p>'
        f"{jp_balls(key, d.numbers, d.bonus)}"
        f'<p class="kv">본숫자 {", ".join(map(str, d.numbers))} · 보너스 {", ".join(map(str, d.bonus))}</p>'
        f"<h2>등수별 당첨금</h2>{jp_prize_table(key, d)}"
        f"<h2>조합 특징</h2>"
        f'<div class="tw"><table>'
        f'<tr><th>번호 합계</th><td class="n">{p.total}</td><th>홀수 개수</th><td class="n">{p.odd}개</td></tr>'
        f'<tr><th>저구간(1~{g.pool // 2})</th><td class="n">{p.low}개</td><th>AC값</th><td class="n">{p.ac}</td></tr>'
        f'<tr><th>끝수 합</th><td class="n">{p.end_sum}</td><th>연속 번호쌍</th><td class="n">{p.consecutive}</td></tr>'
        + (f'<tr><th>직전 회차와 겹침</th><td class="n">{p.carryover}개</td><th></th><td></td></tr>' if prev else "")
        + "</table></div>"
        f'<a class="cta jp" href="{base}/?mode=jp&amp;game={key}">{E(g.name)} 번호 뽑아보기</a>'
        f"{nav}")
    nums = ", ".join(map(str, d.numbers))
    first = jp_first_prize(d)
    title = f"일본 {g.name} {d.no}회 당첨번호 ({d.date}) · 등수별 당첨금"
    desc = (f"일본 {g.name}({g.name_ja}) {d.no}회 {d.date} 추첨 당첨번호는 {nums}, "
            f"보너스 {', '.join(map(str, d.bonus))} 입니다."
            + (f" {first}." if first else "")
            + (f" 이월금 {d.carryover:,}엔." if d.carryover > 0 else ""))
    return name, page(title, desc, f"{base}/{name}", body, base, FOOTER_JP)


def jp_game_page(key: str, base: str) -> tuple[str, str, str]:
    """(파일 이름, html, 최신 추첨일)"""
    g = JP_GAMES[key]
    draws = jp_data.load(key, jp_data.WEB_DATA_DIR)
    last = draws[-1]
    nxt = next_draw_date(g, last.date)
    st = jp_stats.build(g, draws, recent_window=30)
    ps = jp_stats.profile_stats(g, draws)
    first_prizes = [(d.prizes[0][1], d.no) for d in draws if d.prizes and d.prizes[0][1] > 0]
    top_prize, top_no = max(first_prizes) if first_prizes else (0, 0)
    name = f"jp-{key}.html"

    paged = [d.no for d in draws[-JP_DRAW_PAGES:]]
    recent = "".join(
        f'<li><a class="no" href="{base}/{jp_draw_file(key, d.no)}">{d.no}회</a><span class="kv">{jp_day(d.date)}</span>'
        f'{jp_balls(key, d.numbers, d.bonus, small=True)}'
        + (f'<span class="kv">{jp_first_prize(d)}</span>' if d.prizes else "") + "</li>"
        for d in reversed(draws[-20:]))
    freq = sorted(((n, st.frequency.get(n, 0)) for n in range(1, g.pool + 1)), key=lambda kv: (-kv[1], kv[0]))
    freq_rows = "".join(f'<tr><td>{n}</td><td class="n">{c:,}회</td><td class="n">{st.bonus_frequency.get(n, 0):,}회</td>'
                        f'<td class="n">{st.recent.get(n, 0)}회</td><td class="n">{st.gap[n]}회차</td></tr>'
                        for n, c in sorted(freq, key=lambda kv: kv[0]))
    hot = " ".join(str(n) for n, _ in st.hot(10))
    cold = " ".join(str(n) for n, _ in st.cold(10))
    odd_mode = max(ps.odd_distribution.items(), key=lambda kv: kv[1])[0]
    body = (
        f'<p class="kv"><a href="{base}/">lottoracle</a> › <a href="{base}/jp.html">일본 로또</a> › {E(g.name)}</p>'
        f'<h1><span class="chip {key}">{E(g.name_ja)}</span>일본 {E(g.name)} 당첨번호</h1>'
        f'<p class="sub">최신 {last.no}회 · {jp_day(last.date)}<br>다음 {last.no + 1}회 · {jp_day(nxt)}</p>'
        f"<h2>{last.no}회 당첨번호</h2>{jp_balls(key, last.numbers, last.bonus)}"
        f"<h2>{last.no}회 등수별 당첨금</h2>{jp_prize_table(key, last)}"
        f'<a class="cta jp" href="{base}/?mode=jp&amp;game={key}">{E(g.name)} 번호 뽑아보기</a>'
        f"<h2>게임 규칙</h2><table>"
        f"<tr><th>번호</th><td>1~{g.pool} 중 {g.pick}개를 고릅니다</td></tr>"
        f"<tr><th>보너스</th><td>{g.bonus}개 (고르지 않습니다. 2등을 가르는 데만 씁니다)</td></tr>"
        f"<tr><th>추첨</th><td>매주 {JP_DAYS[key]}요일</td></tr>"
        f"<tr><th>1구 가격</th><td>{JP_PRICE[key]}엔</td></tr>"
        f"<tr><th>1등 확률</th><td>1/{JP_ODDS[key]} (어떤 조합이든 같습니다)</td></tr>"
        + (f"<tr><th>최고 1등</th><td>1구당 {top_prize:,}엔 ({top_no}회)</td></tr>" if top_prize else "")
        + f"<tr><th>첫 추첨</th><td>{draws[0].date} (1회)</td></tr></table>"
        f"<h2>최근 20회 당첨번호</h2><ul class=\"dl\">{recent}</ul>"
        + (f'<details><summary class="kv">지난 회차 ({paged[0]}~{paged[-21]}회)</summary><p class="kv">'
           + " · ".join(f'<a href="{base}/{jp_draw_file(key, n)}">{n}회</a>' for n in reversed(paged[:-20]))
           + "</p></details>" if len(paged) > 20 else "")
        + 
        f"<h2>당첨번호 평균치 ({len(draws):,}회 전체)</h2><table>"
        f'<tr><th>합계 평균</th><td class="n">{ps.mean_sum:.1f} (이론값 {expected_sum(g)})</td></tr>'
        f'<tr><th>합계 80% 구간</th><td class="n">{ps.sum_range_80[0]} ~ {ps.sum_range_80[1]}</td></tr>'
        f'<tr><th>가장 흔한 홀수 개수</th><td class="n">{odd_mode}개</td></tr>'
        f'<tr><th>연속번호가 끼는 비율</th><td class="n">{ps.consecutive_ratio * 100:.1f}%</td></tr>'
        f"</table>"
        f'<p class="kv">최근 30회 자주 나온 번호: {hot}<br>가장 오래 안 나온 번호: {cold}</p>'
        f"<h2>번호별 출현 횟수</h2>"
        f'<div class="tw"><table><tr><th>번호</th><th class="n">본숫자</th><th class="n">보너스</th>'
        f'<th class="n">최근 30회</th><th class="n">안 나온 지</th></tr>{freq_rows}</table></div>'
        f'<p class="kv">자주 나온 번호가 다음에도 나온다는 근거는 없습니다. 매 회차는 처음부터 다시 뽑습니다.</p>'
        f'<a class="cta jp" href="{base}/?mode=jp&amp;game={key}">{E(g.name)} 번호 뽑아보기</a>'
    )
    title = f"일본 {g.name}({g.name_ja}) 당첨번호 — 최신 {last.no}회 · 번호별 통계"
    desc = (f"일본 {g.name} {last.no}회({last.date}) 당첨번호와 등수별 당첨금"
            + ("·이월금" if g.carryover else "") + f", 최근 20회 결과, 1~{g.pool} 번호별 출현 횟수. "
            f"다음 추첨 {nxt}. {g.pick}개를 고르는 게임으로 1등 확률은 1/{JP_ODDS[key]}입니다.")
    return name, page(title, desc, f"{base}/{name}", body, base, FOOTER_JP), last.date


def jp_hub_page(base: str, latest: dict) -> str:
    rows = []
    for key, g in JP_GAMES.items():
        last = jp_data.load(key, jp_data.WEB_DATA_DIR)[-1]
        rows.append(
            f'<tr><td><a href="{base}/jp-{key}.html"><span class="chip {key}">{E(g.name)}</span></a></td>'
            f"<td>1~{g.pool} 중 {g.pick}개</td><td>{g.bonus}개</td><td>{JP_DAYS[key]}</td>"
            f'<td class="n">{JP_PRICE[key]}엔</td><td class="n">1/{JP_ODDS[key]}</td></tr>')
    latest_rows = "".join(
        f'<li><a class="no" href="{base}/jp-{key}.html">{E(g.name)}</a>'
        f'<a class="kv" href="{base}/{jp_draw_file(key, last.no)}">{last.no}회 {jp_day(last.date)}</a>'
        f'{jp_balls(key, last.numbers, last.bonus, small=True)}'
        + (f'<span class="kv">{jp_first_prize(last)}</span>' if last.prizes else "") + "</li>"
        for key, g in JP_GAMES.items()
        for last in [jp_data.load(key, jp_data.WEB_DATA_DIR)[-1]])
    body = (
        f'<p class="kv"><a href="{base}/">lottoracle</a> › 일본 로또</p>'
        f"<h1>일본 로또 당첨번호 · 번호 추천</h1>"
        f'<p class="sub">로또6 · 로또7 · 미니로또<br>일본 판매점(宝くじ売り場)에서 사는 숫자 복권</p>'
        f"<h2>최신 당첨번호</h2><ul class=\"dl\">{latest_rows}</ul>"
        f'<h2>세 게임 비교</h2><div class="tw"><table class="wide"><tr><th>게임</th><th>번호</th><th>보너스</th>'
        f'<th>추첨 요일</th><th class="n">1구</th><th class="n">1등 확률</th></tr>{"".join(rows)}</table></div>'
        f"<h2>한국 로또와 다른 점</h2><ul>"
        f"<li>보너스 숫자는 사는 사람이 고르지 않습니다. 추첨에서 따로 뽑아 2등을 가르는 데만 씁니다.</li>"
        f"<li>로또6·로또7은 1등이 없으면 1등 몫이 다음 회차로 넘어갑니다(이월, キャリーオーバー).</li>"
        f"<li>추첨이 일주일에 여러 번 있습니다. 로또6은 월·목, 미니로또는 화, 로또7은 금요일입니다.</li></ul>"
        f'<a class="cta jp" href="{base}/?mode=jp">일본 로또 번호 뽑아보기</a>'
        f'<p class="kv" style="margin-top:14px">앱의 일본 모드에서 게임을 골라 번호를 뽑고, 저장하고, '
        f"일본 판매점 지도를 볼 수 있습니다.</p>")
    return page("일본 로또 당첨번호 · 번호 추천 — 로또6 · 로또7 · 미니로또",
                "일본 로또6·로또7·미니로또의 최신 당첨번호, 게임 규칙 비교(번호 범위·추첨 요일·1등 확률), 번호 추천.",
                f"{base}/jp.html", body, base, FOOTER_JP)


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
        f'<li><a class="no" href="{base}/draw-{d["no"]}.html">{d["no"]}회</a>'
        f'<span class="kv">{E(d.get("draw_date") or draw_date_of(d["no"]))}</span>'
        f'{ball_html(d["numbers"], d["bonus"], small=True)}</li>'
        for d in reversed(targets))
    body = (f'<p class="kv"><a href="{base}/">lottoracle</a> › 회차별 당첨번호</p>'
            f"<h1>로또 6/45 회차별 당첨번호</h1>"
            f'<p class="sub">{nos[0]}회 ~ {nos[-1]}회<br>회차를 누르면 당첨금과 1·2등 배출점</p>'
            f'<ul class="dl">{items}</ul>'
            f'<a class="cta" href="{base}/">번호 뽑아보기</a>')
    open(os.path.join(args.out, "draws.html"), "w", encoding="utf-8").write(page(
        "로또 회차별 당첨번호 모음", f"{nos[0]}회~{nos[-1]}회 로또 6/45 당첨번호와 등수별 당첨금, 회차별 1·2등 배출점.",
        f"{base}/draws.html", body, base))
    written.append("draws.html")

    # ---- 명당(1등 다배출점)
    fame = sorted((s for s in stores if len(s["r1"]) >= 2),
                  key=lambda s: (-len(s["r1"]), -len(s["r2"])))
    rows = "".join(
        f'<tr><td>{E(s["name"])}</td>'
        f'<td class="n">{len(s["r1"])}회</td><td class="n">{len(s["r2"])}회</td>'
        f'<td class="kv">{E(s["addr"])}</td>'
        f'<td class="kv">{", ".join(str(n) for n in sorted(s["r1"], reverse=True)[:6])}</td></tr>'
        for s in fame)
    body = (f'<p class="kv"><a href="{base}/">lottoracle</a> › 로또 명당</p>'
            f"<h1>로또 명당 · 1등 2회 이상 판매점</h1>"
            f'<p class="sub">{min(raw["draws"])}회 ~ {max(raw["draws"])}회 · {len(fame)}곳<br>'
            f'자료: 동행복권 당첨판매점</p>'
            f'<div class="tw"><table class="wide"><tr><th>판매점</th><th class="n">1등</th>'
            f'<th class="n">2등</th><th>주소</th><th>배출 회차</th></tr>'
            f"{rows}</table></div>"
            f'<p class="kv">많이 배출한 곳은 그만큼 많이 팔린 곳이기도 합니다. 어느 판매점에서 사든 1등 확률은 1/8,145,060 으로 같습니다.</p>'
            f'<a class="cta" href="{base}/">지도에서 내 주변 배출점 보기</a>')
    open(os.path.join(args.out, "fame.html"), "w", encoding="utf-8").write(page(
        "로또 명당 — 1등 다배출 판매점 목록",
        f"1등을 두 번 이상 배출한 판매점 {len(fame)}곳의 이름·주소와 배출 회차. 지도에서 내 주변 배출점도 찾을 수 있습니다.",
        f"{base}/fame.html", body, base))
    written.append("fame.html")

    # ---- 지역별 명당. "수원 로또 명당" 처럼 사람들이 실제로 치는 검색어를 노린다.
    # 목록만 있으면 밋밋하므로 그 지역의 배출 실적과 전국 순위를 같이 얹는다.
    by_sido: dict[str, list] = {}
    by_sgg: dict[tuple[str, str], list] = {}
    for st in stores:
        sd = sido_of(st.get("addr", ""))
        if not sd:
            continue
        by_sido.setdefault(sd, []).append(st)
        sg = sgg_of(st["addr"])
        if sg:
            by_sgg.setdefault((sd, sg), []).append(st)

    sido_stats = {k: tally(v) for k, v in by_sido.items()}
    sido_order = sorted(sido_stats, key=lambda k: -sido_stats[k]["r1"])
    sido_rank = {k: i + 1 for i, k in enumerate(sido_order)}
    nation = {
        "r1": sum(t["r1"] for t in sido_stats.values()),
        "r2": sum(t["r2"] for t in sido_stats.values()),
        "shops": sum(t["shops"] for t in sido_stats.values()),
    }
    span = f'{min(raw["draws"])}회~{max(raw["draws"])}회'

    def region_body(name, group, stat, rank, total, sub_rows, parent=None):
        winners = [x for x in group if x["r1"]]
        crumb = (f'<p class="kv"><a href="{base}/">lottoracle</a> › '
                 f'<a href="{base}/regions.html">지역별 로또 명당</a>'
                 + (f' › <a href="{base}/{region_file(parent)}">{E(parent)}</a>' if parent else "")
                 + f' › {E(name)}</p>')
        # 1등이 한 번도 안 나온 지역에까지 '명당' 이라고 쓰면 사실과 다르다.
        # 없으면 없다고 적고, 대신 2등 배출점을 보여 준다.
        title_h1 = f"{E(name)} 로또 명당" if stat["r1"] else f"{E(name)} 로또 판매점"
        sub = (f'{span} 기준<br>판매점 {stat["shops"]:,}곳 중 {stat["winners"]:,}곳이 1등 배출'
               if stat["r1"] else
               f'{span} 기준<br>판매점 {stat["shops"]:,}곳, 아직 1등이 없습니다')
        head = (f"<h1>{title_h1}</h1>"
                f'<p class="sub">{sub}</p>'
                f'<div class="tw"><table>'
                f'<tr><th>1등 배출</th><td class="n">{stat["r1"]}회</td>'
                f'<th>2등 배출</th><td class="n">{stat["r2"]}회</td></tr>'
                f'<tr><th>판매점 수</th><td class="n">{stat["shops"]:,}곳</td>'
                f'<th>{"전국" if parent is None else E(parent)} 순위</th>'
                f'<td class="n">{rank}위 / {total}곳</td></tr>'
                f"</table></div>")
        body = crumb + head
        if sub_rows:
            body += f"<h2>{E(name)} 안에서 많이 나온 지역</h2>" + rank_table(sub_rows, base)
        if winners:
            body += f"<h2>{E(name)} 1등 배출 판매점</h2>" + shop_table(winners, base)
            if len(winners) > 60:
                body += f'<p class="kv">1등 배출점 {len(winners)}곳 중 많이 낸 60곳만 보여 줍니다.</p>'
        else:
            seconds = [x for x in group if x["r2"]]
            if seconds:
                body += (f"<h2>{E(name)} 2등 배출 판매점</h2>" + shop_table(seconds, base))
            else:
                body += (f'<p class="kv">{E(name)} 판매점 {stat["shops"]:,}곳에서는 아직 '
                         f'1·2등이 나오지 않았습니다.</p>')
        body += CAVEAT
        body += f'<a class="cta" href="{base}/">지도에서 내 주변 배출점 보기</a>'
        return body

    for sd in sido_order:
        group, stat = by_sido[sd], sido_stats[sd]
        subs = sorted(((sg, by_sgg[(s2, sg)]) for (s2, sg) in by_sgg if s2 == sd),
                      key=lambda kv: -sum(len(x["r1"]) for x in kv[1]))
        sub_rows = [(sg, region_file(sd, sg), tally(g)) for sg, g in subs]
        body = region_body(sd, group, stat, sido_rank[sd], len(sido_order), sub_rows)
        fn = region_file(sd)
        open(os.path.join(args.out, fn), "w", encoding="utf-8").write(page(
            region_title(sd, stat), region_desc(sd, stat, span),
            f"{base}/{fn}", body, base))
        written.append(fn)

    sgg_pages = 0
    for (sd, sg), group in by_sgg.items():
        stat = tally(group)
        peers = sorted(((k[1], tally(v)) for k, v in by_sgg.items() if k[0] == sd),
                       key=lambda kv: -kv[1]["r1"])
        rank = next(i + 1 for i, (n2, _) in enumerate(peers) if n2 == sg)
        body = region_body(f"{sd} {sg}", group, stat, rank, len(peers), [], parent=sd)
        fn = region_file(sd, sg)
        open(os.path.join(args.out, fn), "w", encoding="utf-8").write(page(
            region_title(f"{sd} {sg}", stat), region_desc(f"{sd} {sg}", stat, span),
            f"{base}/{fn}", body, base))
        written.append(fn)
        sgg_pages += 1

    # ---- 지역 순위 허브
    rows = [(sd, region_file(sd), sido_stats[sd]) for sd in sido_order]
    body = (f'<p class="kv"><a href="{base}/">lottoracle</a> › 지역별 로또 명당</p>'
            f"<h1>지역별 로또 1등 배출 순위</h1>"
            f'<p class="sub">{span} 기준 · 판매점 {nation["shops"]:,}곳<br>'
            f'1등 {nation["r1"]:,}회 · 2등 {nation["r2"]:,}회</p>'
            + rank_table(rows, base) + CAVEAT
            + f'<a class="cta" href="{base}/fame.html">1등을 두 번 이상 배출한 판매점 보기</a>')
    open(os.path.join(args.out, "regions.html"), "w", encoding="utf-8").write(page(
        "지역별 로또 명당 — 시·도별 1등 배출 순위",
        f"전국 시·도별 로또 1·2등 배출 횟수와 판매점 수 순위. {span} 기준 1등 {nation['r1']:,}회.",
        f"{base}/regions.html", body, base))
    written.append("regions.html")
    print(f"  지역 페이지: 시·도 {len(sido_order)}개 + 시·군·구 {sgg_pages}개 + 순위 허브 1개")

    # ---- 일본 로또
    jp_dates: dict[str, str] = {}
    for key in JP_GAMES:
        fn, text, last_date = jp_game_page(key, base)
        open(os.path.join(args.out, fn), "w", encoding="utf-8").write(text)
        written.append(fn)
        jp_dates[fn] = last_date
        draws = jp_data.load(key, jp_data.WEB_DATA_DIR)
        paged = {d.no for d in draws[-JP_DRAW_PAGES:]}
        for i in range(len(draws) - len(paged), len(draws)):
            dn, dtext = jp_draw_page(key, draws, i, base, paged)
            open(os.path.join(args.out, dn), "w", encoding="utf-8").write(dtext)
            written.append(dn)
            jp_dates[dn] = draws[i].date
    jp_dates["jp.html"] = max(jp_dates.values())
    open(os.path.join(args.out, "jp.html"), "w", encoding="utf-8").write(jp_hub_page(base, jp_dates))
    written.append("jp.html")

    # ---- 사이트맵. 크롤러가 이 페이지들을 찾아가는 지도다.
    region_urls = [f for f in written if f.startswith("region-")]
    jp_urls = (["jp.html"] + [f"jp-{k}.html" for k in JP_GAMES]
               + sorted((f for f in jp_dates if f.count("-") == 2), key=lambda f: (-int(f[:-5].rsplit("-", 1)[1]), f)))
    urls = (["", "draws.html", "fame.html", "regions.html", "about.html", "privacy.html"]
            + jp_urls + region_urls + [f"draw-{n}.html" for n in reversed(nos)])
    # lastmod 는 구글이 실제로 읽는 유일한 신호다(changefreq·priority 는 무시한다).
    # 대신 '확인해 보니 맞더라' 가 쌓여야 믿어 주므로, 확실한 곳에만 적는다.
    #   회차 페이지     그 회차 추첨일 — 이후로 내용이 안 바뀐다
    #   목록·명당·지역  최신 회차 추첨일 — 매주 회차와 배출점이 함께 갱신된다
    #   소개·개인정보   날짜를 모른다 — 모르면 안 적는다
    #   일본 로또       그 게임의 최신 추첨일 (허브는 셋 중 가장 늦은 날), 회차 페이지는 그 회차 추첨일
    date_of = {d["no"]: d.get("draw_date") or draw_date_of(d["no"]) for d in targets}
    latest = date_of[nos[-1]]

    def lastmod(u: str) -> str | None:
        if u.startswith("draw-"):
            return date_of[int(u[len("draw-"):-len(".html")])]
        if u in ("about.html", "privacy.html"):
            return None
        if u in jp_dates:
            return jp_dates[u]
        return latest

    def entry(u: str) -> str:
        prio = ("1.0" if u == "" else
                "0.8" if u in ("draws.html", "fame.html", "regions.html", "jp.html") else
                "0.5" if u.startswith("jp-") and u.count("-") == 2 else
                "0.7" if u.startswith("jp-") else
                "0.7" if u.startswith("region-") else
                "0.4" if u == "about.html" else "0.3" if u == "privacy.html" else "0.6")
        freq = ("yearly" if u.startswith("jp-") and u.count("-") == 2 else
                "daily" if u.startswith("jp") else
                "weekly" if u in ("", "draws.html", "fame.html", "regions.html") or u.startswith("region-") else "yearly")
        mod = lastmod(u)
        mod = f"<lastmod>{mod}</lastmod>" if mod else ""
        return (f"  <url><loc>{encode_url(f'{base}/{u}')}</loc>{mod}"
                f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>\n'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
               + "\n".join(entry(u) for u in urls) + "\n</urlset>\n")
    open(os.path.join(args.out, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)

    print(f"{len(written)}개 페이지 + sitemap.xml({len(urls)}개 주소) 생성 ({args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
