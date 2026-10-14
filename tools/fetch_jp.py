"""일본 로또(로또6 · 로또7 · 미니로또) 당첨번호를 받아 data/jp/*.json 으로 저장한다.

    python3 tools/fetch_jp.py                    # 세 게임 모두
    python3 tools/fetch_jp.py --game loto7       # 하나만
    python3 tools/fetch_jp.py --from-dir DIR     # 받아 둔 파일로 (네트워크 없이)

--from-dir 의 파일 이름은 '{원본}_{게임}.{csv|html}' 이다.
예: thekyo_loto6.csv, loto-life_miniloto.csv, rakuten_loto7.html

원본 셋(thekyo · loto-life · rakuten) 중 둘 이상이 같은 값을 내야 저장한다.
하나라도 어긋나면 아무것도 쓰지 않고 실패(종료 코드 1)한다.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle.jp import data
from lottoracle.jp.games import GAMES


def from_dir(folder: str):
    """URL 대신 받아 둔 파일을 돌려준다. 없으면 그 원본은 못 받은 것으로 친다."""
    where = {url: (src, game) for src, urls in data.SOURCES.items() for game, url in urls.items()}

    def fetch(url: str) -> bytes:
        src, game = where[url]
        ext = "html" if src == "rakuten" else "csv"
        p = os.path.join(folder, f"{src}_{game}.{ext}")
        if not os.path.exists(p):
            raise data.SourceError(f"파일 없음 {p}")
        with open(p, "rb") as fp:
            return fp.read()
    return fetch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--game", choices=["all", *GAMES], default="all")
    ap.add_argument("--from-dir", help="네트워크 대신 이 폴더의 파일을 읽는다")
    args = ap.parse_args(argv)

    fetch = from_dir(args.from_dir) if args.from_dir else data.download
    games = list(GAMES) if args.game == "all" else [args.game]
    failed = False
    for key in games:
        try:
            print(data.update(key, fetch=fetch).line())
        except data.SourceError as exc:
            failed = True
            print(f"{GAMES[key].name}: 실패 — {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
