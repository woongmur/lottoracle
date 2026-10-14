/** 일본 로또 과거 회차에서 번호별 통계. 파이썬 lottoracle/jp/stats.py 와 같다.
 *
 * 다른 점: 보너스가 여러 개일 수 있다(로또7 은 둘). 보너스 빈도는 모두 센다.
 */
import { sortedNums } from '../metrics.js';
import { pairKey } from '../stats.js';
import { numberPool, profile } from './metrics.js';

export { pairKey };

const inc = (map, key, by = 1) => map.set(key, (map.get(key) || 0) + by);
const byDrawNo = draws => [...draws].sort((a, b) => a.no - b.no);

export function build(game, draws, recentWindow = 30) {
  const pool = numberPool(game);
  const st = {
    game,
    drawsUsed: draws.length,
    recentWindow,
    frequency: new Map(),
    recent: new Map(),
    gap: new Map(),
    pairs: new Map(),
    bonusFrequency: new Map(),
  };
  if (!draws.length) {
    for (const n of pool) st.gap.set(n, 0);
    return st;
  }
  const ordered = byDrawNo(draws);
  for (const draw of ordered) {
    for (const n of draw.numbers) inc(st.frequency, n);
    for (const b of draw.bonus) inc(st.bonusFrequency, b);
    const nums = sortedNums(draw.numbers);
    for (let i = 0; i < nums.length; i++)
      for (let j = i + 1; j < nums.length; j++) inc(st.pairs, pairKey(nums[i], nums[j]));
  }
  for (const draw of ordered.slice(-recentWindow)) {
    for (const n of draw.numbers) inc(st.recent, n);
  }
  const lastSeen = new Map(pool.map(n => [n, -1]));
  ordered.forEach((draw, idx) => {
    for (const n of draw.numbers) lastSeen.set(n, idx);
  });
  const total = ordered.length;
  for (const n of pool) {
    const idx = lastSeen.get(n);
    st.gap.set(n, idx >= 0 ? total - 1 - idx : total);
  }
  return st;
}

export const meanFrequency = st => (st.drawsUsed ? (st.drawsUsed * st.game.pick) / st.game.pool : 0);

/** 파이썬 Counter.most_common(n) 과 같은 순서 (횟수 내림차순, 동점이면 먼저 센 것). */
function mostCommon(counter, n) {
  const keys = [...counter.keys()];
  const order = new Map(keys.map((k, i) => [k, i]));
  return keys
    .sort((a, b) => (counter.get(b) - counter.get(a)) || (order.get(a) - order.get(b)))
    .slice(0, n)
    .map(k => [k, counter.get(k)]);
}

export const hot = (st, n = 10) => mostCommon(st.recent, n);

export function cold(st, n = 10) {
  return [...st.gap.entries()]
    .sort((a, b) => (b[1] - a[1]) || (a[0] - b[0]))
    .slice(0, n);
}

export function companions(st, number, n = 6) {
  return numberPool(st.game).filter(o => o !== number)
    .map(o => [o, st.pairs.get(pairKey(number, o)) || 0])
    .sort((a, b) => (b[1] - a[1]) || (a[0] - b[0]))
    .slice(0, n);
}

export function profileStats(game, draws) {
  const ordered = byDrawNo(draws);
  if (!ordered.length) throw new Error('분석할 회차 데이터가 없습니다.');
  const sums = [], ends = [];
  const oddD = new Map(), lowD = new Map(), acD = new Map(), carryD = new Map();
  let withConsecutive = 0;
  ordered.forEach((draw, idx) => {
    const prev = idx ? ordered[idx - 1].numbers : [];
    const p = profile(game, draw.numbers, prev);
    sums.push(p.total);
    ends.push(p.endSum);
    inc(oddD, p.odd);
    inc(lowD, p.low);
    inc(acD, p.ac);
    if (idx) inc(carryD, p.carryover);
    if (p.consecutive) withConsecutive++;
  });
  const orderedSums = [...sums].sort((a, b) => a - b);
  const lo = orderedSums[Math.floor(orderedSums.length * 0.10)];
  const hi = orderedSums[Math.min(orderedSums.length - 1, Math.floor(orderedSums.length * 0.90))];
  const mean = arr => arr.reduce((a, b) => a + b, 0) / arr.length;
  return {
    count: ordered.length,
    meanSum: mean(sums),
    sumRange80: [lo, hi],
    oddDistribution: oddD,
    lowDistribution: lowD,
    acDistribution: acD,
    endSumMean: mean(ends),
    consecutiveRatio: withConsecutive / ordered.length,
    carryoverDistribution: carryD,
  };
}
