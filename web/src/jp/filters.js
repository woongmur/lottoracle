/** 일본 로또 조합 필터. 파이썬 lottoracle/jp/filters.py 와 같다 (기본값 근거는 그쪽 주석).
 *
 * 기본값은 1회부터의 실제 당첨조합에서 정했다. 항목 하나하나는 실제 당첨조합의 80% 이상이
 * 통과한다. 확률을 올려 주지는 않는다 — 지나치게 튀는 모양을 걸러낼 뿐이다.
 */
import { profile } from './metrics.js';

const DEFAULT_RULES = {
  loto6: {
    sumRange: [95, 170], oddRange: [2, 4], lowRange: [2, 4], acMin: 6, maxRun: 2,
    maxConsecutivePairs: 1, maxPerZone: 3, minZones: 3, endSumRange: [17, 35],
    maxSameEnding: 2, mult3Range: [0, 4], spreadMin: 20, carryoverRange: [0, 2],
    forbidAllSameParity: true,
  },
  loto7: {
    sumRange: [101, 167], oddRange: [2, 5], lowRange: [2, 5], acMin: 8, maxRun: 3,
    maxConsecutivePairs: 2, maxPerZone: 4, minZones: 3, endSumRange: [23, 39],
    maxSameEnding: 2, mult3Range: [0, 4], spreadMin: 20, carryoverRange: [0, 3],
    forbidAllSameParity: true,
  },
  miniloto: {
    sumRange: [56, 105], oddRange: [1, 4], lowRange: [1, 4], acMin: 4, maxRun: 2,
    maxConsecutivePairs: 1, maxPerZone: 3, minZones: 2, endSumRange: [13, 29],
    maxSameEnding: 2, mult3Range: [0, 3], spreadMin: 14, carryoverRange: [0, 2],
    forbidAllSameParity: true,
  },
};

/** 후보를 못 찾을 때 한 단계에 풀어 주는 폭. */
export const RELAX_STEP = {
  loto6: { sum: 12, endSum: 5, spread: 6 },
  loto7: { sum: 12, endSum: 5, spread: 5 },
  miniloto: { sum: 7, endSum: 5, spread: 4 },
};

/** 게임의 기본 규칙 (새 객체 — 고쳐도 표는 그대로). */
export function defaultRules(game) {
  const r = DEFAULT_RULES[game.key];
  return Object.fromEntries(Object.entries(r).map(([k, v]) => [k, Array.isArray(v) ? [...v] : v]));
}

export function relaxed(game, rules, step = 1) {
  const s = Math.max(0, step);
  const k = game.pick;
  const w = RELAX_STEP[game.key];
  return {
    ...rules,
    sumRange: [rules.sumRange[0] - w.sum * s, rules.sumRange[1] + w.sum * s],
    oddRange: [Math.max(0, rules.oddRange[0] - s), Math.min(k, rules.oddRange[1] + s)],
    lowRange: [Math.max(0, rules.lowRange[0] - s), Math.min(k, rules.lowRange[1] + s)],
    acMin: Math.max(0, rules.acMin - s),
    maxRun: Math.min(k, rules.maxRun + s),
    maxConsecutivePairs: Math.min(k - 1, rules.maxConsecutivePairs + s),
    maxPerZone: Math.min(k, rules.maxPerZone + s),
    minZones: Math.max(1, rules.minZones - s),
    endSumRange: [
      Math.max(0, rules.endSumRange[0] - w.endSum * s),
      Math.min(9 * k, rules.endSumRange[1] + w.endSum * s),
    ],
    maxSameEnding: Math.min(k, rules.maxSameEnding + s),
    mult3Range: [Math.max(0, rules.mult3Range[0] - s), Math.min(k, rules.mult3Range[1] + s)],
    spreadMin: Math.max(0, rules.spreadMin - w.spread * s),
    carryoverRange: [0, Math.min(k, rules.carryoverRange[1] + s)],
  };
}

const inRange = (value, [lo, hi]) => lo <= value && value <= hi;

export function check(game, nums, rules, previous = []) {
  const p = profile(game, nums, previous);
  const bad = [];
  if (!inRange(p.total, rules.sumRange))
    bad.push(`합계 ${p.total} (허용 ${rules.sumRange[0]}~${rules.sumRange[1]})`);
  if (!inRange(p.odd, rules.oddRange)) bad.push(`홀짝 ${p.odd}:${p.even}`);
  if (!inRange(p.low, rules.lowRange)) bad.push(`고저 ${p.low}:${p.high}`);
  if (p.ac < rules.acMin) bad.push(`AC값 ${p.ac} (최소 ${rules.acMin})`);
  if (p.maxRun > rules.maxRun) bad.push(`${p.maxRun}연속수`);
  if (p.consecutive > rules.maxConsecutivePairs) bad.push(`연속쌍 ${p.consecutive}개`);
  const peak = Math.max(...p.zones);
  if (peak > rules.maxPerZone) bad.push(`한 구간에 ${peak}개 집중`);
  const spreadZones = p.zones.filter(z => z).length;
  if (spreadZones < rules.minZones) bad.push(`분포 구간 ${spreadZones}개`);
  if (!inRange(p.endSum, rules.endSumRange)) bad.push(`끝수합 ${p.endSum}`);
  if (p.sameEnding > rules.maxSameEnding) bad.push(`같은 끝수 ${p.sameEnding}개`);
  if (!inRange(p.mult3, rules.mult3Range)) bad.push(`3배수 ${p.mult3}개`);
  if (p.spread < rules.spreadMin) bad.push(`번호 폭 ${p.spread}`);
  if (!inRange(p.carryover, rules.carryoverRange)) bad.push(`이월수 ${p.carryover}개`);
  if (rules.forbidAllSameParity && (p.odd === 0 || p.odd === game.pick))
    bad.push('전부 홀수 또는 전부 짝수');
  return { ok: bad.length === 0, profile: p, violations: bad };
}

export const passes = (game, nums, rules, previous = []) => check(game, nums, rules, previous).ok;
