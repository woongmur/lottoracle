/** 대한민국 로또 평균치에 기반한 조합 필터.
 *
 * 기본값은 실제 당첨조합 분포에서 관찰되는 '흔한 구간'이다. 확률을 올려주지는 않는다.
 * 지나치게 튀는 모양(1·2·3·4·5·6 같은)을 걸러낼 뿐이다.
 */
import { profile } from './metrics.js';

// 6개 번호 합의 이론적 기대값 = 6 * 23 = 138.
export const EXPECTED_SUM = 138;

/** 조합이 통과해야 할 조건. 값을 넉넉히 잡을수록 후보가 늘어난다. */
export function defaultRules() {
  return {
    sumRange: [100, 175],
    oddRange: [2, 4],              // 홀수 개수, 3:3이 최빈
    lowRange: [2, 4],              // 1~22 개수, 3:3이 최빈
    acMin: 7,                      // 당첨조합 AC값 최빈 8
    maxRun: 2,                     // 연속수는 2연속까지 허용
    maxConsecutivePairs: 1,
    maxPerZone: 3,                 // 한 구간에 4개 이상 몰리지 않게
    minZones: 3,                   // 최소 3개 구간에 분산
    endSumRange: [15, 35],
    maxSameEnding: 2,              // 같은 끝수 3개 이상 금지
    mult3Range: [0, 4],
    spreadMin: 20,                 // 최댓값-최솟값
    carryoverRange: [0, 2],        // 이월수(직전 회차 중복)
    forbidAllSameParity: true,
  };
}

/** 후보를 못 찾을 때 단계적으로 완화한 규칙을 만든다. */
export function relaxed(rules, step = 1) {
  const s = Math.max(0, step);
  return {
    ...rules,
    sumRange: [rules.sumRange[0] - 12 * s, rules.sumRange[1] + 12 * s],
    oddRange: [Math.max(0, rules.oddRange[0] - s), Math.min(6, rules.oddRange[1] + s)],
    lowRange: [Math.max(0, rules.lowRange[0] - s), Math.min(6, rules.lowRange[1] + s)],
    acMin: Math.max(0, rules.acMin - s),
    maxRun: Math.min(6, rules.maxRun + s),
    maxConsecutivePairs: Math.min(5, rules.maxConsecutivePairs + s),
    maxPerZone: Math.min(6, rules.maxPerZone + s),
    minZones: Math.max(1, rules.minZones - s),
    endSumRange: [
      Math.max(0, rules.endSumRange[0] - 5 * s),
      Math.min(54, rules.endSumRange[1] + 5 * s),
    ],
    maxSameEnding: Math.min(6, rules.maxSameEnding + s),
    mult3Range: [Math.max(0, rules.mult3Range[0] - s), Math.min(6, rules.mult3Range[1] + s)],
    spreadMin: Math.max(0, rules.spreadMin - 6 * s),
    carryoverRange: [0, Math.min(6, rules.carryoverRange[1] + s)],
  };
}

const inRange = (value, [lo, hi]) => lo <= value && value <= hi;

/** 필터 결과와, 떨어졌다면 그 이유. */
export function check(nums, rules, previous = []) {
  const p = profile(nums, previous);
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
  if (rules.forbidAllSameParity && (p.odd === 0 || p.odd === 6))
    bad.push('전부 홀수 또는 전부 짝수');

  return { ok: bad.length === 0, profile: p, violations: bad };
}

export const passes = (nums, rules, previous = []) => check(nums, rules, previous).ok;
