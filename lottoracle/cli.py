"""명령줄 인터페이스."""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__, backtest as bt, data, model, stats as stats_mod
from .engine import Engine, Options, draw_date_of
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
    if getattr(args, "input", None):
        return data.load_any(args.input)
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


def _options(args: argparse.Namespace) -> Options:
    return Options(
        lines=args.lines,
        seed=args.seed,
        strategies=tuple(args.strategy or ()),
        lucky=args.lucky,
        avoid=args.avoid,
        dream=args.dream,
        birthday=args.birthday,
        zodiac=args.zodiac,
        folklore=not args.no_folklore,
        coverage=args.coverage,
        calibrate=not args.manual_rules,
        candidates=args.candidates,
        temperature=args.temperature,
        max_overlap=args.max_overlap,
        recent_window=args.recent_window,
    )


def cmd_recommend(args: argparse.Namespace) -> int:
    engine = Engine(draws=_load(args))
    opts = _options(args)
    previous = engine.previous
    fl = opts.to_folklore()
    lines = engine.recommend(opts)

    print("=" * 72)
    print(f"  로또 6/45 추천 조합 {args.lines}줄  ·  lottoracle v{__version__}")
    print("=" * 72)
    if previous:
        print(f"기준 회차 : {previous.no}회 ({previous.draw_date or draw_date_of(previous.no)}) "
              f"{list(previous.numbers)} + 보너스 {previous.bonus}")
        print(f"목표 회차 : {previous.no + 1}회 — {draw_date_of(previous.no + 1)} (토) 추첨")
    else:
        print("기준 회차 : 없음 — 과거 데이터 없이 규칙 필터만 적용했습니다.")
    print(f"분석 회차 : {len(engine.draws)}회  ·  최근 창 {args.recent_window}회  ·  "
          f"규칙 {'실데이터 보정 ' + format(args.coverage, '.0%') if not args.manual_rules else '수동'}  ·  "
          f"후보 {args.candidates}개/줄 · 온도 {args.temperature}")
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


def cmd_import(args: argparse.Namespace) -> int:
    incoming = data.load_any(args.file)
    existing = data.load_draws(args.data, required=False)
    merged = data.merge(existing, incoming)
    data.save_draws(merged, args.data)
    newest = data.latest(merged)
    print(f"{args.file} 에서 {len(incoming)}회차를 읽어 총 {len(merged)}회차로 저장했습니다 → {args.data}")
    if newest:
        print(f"최신: {newest.no}회차 {list(newest.numbers)} + {newest.bonus}")
    return 0


