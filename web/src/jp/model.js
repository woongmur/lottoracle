/** 일본 로또 실데이터로 필터를 보정하고 '전형성'을 점수화한다. 파이썬 lottoracle/jp/model.py 와 같다.
 *
 * 한국판 model.js 와 같은 방식. 평활(라플라스)에 쓰는 '나올 수 있는 값의 개수'만
 * 게임마다 계산한다. 전형성은 확률과 무관하다 — 모든 조합은 똑같은 확률로 나온다.
 */
import { defaultWeights, quantile, roundHalfEven, typicalityPercentile } from '../model.js';
import { defaultRules } from './filters.js';
import { maxAc, maxSum, profile } from './metrics.js';

export { defaultWeights, quantile, roundHalfEven, typicalityPercentile };

// 정렬한 구간 분포가 나올 수 있는 가짓수. 모든 조합을 세어 얻은 값.
const ZONE_PATTERNS = { loto6: 10, loto7: 11, miniloto: 6 };

export function supports(game) {
  const k = game.pick;
  return {
    total: Math.floor(maxSum(game) / 5) + 1,
    odd: k + 1,
    low: k + 1,
    ac: maxAc(game) + 1,
    endSum: Math.floor((9 * k) / 3) + 1,
    consecutive: k,
    zone: ZONE_PATTERNS[game.key],
    carryover: k + 1,
    spread: Math.floor((game.pool - 1) / 4) + 1,
    position: game.pool,
  };
}

const inc = (map, key) => map.set(key, (map.get(key) || 0) + 1);
const zoneKey = zones => [...zones].sort((a, b) => a - b).join(',');

export function fit(game, draws) {
  const ordered = [...draws].sort((a, b) => a.no - b.no);
  const emp = {
    game,
    support: supports(game),
    count: ordered.length,
    total: new Map(), odd: new Map(), low: new Map(), ac: new Map(),
    endSum: new Map(), consecutive: new Map(), zonePattern: new Map(),
    carryover: new Map(), spread: new Map(),
    position: Array.from({ length: game.pick }, () => new Map()),
    sumsSorted: [], endSumsSorted: [], spreadsSorted: [],
  };
  const sums = [], ends = [], spreads = [];
  ordered.forEach((draw, idx) => {
    const prev = idx ? ordered[idx - 1].numbers : [];
    const p = profile(game, draw.numbers, prev);
    inc(emp.total, Math.floor(p.total / 5));
    inc(emp.odd, p.odd);
    inc(emp.low, p.low);
    inc(emp.ac, p.ac);
    inc(emp.endSum, Math.floor(p.endSum / 3));
    inc(emp.consecutive, p.consecutive);
    inc(emp.zonePattern, zoneKey(p.zones));
    if (idx) inc(emp.carryover, p.carryover);
    inc(emp.spread, Math.floor(p.spread / 4));
    p.numbers.forEach((n, pos) => inc(emp.position[pos], n));
    sums.push(p.total);
    ends.push(p.endSum);
    spreads.push(p.spread);
  });
  emp.sumsSorted = sums.sort((a, b) => a - b);
  emp.endSumsSorted = ends.sort((a, b) => a - b);
  emp.spreadsSorted = spreads.sort((a, b) => a - b);
  return emp;
}

const smoothed = (emp, counter, key, name) => ((counter.get(key) || 0) + 1.0) / (emp.count + emp.support[name]);

export const pTotal = (emp, v) => smoothed(emp, emp.total, Math.floor(v / 5), 'total');
export const pOdd = (emp, v) => smoothed(emp, emp.odd, v, 'odd');
export const pLow = (emp, v) => smoothed(emp, emp.low, v, 'low');
export const pAc = (emp, v) => smoothed(emp, emp.ac, v, 'ac');
export const pEndSum = (emp, v) => smoothed(emp, emp.endSum, Math.floor(v / 3), 'endSum');
export const pConsecutive = (emp, v) => smoothed(emp, emp.consecutive, v, 'consecutive');
export const pZone = (emp, zones) => smoothed(emp, emp.zonePattern, zoneKey(zones), 'zone');
export const pCarryover = (emp, v) => smoothed(emp, emp.carryover, v, 'carryover');
export const pSpread = (emp, v) => smoothed(emp, emp.spread, Math.floor(v / 4), 'spread');
export const pPosition = (emp, idx, number) => smoothed(emp, emp.position[idx], number, 'position');

