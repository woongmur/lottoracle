"""JS 이식 검증용 골든 데이터 생성 — 파이썬 계산 결과를 JSON 으로 떨군다.

    python3 tools/gen_golden.py

JS 테스트가 같은 입력에 같은 값을 내는지 대조한다. 난수가 개입하는 부분(추천 생성)은
값이 아니라 성질(결정론·범위·규칙 통과)만 검증하므로 여기 담지 않는다.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lottoracle import data, filters, metrics, model, stats

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "web", "test", "golden")

# 검증용 조합: 실제 당첨조합 + 경계값 + 극단적인 모양
SAMPLES = [
    [11, 13, 22, 32, 33, 36],   # 1239회
    [10, 23, 29, 33, 37, 40],   # 1회
    [1, 2, 3, 4, 5, 6],         # 최소
    [40, 41, 42, 43, 44, 45],   # 최대
    [1, 3, 5, 7, 9, 11],        # 전부 홀수
    [2, 4, 6, 8, 10, 12],       # 전부 짝수
    [11, 22, 33, 44, 1, 45],    # 쌍둥이수
    [3, 13, 23, 33, 43, 5],     # 같은 끝수 다수
    [1, 2, 3, 43, 44, 45],      # 양극단
    [7, 14, 21, 28, 35, 42],    # 전부 7배수
    [5, 12, 19, 26, 31, 38],    # 평범
    [45, 1, 23, 22, 8, 17],     # 정렬 안 된 입력
]
PREVIOUS = [11, 13, 22, 32, 33, 36]


def dump(name: str, payload) -> None:
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"  {name}")


def profile_dict(p) -> dict:
    return {
        "numbers": list(p.numbers), "total": p.total, "odd": p.odd, "even": p.even,
        "low": p.low, "high": p.high, "zones": list(p.zones), "ac": p.ac,
        "maxRun": p.max_run, "consecutive": p.consecutive, "endSum": p.end_sum,
        "sameEnding": p.same_ending, "mult3": p.mult3, "spread": p.spread,
        "carryover": p.carryover, "summary": p.summary(),
    }


def rules_dict(r: filters.Ruleset) -> dict:
    return {
        "sumRange": list(r.sum_range), "oddRange": list(r.odd_range),
        "lowRange": list(r.low_range), "acMin": r.ac_min, "maxRun": r.max_run,
        "maxConsecutivePairs": r.max_consecutive_pairs, "maxPerZone": r.max_per_zone,
        "minZones": r.min_zones, "endSumRange": list(r.end_sum_range),
        "maxSameEnding": r.max_same_ending, "mult3Range": list(r.mult3_range),
        "spreadMin": r.spread_min, "carryoverRange": list(r.carryover_range),
        "forbidAllSameParity": r.forbid_all_same_parity,
    }


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    draws = data.load_draws(data.DEFAULT_CACHE)
    print(f"회차 {len(draws)}개로 골든 데이터 생성 → web/test/golden/")

    # 1) 지표
    dump("metrics.json", {
        "previous": PREVIOUS,
        "cases": [
            {"numbers": s, "noPrev": profile_dict(metrics.profile(s)),
             "withPrev": profile_dict(metrics.profile(s, PREVIOUS))}
            for s in SAMPLES
        ],
    })

    # 2) 필터 (기본 규칙 + 완화 1~3단계)
    base = filters.Ruleset()
    dump("filters.json", {
        "base": rules_dict(base),
        "relaxed": {str(step): rules_dict(base.relaxed(step)) for step in (1, 2, 3)},
        "cases": [
            {
                "numbers": s,
                "verdict": {
                    "ok": (v := filters.check(s, base, PREVIOUS)).ok,
                    "violations": v.violations,
                },
            }
            for s in SAMPLES
        ],
    })

    # 3) 번호 통계 (최근 30회 창)
    st = stats.build(draws, recent_window=30)
    ps = stats.profile_stats(draws)
    dump("stats.json", {
        "drawsUsed": st.draws_used,
        "recentWindow": st.recent_window,
        "meanFrequency": st.mean_frequency,
        "frequency": {str(n): st.frequency.get(n, 0) for n in metrics.NUMBER_POOL},
        "recent": {str(n): st.recent.get(n, 0) for n in metrics.NUMBER_POOL},
        "gap": {str(n): st.gap[n] for n in metrics.NUMBER_POOL},
        "bonusFrequency": {str(n): st.bonus_frequency.get(n, 0) for n in metrics.NUMBER_POOL},
        "hot10": [list(x) for x in st.hot(10)],
        "cold10": [list(x) for x in st.cold(10)],
        "companionsOf7": [list(x) for x in st.companions(7, 6)],
        "pairSamples": {
            f"{a}-{b}": st.pairs[frozenset((a, b))]
            for a, b in [(1, 2), (7, 13), (11, 22), (33, 36), (44, 45), (3, 17)]
        },
        "profileStats": {
            "count": ps.count,
            "meanSum": ps.mean_sum,
            "sumRange80": list(ps.sum_range_80),
            "oddDistribution": {str(k): v for k, v in sorted(ps.odd_distribution.items())},
            "lowDistribution": {str(k): v for k, v in sorted(ps.low_distribution.items())},
            "acDistribution": {str(k): v for k, v in sorted(ps.ac_distribution.items())},
            "endSumMean": ps.end_sum_mean,
            "consecutiveRatio": ps.consecutive_ratio,
            "carryoverDistribution": {str(k): v for k, v in sorted(ps.carryover_distribution.items())},
        },
    })

    # 4) 보정 규칙과 전형성 점수
    emp = model.fit(draws)
    ref = model.reference_scores(draws, emp)
    dump("model.json", {
        "empCount": emp.count,
        "calibrated": {f"{c:.2f}": rules_dict(model.calibrate(draws, c)) for c in (0.6, 0.8, 0.9, 0.95)},
        "probes": {
            "pTotal": {str(v): emp.p_total(v) for v in (60, 100, 138, 175, 240)},
            "pOdd": {str(v): emp.p_odd(v) for v in range(7)},
            "pLow": {str(v): emp.p_low(v) for v in range(7)},
            "pAc": {str(v): emp.p_ac(v) for v in range(11)},
            "pEndSum": {str(v): emp.p_end_sum(v) for v in (5, 15, 25, 35, 45)},
            "pConsecutive": {str(v): emp.p_consecutive(v) for v in range(6)},
            "pCarryover": {str(v): emp.p_carryover(v) for v in range(7)},
            "pSpread": {str(v): emp.p_spread(v) for v in (10, 20, 30, 40, 44)},
            "pZone": {
                "0-1-1-2-2": emp.p_zone([0, 1, 1, 2, 2]),
                "6-0-0-0-0": emp.p_zone([6, 0, 0, 0, 0]),
                "1-1-1-1-2": emp.p_zone([1, 1, 1, 1, 2]),
            },
            "pPosition": {f"{i}-{n}": emp.p_position(i, n) for i, n in [(0, 1), (0, 20), (5, 45), (5, 10), (3, 30)]},
        },
        "typicality": [
            {"numbers": s,
             "noPrev": model.typicality(s, emp),
             "withPrev": model.typicality(s, emp, PREVIOUS),
             "percentile": model.typicality_percentile(model.typicality(s, emp, PREVIOUS), ref)}
            for s in SAMPLES
        ],
        "referenceStats": {
            "count": len(ref), "min": ref[0], "max": ref[-1],
            "median": ref[len(ref) // 2],
        },
    })
    print("완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
