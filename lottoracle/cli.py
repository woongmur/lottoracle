"""명령줄 인터페이스."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__, data, stats as stats_mod
from .data import Draw
from .explain import render_line
from .filters import Ruleset, check as check_combo
from .folklore import Folklore
from .generator import recommend
from .metrics import NUMBER_POOL
from .strategies import DEFAULT_STRATEGIES, by_key

DISCLAIMER = (
    "※ 로또는 매 회차 독립적인 무작위 추첨입니다. 1등 확률은 1/8,145,060로 고정되어 있고,\n"
    "   이 프로그램의 통계·속설 로직은 그 확률을 단 1%도 바꾸지 못합니다. 재미로만 쓰세요.\n"
    "   지출은 잃어도 괜찮은 금액까지만. 도박문제 상담 국번없이 1336."
)


def _number_list(text: str) -> tuple[int, ...]:
    if not text:
        return ()
    out = []
    for token in text.replace(",", " ").split():
        n = int(token)
        if n not in NUMBER_POOL:
            raise argparse.ArgumentTypeError(f"번호는 1~45여야 합니다: {n}")
        out.append(n)
    return tuple(sorted(set(out)))


def _load(args: argparse.Namespace) -> list[Draw]:
    if getattr(args, "csv", None):
        return data.load_csv(args.csv)
    draws = data.load_draws(args.data, required=False)
    if not draws and not getattr(args, "offline", False):
        print("데이터 캐시가 비어 있습니다. 동행복권에서 내려받는 중...", file=sys.stderr)
        try:
            draws = data.update_cache(args.data)
        except Exception as exc:  # 네트워크 차단 환경에서도 계속 진행한다
            print(f"  → 수집 실패({exc}). 통계 없이 규칙 필터만으로 진행합니다.", file=sys.stderr)
    return draws


def _folklore(args: argparse.Namespace) -> Folklore:
    return Folklore(
        enabled=not args.no_folklore,
        lucky=args.lucky,
        avoid=args.avoid,
        dream=args.dream,
        birthday=args.birthday,
        zodiac=args.zodiac,
    )


# ------------------------------------------------------------------- 명령들

def cmd_fetch(args: argparse.Namespace) -> int:
    draws = data.update_cache(args.data)
    newest = data.latest(draws)
    print(f"총 {len(draws)}회차 저장 완료 → {args.data}")
    if newest:
        print(f"최신: {newest.no}회차 ({newest.draw_date}) {list(newest.numbers)} + {newest.bonus}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    draws = _load(args)
    if not draws:
        print("분석할 데이터가 없습니다. `fetch`를 먼저 실행하거나 --csv를 지정하세요.")
        return 1
    st = stats_mod.build(draws, recent_window=args.recent_window)
    print("=== 대한민국 로또 6/45 평균치 ===")
    print(stats_mod.profile_stats(draws).render())
    print()
    print(f"최근 {args.recent_window}회 다출현(핫) : "
          + ", ".join(f"{n}({c}회)" for n, c in st.hot(10)))
    print("장기 미출현(콜드)      : "
          + ", ".join(f"{n}({g}회차째)" for n, g in st.cold(10)))
    print("전체 다출현            : "
          + ", ".join(f"{n}({c}회)" for n, c in st.frequency.most_common(10)))
    print("전체 소출현            : "
          + ", ".join(f"{n}({c}회)" for n, c in st.frequency.most_common()[-10:]))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    nums = args.numbers
    if len(nums) != 6:
        print(f"번호 6개를 입력하세요 (입력: {len(nums)}개)")
        return 2
    draws = _load(args)
    previous = data.latest(draws)
    verdict = check_combo(nums, Ruleset(), previous.numbers if previous else ())
    print(f"조합: {list(nums)}")
    print(f"지표: {verdict.profile.summary()}")
    if verdict.ok:
        print("판정: 평균치 필터 통과 ✓")
    else:
        print("판정: 탈락 ✗ — " + ", ".join(verdict.violations))
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    draws = _load(args)
    previous = data.latest(draws)
    st = stats_mod.build(draws, recent_window=args.recent_window)
    fl = _folklore(args)

    strategies = (
        tuple(by_key(k) for k in args.strategy) if args.strategy else DEFAULT_STRATEGIES
    )
    lines = recommend(
        st,
        previous=previous,
        strategies=strategies,
        lines=args.lines,
        seed=args.seed,
        folklore=fl,
    )

    print("=" * 72)
    print(f"  로또 6/45 추천 조합 {args.lines}줄  ·  lottoracle v{__version__}")
    print("=" * 72)
    if previous:
        print(f"기준 회차 : {previous.no}회 ({previous.draw_date}) "
              f"{list(previous.numbers)} + 보너스 {previous.bonus}")
        print(f"다음 추첨 : {data.next_draw_date()} (토)")
    else:
        print("기준 회차 : 없음 — 과거 데이터 없이 규칙 필터만 적용했습니다.")
    print(f"분석 회차 : {st.draws_used}회  ·  최근 창 {args.recent_window}회")
    notes = fl.describe() if fl.enabled else ["속설 로직 끔(--no-folklore)"]
    print("속설 설정 : " + (" | ".join(notes) if notes else "기본값"))
    if args.seed is not None:
        print(f"시드      : {args.seed} (같은 시드 = 같은 결과)")
    print("-" * 72)

    for i, line in enumerate(lines, start=1):
        print(render_line(i, line, previous, fl))
        print()

    print("-" * 72)
    print(DISCLAIMER)
    return 0


# --------------------------------------------------------------------- 파서

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lottoracle",
        description="한국 로또 6/45 번호 추천기 — 통계 필터 + 민간속설 가중치 (예측 아님)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=DISCLAIMER,
    )
    parser.add_argument("--version", action="version", version=f"lottoracle {__version__}")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", default=data.DEFAULT_CACHE, help="캐시 파일 경로")
    common.add_argument("--csv", help="CSV로 회차 데이터 직접 입력 (회차,n1..n6,보너스)")
    common.add_argument("--offline", action="store_true", help="네트워크 수집 시도 안 함")
    common.add_argument("--recent-window", type=int, default=30, help="'핫넘버' 판정 회차 수")

    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("recommend", parents=[common], help="번호 추천 (기본 명령)")
    rec.add_argument("-n", "--lines", type=int, default=5, help="추천 줄 수 (기본 5)")
    rec.add_argument("--seed", type=int, help="난수 시드 — 재현 가능한 결과")
    rec.add_argument(
        "--strategy",
        action="append",
        choices=[s.key for s in DEFAULT_STRATEGIES],
        help="사용할 전략 (여러 번 지정 가능, 기본은 5종 전부)",
    )
    rec.add_argument("--lucky", type=_number_list, default=(), help="행운수 (예: --lucky '7 13')")
    rec.add_argument("--avoid", type=_number_list, default=(), help="기피수 — 제외 (예: --avoid 4)")
    rec.add_argument("--dream", default="", help="꿈 키워드 (예: --dream 돼지)")
    rec.add_argument("--birthday", default="", help="생일 (예: 1990-05-21)")
    rec.add_argument("--zodiac", default="", help="띠 또는 태어난 해 (예: 말 / 1990)")
    rec.add_argument("--no-folklore", action="store_true", help="속설 로직 전부 끄기")
    rec.set_defaults(func=cmd_recommend)

    fetch = sub.add_parser("fetch", parents=[common], help="동행복권에서 회차 데이터 수집")
    fetch.set_defaults(func=cmd_fetch)

    stat = sub.add_parser("stats", parents=[common], help="과거 회차 통계 요약")
    stat.set_defaults(func=cmd_stats)

    chk = sub.add_parser("check", parents=[common], help="내 조합이 평균치 안에 드는지 검사")
    chk.add_argument("numbers", nargs="+", type=int, help="번호 6개")
    chk.set_defaults(func=cmd_check)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    known = {"recommend", "fetch", "stats", "check", "-h", "--help", "--version"}
    if not argv or argv[0] not in known:
        argv.insert(0, "recommend")  # 서브명령 생략 시 recommend
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
