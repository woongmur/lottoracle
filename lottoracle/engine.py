"""CLI와 GUI가 함께 쓰는 서비스 계층. 데이터 로드 → 통계/모델 준비 → 추천/채점/백테스트."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Sequence

from . import __version__, backtest as bt, data, model, qr as qr_mod, stats as stats_mod
from .data import Draw
from .explain import analysis_note, zone_phrase
from .folklore import Folklore, color_signature, ball_color
from .fortune import Profile, daily_fortune, zodiac_table
from .store import UserStore
from .generator import Line, recommend
from .metrics import NUMBER_POOL
from .strategies import DEFAULT_STRATEGIES, by_key


def draw_date_of(no: int) -> str:
    """회차 번호로 추첨일을 계산한다 (1회차 2002-12-07, 매주 토요일)."""
    return (data.FIRST_DRAW_DATE + timedelta(weeks=no - 1)).isoformat()


@dataclass
class Options:
    """추천 옵션 한 묶음. CLI 인자/GUI 폼이 이걸로 변환된다."""

    lines: int = 5
    seed: int | None = None
    strategies: tuple[str, ...] = ()
    lucky: tuple[int, ...] = ()
    avoid: tuple[int, ...] = ()
    dream: str = ""
    birthday: str = ""
    zodiac: str = ""
    folklore: bool = True
    coverage: float = 0.80         # 실데이터 보정 범위 (0.6 빡빡 ~ 0.95 느슨)
    calibrate: bool = True         # False 면 전략별 수동 규칙 사용
    candidates: int = 40
    temperature: float = 1.0
    max_overlap: int = 3
    recent_window: int = 30

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Options":
        def ints(v: Any) -> tuple[int, ...]:
            if isinstance(v, (list, tuple)):
                items = v
            else:
                items = str(v or "").replace(",", " ").split()
            out = sorted({int(x) for x in items if str(x).strip()})
            bad = [n for n in out if n not in NUMBER_POOL]
            if bad:
                raise ValueError(f"번호는 1~45 범위여야 합니다: {bad}")
            return tuple(out)

        seed = raw.get("seed")
        return cls(
            lines=max(1, min(20, int(raw.get("lines", 5) or 5))),
            seed=int(seed) if seed not in (None, "", "null") else None,
            strategies=tuple(raw.get("strategies") or ()),
            lucky=ints(raw.get("lucky", ())),
            avoid=ints(raw.get("avoid", ())),
            dream=str(raw.get("dream", "") or ""),
            birthday=str(raw.get("birthday", "") or ""),
            zodiac=str(raw.get("zodiac", "") or ""),
            folklore=bool(raw.get("folklore", True)),
            coverage=max(0.5, min(0.99, float(raw.get("coverage", 0.8) or 0.8))),
            calibrate=bool(raw.get("calibrate", True)),
            candidates=max(1, min(400, int(raw.get("candidates", 40) or 40))),
            temperature=max(0.05, min(5.0, float(raw.get("temperature", 1.0) or 1.0))),
            max_overlap=max(0, min(6, int(raw.get("max_overlap", 3) or 3))),
            recent_window=max(5, min(200, int(raw.get("recent_window", 30) or 30))),
        )

    def to_folklore(self) -> Folklore:
        return Folklore(
            enabled=self.folklore,
            lucky=self.lucky,
            avoid=self.avoid,
            dream=self.dream,
            birthday=self.birthday,
            zodiac=self.zodiac,
        )


@dataclass
class Engine:
    draws: list[Draw] = field(default_factory=list)
    path: str = data.DEFAULT_CACHE            # 회차 캐시 파일 (refresh 가 여기에 이어 쓴다)
    store: UserStore = field(default_factory=UserStore)  # 프로필·내 번호·설정

    # ---------------------------------------------------------- 준비
    @classmethod
    def load(cls, path: str | None = None, offline: bool = True) -> "Engine":
        path = path or data.DEFAULT_CACHE
        draws = data.load_any(path) if path != data.DEFAULT_CACHE else data.load_draws(path, required=False)
        if not draws and not offline:
            draws = data.update_cache(path)
        return cls(draws=draws, path=path)

    @property
    def previous(self) -> Draw | None:
        return data.latest(self.draws)

    def refresh(self, timeout: float = 10.0) -> dict[str, Any]:
        """동행복권에서 새 회차만 이어받아 캐시와 메모리를 갱신한다."""
        if not self.path.lower().endswith(".json"):
            raise ValueError("xlsx/csv 입력으로 실행 중에는 온라인 갱신을 할 수 없습니다.")
        before = self.previous.no if self.previous else 0
        self.draws = data.update_cache(self.path, timeout=timeout)
        after = self.previous.no if self.previous else 0
        return {
            "before": before,
            "after": after,
            "added": max(0, after - before),
            "previous": self.draw_payload(self.previous) if self.previous else None,
        }

    def prepare(self, opts: Options):
        st = stats_mod.build(self.draws, recent_window=opts.recent_window)
        emp = model.fit(self.draws) if self.draws else None
        ref = model.reference_scores(self.draws, emp) if emp else []
        rules = model.calibrate(self.draws, opts.coverage) if (opts.calibrate and self.draws) else None
        return st, emp, ref, rules

    # ---------------------------------------------------------- 추천
    def recommend(self, opts: Options) -> list[Line]:
        st, emp, ref, rules = self.prepare(opts)
        strategies = tuple(by_key(k) for k in opts.strategies) if opts.strategies else DEFAULT_STRATEGIES
        return recommend(
            st,
            previous=self.previous,
            strategies=strategies,
            lines=opts.lines,
            seed=opts.seed,
            folklore=opts.to_folklore(),
            emp=emp,
            reference=ref,
            candidates=opts.candidates,
            temperature=opts.temperature,
            max_overlap=opts.max_overlap,
            rules_override=rules,
        )

    def recommend_payload(self, opts: Options) -> dict[str, Any]:
        lines = self.recommend(opts)
        fl = opts.to_folklore()
        prev = self.previous
        _, _, _, rules = self.prepare(opts)
        return {
            "version": __version__,
            "previous": self.draw_payload(prev) if prev else None,
            "next_draw_no": (prev.no + 1) if prev else None,
            "next_draw_date": draw_date_of(prev.no + 1) if prev else None,
            "draws_used": len(self.draws),
            "folklore": fl.describe() if fl.enabled else ["속설 로직 끔"],
            "rules": rules.__dict__ if rules else None,
            "seed": opts.seed,
            "lines": [
                {
                    "index": i,
                    "strategy": ln.strategy.key,
                    "strategy_name": ln.strategy.name,
                    "concept": ln.strategy.concept,
                    "numbers": list(ln.numbers),
                    "bonus": ln.bonus,
                    "colors": [ball_color(n) for n in ln.numbers],
                    "bonus_color": ball_color(ln.bonus),
                    "note": analysis_note(ln, prev, fl),
                    "metrics": ln.profile.summary(),
                    "zones": zone_phrase(ln.numbers),
                    "omens": ln.omens,
                    "luck": ln.luck,
                    "typicality": round(ln.typicality, 3),
                    "percentile": round(ln.percentile, 1),
                    "pool_size": ln.pool_size,
                    "relaxed": ln.relaxed_step,
                }
                for i, ln in enumerate(lines, start=1)
            ],
        }

    # ---------------------------------------------------------- 통계
    @staticmethod
    def draw_payload(d: Draw) -> dict[str, Any]:
        return {
            "no": d.no,
            "date": d.draw_date or draw_date_of(d.no),
            "numbers": list(d.numbers),
            "bonus": d.bonus,
            "colors": [ball_color(n) for n in d.numbers],
            "bonus_color": ball_color(d.bonus),
            "first_winners": d.first_winners,
            "first_prize": d.first_prize,
        }

    def stats_payload(self, recent_window: int = 30, coverage: float = 0.8) -> dict[str, Any]:
        if not self.draws:
            return {"draws_used": 0}
        st = stats_mod.build(self.draws, recent_window=recent_window)
        ps = stats_mod.profile_stats(self.draws)
        rules = model.calibrate(self.draws, coverage)

        def dist(counter) -> list[dict]:
            total = sum(counter.values()) or 1
            return [{"key": k, "count": v, "ratio": round(v / total, 4)} for k, v in sorted(counter.items())]

        return {
            "draws_used": len(self.draws),
            "first_no": self.draws[0].no,
            "last_no": self.draws[-1].no,
            "mean_sum": round(ps.mean_sum, 2),
            "sum_range_80": list(ps.sum_range_80),
            "odd": dist(ps.odd_distribution),
            "low": dist(ps.low_distribution),
            "ac": dist(ps.ac_distribution),
            "end_sum_mean": round(ps.end_sum_mean, 2),
            "consecutive_ratio": round(ps.consecutive_ratio, 4),
            "carryover": dist(ps.carryover_distribution),
            "frequency": [{"n": n, "count": st.frequency.get(n, 0), "bonus": st.bonus_frequency.get(n, 0),
                           "recent": st.recent.get(n, 0), "gap": st.gap.get(n, 0), "color": ball_color(n)}
                          for n in NUMBER_POOL],
            "mean_frequency": round(st.mean_frequency, 2),
            "hot": st.hot(10),
            "cold": st.cold(10),
            "recent_window": recent_window,
            "calibrated_rules": rules.__dict__,
            "coverage": coverage,
        }

    def draws_payload(self, limit: int = 20) -> list[dict[str, Any]]:
        return [self.draw_payload(d) for d in sorted(self.draws, key=lambda d: -d.no)[:limit]]

    # ---------------------------------------------------------- 채점
    def find_draw(self, no: int | None) -> Draw | None:
        if no is None:
            return self.previous
        return next((d for d in self.draws if d.no == no), None)

    def grade_payload(self, lines: Sequence[Sequence[int]], draw_no: int | None = None) -> dict[str, Any]:
        draw = self.find_draw(draw_no)
        if draw is None:
            raise ValueError(f"{draw_no}회차 데이터가 없습니다.")
        graded = bt.grade(lines, draw)
        return {
            "draw": self.draw_payload(draw),
            "results": [
                {"numbers": list(g.numbers), "hit": list(g.hit), "bonus_hit": g.bonus_hit,
                 "rank": g.rank, "label": g.label, "prize": g.prize}
                for g in graded
            ],
            "total_prize": sum(g.prize for g in graded),
        }

    # ---------------------------------------------------------- 운세 · 프로필
    def fortune_payload(self, profile: Profile | None = None, today: date | None = None) -> dict[str, Any]:
        profile = self.store.load_profile() if profile is None else profile
        f = daily_fortune(profile, today)
        prev = self.previous
        return {
            "profile": profile.to_dict(),
            "has_profile": not profile.is_empty,
            "fortune": f.to_dict(),
            "recommend_inputs": profile.recommend_inputs(today) if not profile.is_empty else None,
            "zodiac_table": zodiac_table(today, exclude=profile.zodiac),
            "next_draw_no": (prev.no + 1) if prev else None,
            "next_draw_date": draw_date_of(prev.no + 1) if prev else None,
        }

    # ---------------------------------------------------------- QR 당첨 확인
    def qr_payload(self, text: str) -> dict[str, Any]:
        """로또 용지 QR 을 읽어 그 자리에서 채점한다.

        아직 추첨 전이거나 캐시에 없는 회차면 조합만 돌려주고 status 로 알린다.
        """
        ticket = qr_mod.parse(text)
        draw = self.find_draw(ticket.draw_no)
        out: dict[str, Any] = {
            "ticket": ticket.to_dict(),
            "draw_date": draw_date_of(ticket.draw_no),
            "colors": [[ball_color(n) for n in row] for row in ticket.lines],
        }
        if draw is None:
            newest = self.previous
            out["status"] = "pending" if (newest and ticket.draw_no > newest.no) else "missing"
            out["latest_draw"] = newest.no if newest else None
            return out

        graded = bt.grade(ticket.lines, draw)
        ranks = [g.rank for g in graded if g.rank]
        out.update({
            "status": "graded",
            "draw": self.draw_payload(draw),
            "results": [
                {"numbers": list(g.numbers), "hit": list(g.hit), "bonus_hit": g.bonus_hit,
                 "rank": g.rank, "label": g.label, "prize": g.prize}
                for g in graded
            ],
            "best_rank": min(ranks) if ranks else 0,
            "total_prize": sum(g.prize for g in graded),
        })
        return out

    # ---------------------------------------------------------- 내 번호
    def picks_payload(self) -> list[dict[str, Any]]:
        """저장한 조합 목록. 목표 회차가 추첨됐으면 자동으로 채점해 붙인다."""
        out = []
        for p in sorted(self.store.list_picks(), key=lambda r: (r.get("target_draw", 0), r.get("saved_at", "")), reverse=True):
            item = dict(p)
            draw = self.find_draw(int(p.get("target_draw", 0)))
            item["draw_date"] = draw_date_of(int(p.get("target_draw", 0)))
            if draw is not None:
                graded = bt.grade(p["lines"], draw)
                item["draw"] = self.draw_payload(draw)
                item["results"] = [
                    {"numbers": list(g.numbers), "hit": list(g.hit), "bonus_hit": g.bonus_hit,
                     "rank": g.rank, "label": g.label, "prize": g.prize}
                    for g in graded
                ]
                ranks = [g.rank for g in graded if g.rank]
                item["best_rank"] = min(ranks) if ranks else 0
                item["total_prize"] = sum(g.prize for g in graded)
            else:
                item["draw"] = None
                item["results"] = None
            item["colors"] = [[ball_color(n) for n in row] for row in p["lines"]]
            out.append(item)
        return out

    # ---------------------------------------------------------- 백테스트
    def backtest(self, opts: Options, rounds: int = 52, seed: int | None = None) -> bt.BacktestResult:
        strategies = tuple(by_key(k) for k in opts.strategies) if opts.strategies else DEFAULT_STRATEGIES
        fl = opts.to_folklore()

        def recommender(history: Sequence[Draw], rng: random.Random) -> list[tuple[int, ...]]:
            st = stats_mod.build(history, recent_window=opts.recent_window)
            emp = model.fit(history)
            rules = model.calibrate(history, opts.coverage) if opts.calibrate else None
            lines = recommend(
                st, previous=history[-1], strategies=strategies, lines=opts.lines,
                seed=rng.random(), folklore=fl, emp=emp, reference=(),
                candidates=min(opts.candidates, 15), temperature=opts.temperature,
                max_overlap=opts.max_overlap, rules_override=rules,
            )
            return [ln.numbers for ln in lines]

        return bt.run(self.draws, recommender, rounds=rounds, lines_per_round=opts.lines, seed=seed)

    def backtest_payload(self, opts: Options, rounds: int = 52, seed: int | None = None) -> dict[str, Any]:
        r = self.backtest(opts, rounds=rounds, seed=seed)
        return {
            "rounds": r.rounds,
            "lines_per_round": r.lines_per_round,
            "tickets": r.tickets,
            "spent": r.spent,
            "rows": r.summary_rows(),
            "model_prize": r.model_prize,
            "random_prize": r.random_prize,
            "model_roi": round(r.model_prize / r.spent, 4) if r.spent else 0,
            "random_roi": round(r.random_prize / r.spent, 4) if r.spent else 0,
            "best": [{"no": no, "rank": bt.RANK_LABEL[rk], "numbers": list(c)}
                     for no, rk, c in sorted(r.best_model, key=lambda t: t[1])[:10]],
            "text": r.render(),
        }
