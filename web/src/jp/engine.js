/** 일본 로또 화면이 쓰는 서비스 계층. 한국판 engine.js 와 따로 둔다.
 *
 * 한 엔진이 게임 하나(로또6 / 로또7 / 미니로또)를 맡는다. 데이터는 web/data/jp/{게임}.json.
 * 당첨 확인(채점)은 넣지 않는다 — 결과는 공식 발표처와 검색으로 충분하다.
 * 무거운 계산(통계·경험분포·참조점수)은 옵션이 바뀔 때만 다시 한다.
 */
import { analysisNote, zonePhrase } from './explain.js';
import { createWishes, inPool } from './folklore.js';
import { getGame } from './games.js';
import { recommend } from './generator.js';
import { expectedSum, numberPool, summary } from './metrics.js';
import { calibrate, fit, referenceScores } from './model.js';
import { build as buildStats, cold, hot, meanFrequency, profileStats } from './stats.js';
import { byKey, strategies as allStrategies } from './strategies.js';

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
const DAY_MS = 86400000;

/** 'YYYY-MM-DD' 다음의 추첨일. 요일표만 본다(연말연시 휴무 같은 예외는 모른다). */
export function nextDrawDate(game, lastDate) {
  const [y, m, d] = String(lastDate).split('-').map(Number);
  let t = Date.UTC(y, m - 1, d);
  for (let i = 0; i < 14; i++) {
    t += DAY_MS;
    const weekday = (new Date(t).getUTCDay() + 6) % 7;      // 월=0
    if (game.weekdays.includes(weekday)) return new Date(t).toISOString().slice(0, 10);
  }
  throw new Error(`${game.name} 추첨 요일표가 비었습니다`);
}

/** 화면 폼 값을 검증된 추천 옵션으로. */
export function parseOptions(game, raw = {}) {
  const ints = v => {
    const items = Array.isArray(v) ? v : String(v ?? '').replace(/,/g, ' ').split(/\s+/);
    return [...new Set(items.filter(x => String(x).trim() !== '').map(Number))].sort((a, b) => a - b);
  };
  const num = (v, fallback) => {
    const n = Number(v);
    return Number.isFinite(n) && String(v ?? '').trim() !== '' ? n : fallback;
  };
  const avoid = ints(raw.avoid ?? []);
  const bad = avoid.filter(n => !Number.isInteger(n) || n < 1 || n > game.pool);
  if (bad.length) throw new Error(`${game.name} 번호는 1~${game.pool} 범위여야 합니다: ${bad.join(', ')}`);
  if (game.pool - avoid.length < game.pick) {
    throw new Error(`기피수를 빼면 ${game.pick}개를 고를 번호가 남지 않습니다.`);
  }
  const seed = raw.seed;
  return {
    lines: clamp(Math.trunc(num(raw.lines, 5)), 1, 10),
    seed: seed === '' || seed === null || seed === undefined ? null : Number(seed),
    strategies: raw.strategies?.length ? [...raw.strategies] : [],
    // 운세 번호는 1~45 에서 나온다. 이 게임 범위 밖은 조용히 버린다.
    lucky: inPool(game, ints(raw.lucky ?? [])),
    avoid,
    folklore: raw.folklore === undefined ? true : Boolean(raw.folklore),
    coverage: clamp(num(raw.coverage, 0.8), 0.5, 0.99),
    calibrate: raw.calibrate === undefined ? true : Boolean(raw.calibrate),
    candidates: clamp(Math.trunc(num(raw.candidates, 40)), 1, 400),
    temperature: clamp(num(raw.temperature, 1.0), 0.05, 5.0),
    maxOverlap: clamp(Math.trunc(num(raw.maxOverlap, Math.floor(game.pick / 2))), 0, game.pick),
    recentWindow: clamp(Math.trunc(num(raw.recentWindow, 30)), 5, 200),
  };
}

/** JSON 한 회차를 엔진 형식으로. 보너스는 늘 배열. */
const normalize = d => ({
  no: Number(d.no),
  date: String(d.date),
  numbers: [...d.numbers].map(Number).sort((a, b) => a - b),
  bonus: (Array.isArray(d.bonus) ? d.bonus : [d.bonus]).map(Number),
  prizes: d.prizes || [],
  carryover: d.carryover ?? -1,
});

