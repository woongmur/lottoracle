"""설날(음력 1월 1일)의 양력 날짜 표를 만든다.

    python3 tools/gen_seollal.py

띠는 음력 해를 따른다. 그래서 양력 생일로 띠를 정하려면 그해 설날보다
앞인지 뒤인지 봐야 한다. 예: 1990-01-15(양력)은 1990년 설날(1/27)보다
앞이라 말띠가 아니라 뱀띠다.

한국천문연구원 자료를 쓰는 korean_lunar_calendar 로 뽑아 표로 굳힌다.
앱은 이 표만 쓰고 라이브러리에 의존하지 않는다 (이 프로젝트는 무의존성).

    pip install korean_lunar_calendar
"""

from __future__ import annotations

import os
import sys

FIRST, LAST = 1900, 2050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build() -> dict[int, str]:
    try:
        from korean_lunar_calendar import KoreanLunarCalendar
    except ImportError:
        sys.exit("pip install korean_lunar_calendar 가 필요합니다 (생성할 때만).")
    cal = KoreanLunarCalendar()
    out = {}
    for year in range(FIRST, LAST + 1):
        if not cal.setLunarDate(year, 1, 1, False):
            sys.exit(f"{year}년 설날을 구하지 못했습니다.")
        out[year] = cal.SolarIsoFormat()
    return out


def render_py(table: dict[int, str]) -> str:
    # '01-27' 처럼 월-일만 담는다. 연도는 키로 이미 있다.
    body = "\n".join(
        f'    {y}: "{d[5:]}",' for y, d in sorted(table.items())
    )
    return f'''"""설날(음력 1월 1일)의 양력 월-일. tools/gen_seollal.py 가 만든다. 손으로 고치지 말 것."""

SEOLLAL_FIRST = {FIRST}
SEOLLAL_LAST = {LAST}

# 연도 -> 그해 설날의 양력 "MM-DD"
SEOLLAL: dict[int, str] = {{
{body}
}}
'''


def render_js(table: dict[int, str]) -> str:
    body = "\n".join(
        f"  {y}: '{d[5:]}'," for y, d in sorted(table.items())
    )
    return f'''/** 설날(음력 1월 1일)의 양력 월-일. tools/gen_seollal.py 가 만든다. 손으로 고치지 말 것. */

export const SEOLLAL_FIRST = {FIRST};
export const SEOLLAL_LAST = {LAST};

/** 연도 -> 그해 설날의 양력 'MM-DD' */
export const SEOLLAL = {{
{body}
}};
'''


def main() -> int:
    table = build()
    py = os.path.join(ROOT, "lottoracle", "seollal.py")
    js = os.path.join(ROOT, "web", "src", "seollal.js")
    for path, text in ((py, render_py(table)), (js, render_js(table))):
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(text)
        print(f"{path} ({len(table)}개 연도)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
