/** 채점(등수 판정)과 당첨금 계산. */
import { sortedNums } from './metrics.js';

export const RANK_LABEL = { 1: '1등', 2: '2등', 3: '3등', 4: '4등', 5: '5등', 0: '낙첨' };
// 확률은 정확값, 상금은 대략적인 평균치(1~3등은 회차별 변동).
export const RANK_ODDS = {
  1: 1 / 8145060, 2: 6 / 8145060, 3: 228 / 8145060,
  4: 11115 / 8145060, 5: 182780 / 8145060,
};
export const RANK_PRIZE = { 1: 2000000000, 2: 55000000, 3: 1500000, 4: 50000, 5: 5000 };
export const RANK_MATCH = { 1: '6개', 2: '5개+보너스', 3: '5개', 4: '4개', 5: '3개' };
export const TICKET_PRICE = 1000;

/** 등수: 1등 6개 / 2등 5개+보너스 / 3등 5개 / 4등 4개 / 5등 3개 / 0 낙첨. */
export function rankOf(nums, draw) {
  const winning = new Set(draw.numbers);
  const hit = nums.filter(n => winning.has(n)).length;
  if (hit === 6) return 1;
  if (hit === 5) return nums.includes(draw.bonus) ? 2 : 3;
  if (hit === 4) return 4;
  if (hit === 3) return 5;
  return 0;
}

/**
 * 조합들을 한 회차에 대해 채점한다.
 * 회차가 1~5등 실제 당첨금(draw.prizes)을 갖고 있으면 그 금액을, 없으면 평균치를 쓴다.
 */
export function grade(lines, draw) {
  const winning = new Set(draw.numbers);
  const byRank = new Map((draw.prizes || []).map(p => [p.rank, p]));
  const actual = byRank.size === 5;
  const results = lines.map(row => {
    const numbers = sortedNums(row);
    const rank = rankOf(numbers, draw);
    const actualPrize = rank && actual ? byRank.get(rank)?.amount : undefined;
    return {
      numbers,
      hit: numbers.filter(n => winning.has(n)),
      bonusHit: numbers.includes(draw.bonus),
      rank,
      label: RANK_LABEL[rank],
      prize: rank ? (actualPrize ?? RANK_PRIZE[rank]) : 0,
    };
  });
  const ranks = results.filter(r => r.rank).map(r => r.rank);
  return {
    results,
    bestRank: ranks.length ? Math.min(...ranks) : 0,
    totalPrize: results.reduce((a, r) => a + r.prize, 0),
    actualPrize: actual,
  };
}
