/** 실데이터로 필터를 보정하고, 조합의 '전형성'을 점수화한다.
 *
 * 전형성(typicality) = 이 조합의 모양이 과거 당첨조합들의 모양 분포에서 얼마나 흔한가.
 * 확률과는 무관하다 — 모든 조합은 똑같이 1/8,145,060 이다. 다만 '흔한 모양'을 고르면
 * 1·2·3·4·5·6 같은 조합이 배제되고, 당첨 시 인기 조합과 상금을 나눌 위험이 줄어든다.
 */
import { defaultRules } from './filters.js';
import { PICK, profile } from './metrics.js';

/** 파이썬 round() 와 같은 은행가 반올림 — .5 는 짝수 쪽으로 간다. */
export function roundHalfEven(x) {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

export function quantile(sortedValues, q) {
  if (!sortedValues.length) return 0;
  const idx = roundHalfEven((sortedValues.length - 1) * q);
  return sortedValues[Math.max(0, Math.min(sortedValues.length - 1, idx))];
}

const inc = (map, key) => map.set(key, (map.get(key) || 0) + 1);
const zoneKey = zones => [...zones].sort((a, b) => a - b).join(',');

/** 지표별 경험 분포. 각 Map 은 값 → 관측 횟수. */
export function fit(draws) {
  const ordered = [...draws].sort((a, b) => a.no - b.no);
  const emp = {
    count: ordered.length,
    total: new Map(), odd: new Map(), low: new Map(), ac: new Map(),
    endSum: new Map(), consecutive: new Map(), zonePattern: new Map(),
    carryover: new Map(), spread: new Map(),
    position: Array.from({ length: PICK }, () => new Map()),
    sumsSorted: [], endSumsSorted: [], spreadsSorted: [],
  };
  const sums = [], ends = [], spreads = [];
  ordered.forEach((draw, idx) => {
    const prev = idx ? ordered[idx - 1].numbers : [];
    const p = profile(draw.numbers, prev);
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

// ---- 확률 조회 (라플라스 평활) ----
const smoothed = (emp, counter, key, support) =>
  ((counter.get(key) || 0) + 1.0) / (emp.count + support);

export const pTotal = (emp, v) => smoothed(emp, emp.total, Math.floor(v / 5), 60);   // 5단위 구간
export const pOdd = (emp, v) => smoothed(emp, emp.odd, v, 7);
export const pLow = (emp, v) => smoothed(emp, emp.low, v, 7);
export const pAc = (emp, v) => smoothed(emp, emp.ac, v, 11);
export const pEndSum = (emp, v) => smoothed(emp, emp.endSum, Math.floor(v / 3), 20);
export const pConsecutive = (emp, v) => smoothed(emp, emp.consecutive, v, 6);
export const pZone = (emp, zones) => smoothed(emp, emp.zonePattern, zoneKey(zones), 40);
export const pCarryover = (emp, v) => smoothed(emp, emp.carryover, v, 7);
export const pSpread = (emp, v) => smoothed(emp, emp.spread, Math.floor(v / 4), 12);
export const pPosition = (emp, idx, number) => smoothed(emp, emp.position[idx], number, 45);

/**
 * 실데이터 백분위로 규칙 범위를 자동 보정한다.
 * coverage=0.90 이면 합계·끝수합·번호폭은 과거 당첨조합의 가운데 90%를 덮는 범위,
 * 홀짝·고저·AC·연속수는 누적 비율이 (1-coverage) 미만인 꼬리를 잘라낸 범위가 된다.
 */
export function calibrate(draws, coverage = 0.90, base = null) {
  base = base || defaultRules();
  if (!draws.length) return base;
  const emp = fit(draws);
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

  const [oddLo, oddHi] = trimmed(emp.odd, 3, 3);
  const [lowLo, lowHi] = trimmed(emp.low, 3, 3);
  const [acLo] = trimmed(emp.ac, 8, 8);
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
    mult3Range: base.mult3Range,
    spreadMin: quantile(emp.spreadsSorted, tail),
    carryoverRange: [0, Math.max(2, carryHi)],
    forbidAllSameParity: base.forbidAllSameParity,
  };
}

/** 지표별 로그가능도 가중. 0이면 그 지표는 무시. */
export function defaultWeights() {
  return {
    total: 1.0, odd: 1.0, low: 1.0, ac: 1.0, endSum: 0.6,
    consecutive: 0.6, zone: 1.0, carryover: 0.5, spread: 0.5, position: 0.8,
  };
}

/** 가중 로그가능도. 높을수록 '흔한 모양'. 데이터가 없으면 0. */
export function typicality(nums, emp, previous = [], weights = defaultWeights()) {
  if (!emp.count) return 0.0;
  const p = profile(nums, previous);
  let score = 0.0;
  score += weights.total * Math.log(pTotal(emp, p.total));
  score += weights.odd * Math.log(pOdd(emp, p.odd));
  score += weights.low * Math.log(pLow(emp, p.low));
  score += weights.ac * Math.log(pAc(emp, p.ac));
  score += weights.endSum * Math.log(pEndSum(emp, p.endSum));
  score += weights.consecutive * Math.log(pConsecutive(emp, p.consecutive));
  score += weights.zone * Math.log(pZone(emp, p.zones));
  if (previous.length) score += weights.carryover * Math.log(pCarryover(emp, p.carryover));
  score += weights.spread * Math.log(pSpread(emp, p.spread));
  let positional = 0.0;
  p.numbers.forEach((n, i) => { positional += Math.log(pPosition(emp, i, n)); });
  score += (weights.position * positional) / PICK;
  return score;
}

/** 참조 점수 분포 안에서의 백분위 (0~100). */
export function typicalityPercentile(score, reference) {
  if (!reference.length) return 50.0;
  const below = reference.filter(r => r <= score).length;
  return (100.0 * below) / reference.length;
}

/** 과거 당첨조합 각각의 전형성 점수 — 새 조합의 점수를 비교할 기준. */
export function referenceScores(draws, emp, weights = defaultWeights()) {
  const ordered = [...draws].sort((a, b) => a.no - b.no);
  return ordered
    .map((d, idx) => typicality(d.numbers, emp, idx ? ordered[idx - 1].numbers : [], weights))
    .sort((a, b) => a - b);
}
