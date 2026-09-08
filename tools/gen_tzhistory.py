"""한국 표준시가 바뀐 지점의 표를 만든다.

    python3 tools/gen_tzhistory.py

사주의 시주(時柱)는 태어난 시각으로 정해지는데, 그 시각은 '그때 시계가
가리키던 값' 이다. 그런데 한국은 표준시가 여러 번 바뀌었다.

    1908-04-01  서울 지방시 -> 동경 127.5도 (UTC+8:30)
    1912-01-01  동경 135도 (UTC+9)
    1954-03-21  동경 127.5도 (UTC+8:30)   ← 7년간
    1961-08-10  동경 135도 (UTC+9)

여기에 서머타임이 12차례 더 있다 (1948~51, 1955~60, 1987~88).
1958년처럼 UTC+8:30 위에 서머타임 1시간이 얹혀 UTC+9:30 이던 해도 있다.

이걸 무시하면 1954~61년생과 서머타임 기간 출생자의 시주가 통째로 어긋난다.
무료 만세력이 자주 빼먹는 지점이라 여기서는 제대로 다룬다.

원본은 IANA tz 데이터베이스(Asia/Seoul)다. 파이썬 표준 라이브러리 zoneinfo 로
읽어 표로 굳힌다. 브라우저도 같은 데이터를 갖고 있지만, 1970년 이전 자료까지
정확한지는 브라우저마다 확인해야 하므로 실행 중에 브라우저를 믿지 않는다.
표로 굳혀 두면 파이썬과 JS 가 같은 값을 쓰고 골든 데이터로 교차검증도 된다.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

FIRST, LAST = 1900, 2050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KST = ZoneInfo("Asia/Seoul")


def build() -> list[tuple[int, int]]:
    """[(전환 시각 epoch 초, 그 뒤의 UTC 오프셋 초), ...] 를 시간순으로."""
    def offset(dt: datetime) -> int:
        return int(dt.astimezone(KST).utcoffset().total_seconds())

    cur = datetime(FIRST, 1, 1, tzinfo=timezone.utc)
    end = datetime(LAST + 1, 1, 1, tzinfo=timezone.utc)
    prev = offset(cur)
    out: list[tuple[int, int]] = [(int(cur.timestamp()), prev)]
    while cur < end:
        nxt = cur + timedelta(days=1)
        cand = offset(nxt)
        if cand != prev:
            # 하루 안에서 분 단위까지 좁힌다
            lo, hi = cur, nxt
            while (hi - lo) > timedelta(minutes=1):
                mid = lo + (hi - lo) / 2
                if offset(mid) == prev:
                    lo = mid
                else:
                    hi = mid
            out.append((int(hi.timestamp()), cand))
            prev = cand
        cur = nxt
    return out


HEADER = (
    "한국 표준시 전환 표. tools/gen_tzhistory.py 가 IANA tz(Asia/Seoul)에서 만든다.\n"
    " * 손으로 고치지 말 것.\n"
    " *\n"
    " * 각 항목은 (전환이 일어난 UTC epoch 초, 그 시점 이후의 UTC 오프셋 초).\n"
    " * 첫 항목은 표의 시작점이라 전환이 아니라 초기 상태다."
)


def render_py(rows: list[tuple[int, int]]) -> str:
    body = "\n".join(f"    ({t}, {o})," for t, o in rows)
    return f'''"""{HEADER.replace(" * ", "").replace(" *", "")}"""

TZ_FIRST_YEAR = {FIRST}
TZ_LAST_YEAR = {LAST}

# (전환 UTC epoch 초, 그 뒤의 UTC 오프셋 초)
KST_TRANSITIONS: list[tuple[int, int]] = [
{body}
]
'''


def render_js(rows: list[tuple[int, int]]) -> str:
    body = "\n".join(f"  [{t}, {o}]," for t, o in rows)
    return f'''/** {HEADER}
 */

export const TZ_FIRST_YEAR = {FIRST};
export const TZ_LAST_YEAR = {LAST};

/** [전환 UTC epoch 초, 그 뒤의 UTC 오프셋 초] */
export const KST_TRANSITIONS = [
{body}
];
'''


def main() -> int:
    rows = build()
    py = os.path.join(ROOT, "lottoracle", "tzhistory.py")
    js = os.path.join(ROOT, "web", "src", "tzhistory.js")
    for path, text in ((py, render_py(rows)), (js, render_js(rows))):
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(text)
        print(f"{path} ({len(rows)}개 항목)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
