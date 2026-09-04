"""회차별 1~5등 당첨 현황을 채워 data/draws.json 을 갱신한다.

    python3 tools/backfill_prizes.py            # 빠진 회차 전부
    python3 tools/backfill_prizes.py --recent 300

회차 목록에서 '1등 N명 · 1게임당 M원' 을 곧바로 보여주려면 이 값이 미리 있어야 한다.
없으면 회차를 눌러 열 때마다 동행복권 API 를 부르게 되고, 목록에는 '-' 만 남는다.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle import data

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_OUT = os.path.join(ROOT, "web", "data", "draws.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="회차 당첨 현황 백필")
    ap.add_argument("--recent", type=int, default=0, help="최근 N회차만")
    ap.add_argument("--retries", type=int, default=4)
    args = ap.parse_args()

    draws = data.load_draws(data.DEFAULT_CACHE)
    by_no = {d.no: d for d in draws}
    latest = max(by_no)

    targets = [d.no for d in draws if not d.prizes]
    if args.recent:
        targets = [n for n in targets if n > latest - args.recent]
    targets.sort(reverse=True)          # 최근 회차부터 — 중간에 멈춰도 쓸모 있게

    if not targets:
        print("채울 회차가 없습니다.")
        return 0
    print(f"{len(targets)}개 회차 백필: {targets[0]}~{targets[-1]}")

    filled, empty, failed = 0, [], []
    for i, no in enumerate(targets, start=1):
        got = None
        for attempt in range(args.retries + 1):
            try:
                got = data.fetch_draw(no, timeout=20.0)
                break
            except Exception:
                if attempt < args.retries:
                    time.sleep(min(8.0, 1.5 * (attempt + 1)))
        if got is None:
            failed.append(no)
        elif got.prizes:
            by_no[no] = got             # 번호는 그대로, 당첨 현황이 붙은 판으로 교체
            filled += 1
        else:
            empty.append(no)            # API 가 그 회차 당첨 현황을 주지 않는다

        if i % 50 == 0 or i == len(targets):
            data.save_draws([by_no[n] for n in sorted(by_no)], data.DEFAULT_CACHE)
            print(f"  {i}/{len(targets)} · 채움 {filled} · 자료없음 {len(empty)} · 실패 {len(failed)}", flush=True)

    ordered = [by_no[n] for n in sorted(by_no)]
    data.save_draws(ordered, data.DEFAULT_CACHE)
    data.save_draws(ordered, WEB_OUT)
    have = sum(1 for d in ordered if d.prizes)
    print(f"완료: 당첨 현황 보유 {have}/{len(ordered)}회차 · 새로 채움 {filled}")
    if empty:
        print(f"API 에 자료 없음 {len(empty)}회차: {empty[:10]}{' …' if len(empty) > 10 else ''}")
    if failed:
        print(f"실패 {len(failed)}회차: {failed[:10]}{' …' if len(failed) > 10 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