def cmd_grade(args: argparse.Namespace) -> int:
    nums = args.numbers
    if len(nums) % 6:
        print(f"번호는 6개 단위로 입력하세요 (입력: {len(nums)}개)")
        return 2
    lines = [nums[i:i + 6] for i in range(0, len(nums), 6)]
    engine = Engine(draws=_load(args))
    payload = engine.grade_payload(lines, args.draw)
    d = payload["draw"]
    print(f"{d['no']}회차 ({d['date']}) 당첨번호 {d['numbers']} + 보너스 {d['bonus']}")
    for i, r in enumerate(payload["results"], start=1):
        bonus = " +보너스" if r["bonus_hit"] else ""
        print(f"{i}줄 {r['numbers']} → 일치 {r['hit']}{bonus} → {r['label']}"
              + (f" (약 {r['prize']:,}원)" if r["prize"] else ""))
    print(f"합계 약 {payload['total_prize']:,}원")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    engine = Engine(draws=_load(args))
    if len(engine.draws) < 60:
        print("백테스트에는 최소 60회차가 필요합니다.")
        return 1
    print(f"최근 {args.rounds}회차에 대해 각 회차 직전 데이터만으로 추천을 만들어 채점합니다...")
    result = engine.backtest(_options(args), rounds=args.rounds, seed=args.seed)
    print(result.render())
    print()
    print("해석: 모델과 무작위 열의 차이는 표본 오차 범위 안이어야 정상입니다. "
          "이 도구가 확률을 바꾸지 못한다는 증거로 보세요.")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from .web import serve

    engine = Engine(draws=_load(args))
    return serve(engine, host=args.host, port=args.port, open_browser=not args.no_browser)


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
    common.add_argument("--input", help="xlsx/csv/json 파일을 직접 데이터로 사용")
    common.add_argument("--offline", action="store_true", help="네트워크 수집 시도 안 함")
    common.add_argument("--recent-window", type=int, default=30, help="'핫넘버' 판정 회차 수")

    tuning = argparse.ArgumentParser(add_help=False)
    tuning.add_argument("-n", "--lines", type=int, default=5, help="추천 줄 수 (기본 5)")
    tuning.add_argument("--seed", type=int, help="난수 시드 — 재현 가능한 결과")
    tuning.add_argument(
        "--strategy",
        action="append",
        choices=[s.key for s in DEFAULT_STRATEGIES],
        help="사용할 전략 (여러 번 지정 가능, 기본은 5종 전부)",
    )
    tuning.add_argument("--lucky", type=_number_list, default=(), help="행운수 (예: --lucky '7 13')")
    tuning.add_argument("--avoid", type=_number_list, default=(), help="기피수 — 제외 (예: --avoid 4)")
    tuning.add_argument("--dream", default="", help="꿈 키워드 (예: --dream 돼지)")
    tuning.add_argument("--birthday", default="", help="생일 (예: 1990-05-21)")
    tuning.add_argument("--zodiac", default="", help="띠 또는 태어난 해 (예: 말 / 1990)")
    tuning.add_argument("--no-folklore", action="store_true", help="속설 로직 전부 끄기")
    tuning.add_argument("--coverage", type=float, default=0.8,
                        help="실데이터 보정 범위 0.5~0.99 (낮을수록 빡빡, 기본 0.8)")
    tuning.add_argument("--manual-rules", action="store_true", help="자동 보정 대신 전략별 수동 규칙 사용")
    tuning.add_argument("--candidates", type=int, default=40, help="줄당 비교할 후보 수 (기본 40)")
    tuning.add_argument("--temperature", type=float, default=1.0,
                        help="선택 온도 — 낮을수록 가장 흔한 모양만 (기본 1.0)")
    tuning.add_argument("--max-overlap", type=int, default=3, help="줄 간 최대 중복 번호 수 (기본 3)")

    sub = parser.add_subparsers(dest="command")

    rec = sub.add_parser("recommend", parents=[common, tuning], help="번호 추천 (기본 명령)")
    rec.set_defaults(func=cmd_recommend)

    imp = sub.add_parser("import", parents=[common], help="xlsx/csv 파일을 캐시에 병합")
    imp.add_argument("file", help="동행복권 엑셀(.xlsx) 또는 CSV")
    imp.set_defaults(func=cmd_import)

    grd = sub.add_parser("grade", parents=[common], help="조합 채점 (등수 판정)")
    grd.add_argument("--draw", type=int, help="채점 기준 회차 (기본: 최신 회차)")
    grd.add_argument("numbers", nargs="+", type=int, help="번호 6개 단위로 여러 줄")
    grd.set_defaults(func=cmd_grade)

    back = sub.add_parser("backtest", parents=[common, tuning], help="과거 회차로 추천 성적 검증")
    back.add_argument("--rounds", type=int, default=52, help="검증할 최근 회차 수 (기본 52)")
    back.set_defaults(func=cmd_backtest)

    gui = sub.add_parser("gui", parents=[common], help="브라우저 GUI 실행")
    gui.add_argument("--host", default="127.0.0.1")
    gui.add_argument("--port", type=int, default=8765)
    gui.add_argument("--no-browser", action="store_true", help="브라우저 자동 열기 안 함")
    gui.set_defaults(func=cmd_gui)

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
    known = {"recommend", "fetch", "stats", "check", "import", "grade", "backtest", "gui",
             "-h", "--help", "--version"}
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
