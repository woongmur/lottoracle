"""회차별 1·2등 배출점을 모아 data/stores.json 으로 저장한다.

    python3 tools/fetch_stores.py --recent 100      # 최근 100회차
    python3 tools/fetch_stores.py --since 1240      # 1240회부터 (주간 갱신용)

동행복권 당첨판매점 검색 API 를 회차·등수별로 부른다. 브라우저가 방문할 때마다
수백 번 호출할 수는 없으므로, 여기서 미리 모아 정적 JSON 으로 배포한다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle import data

API = "https://www.dhlottery.co.kr/wnprchsplcsrch/selectLtWnShp.do"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "stores.json")
WEB_OUT = os.path.join(ROOT, "web", "data", "stores.json")


def fetch(draw_no: int, rank: int, timeout: float = 30.0, retries: int = 6) -> list[dict]:
    """한 회차의 rank 등 배출점 목록. 실패하면 재시도하고, 그래도 안 되면 예외."""
    url = f"{API}?srchLtEpsd={draw_no}&srchWnShpRnk={rank}"
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0", "Accept": "application/json",
                "Referer": "https://www.dhlottery.co.kr/wnprchsplcsrch/home",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            body = payload.get("data")
            return (body or {}).get("list") or []
        except Exception as exc:      # 네트워크·파싱 실패 모두 재시도
            last = exc
            if attempt < retries:
                time.sleep(min(8.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"{draw_no}회 {rank}등 조회 실패: {last}")


def load_existing() -> dict:
    if not os.path.exists(OUT):
        return {"stores": {}, "draws": []}
    with open(OUT, encoding="utf-8") as fp:
        return json.load(fp)


def save(db: dict) -> None:
    db["draws"] = sorted(set(db["draws"]))
    for path in (OUT, WEB_OUT):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(db, fp, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def absorb(db: dict, draw_no: int, rank: int, rows: list[dict]) -> int:
    """조회 결과를 판매점 단위로 합친다. 같은 가게는 회차 목록만 늘어난다."""
    added = 0
    for row in rows:
        sid = str(row.get("ltShpId") or "").strip()
        if not sid:
            continue
        store = db["stores"].setdefault(sid, {
            "name": (row.get("shpNm") or "").strip(),
            "addr": " ".join((row.get("shpAddr") or "").split()),
            "region": (row.get("region") or "").strip(),
            "lat": row.get("shpLat"),
            "lot": row.get("shpLot"),
            "kind": (row.get("atmtPsvYnTxt") or "").strip(),   # 자동/수동
            "r1": [], "r2": [],
        })
        key = "r1" if rank == 1 else "r2"
        if draw_no not in store[key]:
            store[key].append(draw_no)
            store[key].sort()
            added += 1
        # 좌표가 비어 있던 기록이면 채운다
        if store["lat"] is None and row.get("shpLat") is not None:
            store["lat"], store["lot"] = row.get("shpLat"), row.get("shpLot")
    return added


def main() -> int:
    ap = argparse.ArgumentParser(description="당첨 배출점 수집")
    ap.add_argument("--recent", type=int, default=0, help="최근 N회차")
    ap.add_argument("--since", type=int, default=0, help="이 회차부터 최신까지")
    ap.add_argument("--ranks", default="1,2", help="수집할 등수 (기본 1,2)")
    args = ap.parse_args()

    draws = data.load_draws(data.DEFAULT_CACHE)
    latest = max(d.no for d in draws)
    db = load_existing()
    done = set(db["draws"])

    if args.since:
        targets = [n for n in range(args.since, latest + 1)]
    elif args.recent:
        targets = [n for n in range(max(1, latest - args.recent + 1), latest + 1)]
    else:
        targets = [n for n in range(1, latest + 1)]
    targets = [n for n in targets if n not in done]
    ranks = [int(r) for r in args.ranks.split(",")]

    if not targets:
        print("새로 받을 회차가 없습니다.")
        return 0
    print(f"{len(targets)}개 회차 수집: {targets[0]}~{targets[-1]} (등수 {ranks})")

    failed = []
    for i, no in enumerate(targets, start=1):
        try:
            for rank in ranks:
                absorb(db, no, rank, fetch(no, rank))
            db["draws"].append(no)
        except Exception as exc:
            failed.append(no)
            print(f"  {no}회 건너뜀: {exc}")
        if i % 10 == 0 or i == len(targets):
            save(db)
            print(f"  {i}/{len(targets)} · 판매점 {len(db['stores'])}곳 저장")

    save(db)
    r1 = sum(len(s["r1"]) for s in db["stores"].values())
    r2 = sum(len(s["r2"]) for s in db["stores"].values())
    print(f"완료: 회차 {len(db['draws'])}개 · 판매점 {len(db['stores'])}곳 · 1등 {r1}건 · 2등 {r2}건")
    if failed:
        print(f"실패 {len(failed)}회차: {failed[:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
