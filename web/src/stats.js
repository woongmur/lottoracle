/** 과거 회차에서 번호별 통계를 뽑아낸다. */
import { NUMBER_POOL, profile, sortedNums } from './metrics.js';

/** 번호쌍을 Map 키로 쓰기 위한 문자열. 작은 번호가 앞. */
export const pairKey = (a, b) => (a < b ? `${a}-${b}` : `${b}-${a}`);

const inc = (map, key, by = 1) => map.set(key, (map.get(key) || 0) + by);

/** 회차 목록을 회차 번호 오름차순으로. */
const byDrawNo = draws => [...draws].sort((a, b) => a.no - b.no);

/**
 * 번호 1~45에 대한 출현 통계.
 * frequency/recent/gap/pairs/bonusFrequency 는 모두 Map.
 */
export function build(draws, recentWindow = 30) {
  const st = {
    drawsUsed: draws.length,
    recentWindow,
    frequency: new Map(),
    recent: new Map(),
    gap: new Map(),
    pairs: new Map(),
    bonusFrequency: new Map(),
  };
  if (!draws.length) {
    for (const n of NUMBER_POOL) st.gap.set(n, 0);
    return st;
  }

  const ordered = byDrawNo(draws);
  for (const draw of ordered) {
    for (const n of draw.numbers) inc(st.frequency, n);
    inc(st.bonusFrequency, draw.bonus);
    const nums = sortedNums(draw.numbers);
    for (let i = 0; i < nums.length; i++)
      for (let j = i + 1; j < nums.length; j++) inc(st.pairs, pairKey(nums[i], nums[j]));
  }

  for (const draw of ordered.slice(-recentWindow)) {
    for (const n of draw.numbers) inc(st.recent, n);
  }

  const lastSeen = new Map(NUMBER_POOL.map(n => [n, -1]));
  ordered.forEach((draw, idx) => {
    for (const n of draw.numbers) lastSeen.set(n, idx);
  });
  const total = ordered.length;
  for (const n of NUMBER_POOL) {
    const idx = lastSeen.get(n);
    st.gap.set(n, idx >= 0 ? total - 1 - idx : total);
  }
  return st;
}

export const meanFrequency = st => (st.drawsUsed ? (st.drawsUsed * 6) / 45 : 0);

/**
 * 파이썬 Counter.most_common(n) 과 같은 순서:
 * 횟수 내림차순, 동점이면 먼저 등록된 순(= 번호가 처음 나온 순).
 */
function mostCommon(counter, n) {
  const keys = [...counter.keys()];                       // Map 은 삽입 순서를 지킨다
  const order = new Map(keys.map((k, i) => [k, i]));
  return keys
    .sort((a, b) => (counter.get(b) - counter.get(a)) || (order.get(a) - order.get(b)))
    .slice(0, n)
    .map(k => [k, counter.get(k)]);
}

/** 최근 창에서 많이 나온 번호. */
export const hot = (st, n = 10) => mostCommon(st.recent, n);

/** 오래 안 나온 번호. 파이썬은 gap 내림차순 정렬(동점이면 번호 오름차순). */
export function cold(st, n = 10) {
  return [...st.gap.entries()]
    .sort((a, b) => (b[1] - a[1]) || (a[0] - b[0]))
    .slice(0, n);
}

/** 해당 번호와 같이 나온 적 많은 번호(궁합수). */
export function companions(st, number, n = 6) {
  return NUMBER_POOL.filter(other => other !== number)
    .map(other => [other, st.pairs.get(pairKey(number, other)) || 0])
    .sort((a, b) => (b[1] - a[1]) || (a[0] - b[0]))
    .slice(0, n);
}

/** 당첨조합들이 실제로 어떤 모양이었는지 요약 (= '대한민국 로또 평균치'). */
export function profileStats(draws) {
  const ordered = byDrawNo(draws);
  if (!ordered.length) throw new Error('분석할 회차 데이터가 없습니다.');

  const sums = [], ends = [];
  const oddD = new Map(), lowD = new Map(), acD = new Map(), carryD = new Map();
  let withConsecutive = 0;

  ordered.forEach((draw, idx) => {
    const prev = idx ? ordered[idx - 1].numbers : [];
    const p = profile(draw.numbers, prev);
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