/** raw 는 web/data/jp/{게임}.json 의 내용({game, draws}) 또는 회차 배열. */
export function createJpEngine(gameKey, raw = []) {
  const game = getGame(gameKey);
  const list = Array.isArray(raw) ? raw : (raw.draws || []);
  if (!Array.isArray(raw) && raw.game && raw.game !== game.key) {
    throw new Error(`${game.name} 엔진에 ${raw.game} 데이터를 넣었습니다`);
  }
  const draws = list.map(normalize).sort((a, b) => a.no - b.no);
  let cache = null;

  const previous = () => (draws.length ? draws[draws.length - 1] : null);
  const nextDraw = () => {
    const prev = previous();
    return prev ? { no: prev.no + 1, date: nextDrawDate(game, prev.date) } : null;
  };

  function prepare(opts) {
    const key = `${opts.recentWindow}|${opts.coverage}|${opts.calibrate}`;
    if (cache && cache.key === key) return cache;
    const stats = buildStats(game, draws, opts.recentWindow);
    const emp = draws.length ? fit(game, draws) : null;
    const reference = emp ? referenceScores(draws, emp) : [];
    const rules = opts.calibrate && draws.length ? calibrate(game, draws, opts.coverage) : null;
    cache = { key, stats, emp, reference, rules };
    return cache;
  }

  const drawPayload = d => ({
    no: d.no, date: d.date, numbers: d.numbers, bonus: d.bonus,
    prizes: d.prizes, carryover: d.carryover,
  });

  const gameInfo = () => ({
    key: game.key, name: game.name, nameJa: game.nameJa, pool: game.pool,
    pick: game.pick, bonus: game.bonus, weekdays: game.weekdays, expectedSum: expectedSum(game),
  });

  return {
    game,
    get draws() { return draws; },
    get previous() { return previous(); },
    gameInfo,
    drawPayload,

    nextDraw,

    recommendPayload(rawOptions = {}) {
      const opts = parseOptions(game, rawOptions);
      const { stats, emp, reference, rules } = prepare(opts);
      const wishes = createWishes({ lucky: opts.lucky, avoid: opts.avoid, enabled: opts.folklore });
      const prev = previous();
      const chosen = opts.strategies.length ? opts.strategies.map(k => byKey(game, k)) : allStrategies(game);
      const lines = recommend(game, stats, {
        previous: prev, strategies: chosen, lines: opts.lines, seed: opts.seed,
        wishes, emp, reference, candidates: opts.candidates,
        temperature: opts.temperature, maxOverlap: opts.maxOverlap, rulesOverride: rules,
      });
      return {
        game: gameInfo(),
        previous: prev ? drawPayload(prev) : null,
        next: nextDraw(),
        drawsUsed: draws.length,
        rules,
        seed: opts.seed,
        lucky: opts.lucky,
        avoid: opts.avoid,
        lines: lines.map((ln, i) => ({
          index: i + 1,
          strategy: ln.strategy.key,
          strategyName: ln.strategy.name,
          concept: ln.strategy.concept,
          numbers: ln.numbers,
          note: analysisNote(game, ln.numbers, ln.relaxedStep, prev, wishes),
          metrics: summary(ln.profile),
          zones: zonePhrase(game, ln.numbers),
          typicality: Number(ln.typicality.toFixed(3)),
          percentile: Number(ln.percentile.toFixed(1)),
          poolSize: ln.poolSize,
          relaxed: ln.relaxedStep,
        })),
      };
    },

    statsPayload(recentWindow = 30, coverage = 0.8) {
      if (!draws.length) return { game: gameInfo(), drawsUsed: 0 };
      const stats = buildStats(game, draws, recentWindow);
      const ps = profileStats(game, draws);
      const dist = counter => {
        const total = [...counter.values()].reduce((x, y) => x + y, 0) || 1;
        return [...counter.entries()].sort((a, b) => a[0] - b[0])
          .map(([key, count]) => ({ key, count, ratio: Number((count / total).toFixed(4)) }));
      };
      return {
        game: gameInfo(),
        drawsUsed: draws.length,
        firstNo: draws[0].no,
        firstDate: draws[0].date,
        lastNo: draws[draws.length - 1].no,
        lastDate: draws[draws.length - 1].date,
        meanSum: Number(ps.meanSum.toFixed(2)),
        sumRange80: ps.sumRange80,
        odd: dist(ps.oddDistribution),
        low: dist(ps.lowDistribution),
        ac: dist(ps.acDistribution),
        endSumMean: Number(ps.endSumMean.toFixed(2)),
        consecutiveRatio: Number(ps.consecutiveRatio.toFixed(4)),
        carryover: dist(ps.carryoverDistribution),
        frequency: numberPool(game).map(n => ({
          n, count: stats.frequency.get(n) || 0, bonus: stats.bonusFrequency.get(n) || 0,
          recent: stats.recent.get(n) || 0, gap: stats.gap.get(n),
        })),
        meanFrequency: Number(meanFrequency(stats).toFixed(2)),
        hot: hot(stats, 10),
        cold: cold(stats, 10),
        recentWindow,
        calibratedRules: calibrate(game, draws, coverage),
        coverage,
      };
    },

    drawsPayload: (limit = 20) => [...draws].reverse().slice(0, limit).map(drawPayload),
  };
}