export function calibrate(game, draws, coverage = 0.90, base = null) {
  base = base || defaultRules(game);
  if (!draws.length) return base;
  const emp = fit(game, draws);
  const tail = (1.0 - coverage) / 2.0;

  const trimmed = (counter, loDefault, hiDefault) => {
    const keys = [...counter.keys()].sort((a, b) => a - b);
    const n = [...counter.values()].reduce((a, b) => a + b, 0);
    let acc = 0, lo = keys[0];
    for (const k of keys) {
      acc += counter.get(k);
      if (acc / n > tail) { lo = k; break; }
    }
    acc = 0;
    let hi = keys[keys.length - 1];
    for (let i = keys.length - 1; i >= 0; i--) {
      acc += counter.get(keys[i]);
      if (acc / n > tail) { hi = keys[i]; break; }
    }
    return lo > hi ? [Math.min(lo, loDefault), Math.max(hi, hiDefault)] : [lo, hi];
  };

  const [oddLo, oddHi] = trimmed(emp.odd, ...base.oddRange);
  const [lowLo, lowHi] = trimmed(emp.low, ...base.lowRange);
  const [acLo] = trimmed(emp.ac, base.acMin, base.acMin);
  const [, consHi] = trimmed(emp.consecutive, 0, 0);
  const [, carryHi] = trimmed(emp.carryover, 0, 1);

  return {
    sumRange: [quantile(emp.sumsSorted, tail), quantile(emp.sumsSorted, 1 - tail)],
    oddRange: [oddLo, oddHi],
    lowRange: [lowLo, lowHi],
    acMin: acLo,
    maxRun: base.maxRun,
    maxConsecutivePairs: Math.max(1, consHi),
    maxPerZone: base.maxPerZone,
    minZones: base.minZones,
    endSumRange: [quantile(emp.endSumsSorted, tail), quantile(emp.endSumsSorted, 1 - tail)],
    maxSameEnding: base.maxSameEnding,
    mult3Range: [...base.mult3Range],
    spreadMin: quantile(emp.spreadsSorted, tail),
    carryoverRange: [0, Math.max(2, carryHi)],
    forbidAllSameParity: base.forbidAllSameParity,
  };
}

/** 가중 로그가능도. 높을수록 '흔한 모양'. 데이터가 없으면 0. */
export function typicality(nums, emp, previous = [], w = defaultWeights()) {
  if (!emp.count) return 0.0;
  const p = profile(emp.game, nums, previous);
  let score = 0.0;
  score += w.total * Math.log(pTotal(emp, p.total));
  score += w.odd * Math.log(pOdd(emp, p.odd));
  score += w.low * Math.log(pLow(emp, p.low));
  score += w.ac * Math.log(pAc(emp, p.ac));
  score += w.endSum * Math.log(pEndSum(emp, p.endSum));
  score += w.consecutive * Math.log(pConsecutive(emp, p.consecutive));
  score += w.zone * Math.log(pZone(emp, p.zones));
  if (previous.length) score += w.carryover * Math.log(pCarryover(emp, p.carryover));
  score += w.spread * Math.log(pSpread(emp, p.spread));
  let positional = 0.0;
  p.numbers.forEach((n, i) => { positional += Math.log(pPosition(emp, i, n)); });
  score += (w.position * positional) / emp.game.pick;
  return score;
}

export function referenceScores(draws, emp, weights = defaultWeights()) {
  const ordered = [...draws].sort((a, b) => a.no - b.no);
  return ordered
    .map((d, idx) => typicality(d.numbers, emp, idx ? ordered[idx - 1].numbers : [], weights))
    .sort((a, b) => a - b);
}
