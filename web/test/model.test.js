/** model.js 가 파이썬 lottoracle.model 과 같은 보정·점수를 내는지 대조한다.
 *  부동소수점은 상대오차로 비교한다 (같은 IEEE 754 연산이라 오차는 극히 작아야 한다).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as model from '../src/model.js';
import { defaultRules } from '../src/filters.js';

const golden = JSON.parse(readFileSync(new URL('./golden/model.json', import.meta.url)));
const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
const PREVIOUS = [11, 13, 22, 32, 33, 36];
const emp = model.fit(draws);
const ref = model.referenceScores(draws, emp);

const near = (a, b, label, eps = 1e-12) => {
  const scale = Math.max(1, Math.abs(a), Math.abs(b));
  assert.ok(Math.abs(a - b) / scale < eps, `${label}: ${a} != ${b}`);
};

test('분포 집계 회차 수가 같다', () => {
  assert.equal(emp.count, golden.empCount);
});

test('coverage 별 보정 규칙이 파이썬과 같다', () => {
  for (const [cov, expected] of Object.entries(golden.calibrated)) {
    assert.deepEqual(model.calibrate(draws, Number(cov)), expected, `coverage ${cov}`);
  }
});

test('평활 확률값이 파이썬과 같다', () => {
  const p = golden.probes;
  for (const [v, want] of Object.entries(p.pTotal)) near(model.pTotal(emp, Number(v)), want, `pTotal(${v})`);
  for (const [v, want] of Object.entries(p.pOdd)) near(model.pOdd(emp, Number(v)), want, `pOdd(${v})`);
  for (const [v, want] of Object.entries(p.pLow)) near(model.pLow(emp, Number(v)), want, `pLow(${v})`);
  for (const [v, want] of Object.entries(p.pAc)) near(model.pAc(emp, Number(v)), want, `pAc(${v})`);
  for (const [v, want] of Object.entries(p.pEndSum)) near(model.pEndSum(emp, Number(v)), want, `pEndSum(${v})`);
  for (const [v, want] of Object.entries(p.pConsecutive)) near(model.pConsecutive(emp, Number(v)), want, `pConsecutive(${v})`);
  for (const [v, want] of Object.entries(p.pCarryover)) near(model.pCarryover(emp, Number(v)), want, `pCarryover(${v})`);
  for (const [v, want] of Object.entries(p.pSpread)) near(model.pSpread(emp, Number(v)), want, `pSpread(${v})`);
  for (const [key, want] of Object.entries(p.pZone)) {
    near(model.pZone(emp, key.split('-').map(Number)), want, `pZone(${key})`);
  }
  for (const [key, want] of Object.entries(p.pPosition)) {
    const [i, n] = key.split('-').map(Number);
    near(model.pPosition(emp, i, n), want, `pPosition(${key})`);
  }
});

test('전형성 점수와 백분위가 파이썬과 같다', () => {
  for (const c of golden.typicality) {
    near(model.typicality(c.numbers, emp), c.noPrev, `${c.numbers} 점수(직전 없음)`);
    const withPrev = model.typicality(c.numbers, emp, PREVIOUS);
    near(withPrev, c.withPrev, `${c.numbers} 점수(직전 있음)`);
    near(model.typicalityPercentile(withPrev, ref), c.percentile, `${c.numbers} 백분위`);
  }
});

test('참조 점수 분포가 파이썬과 같다', () => {
  assert.equal(ref.length, golden.referenceStats.count);
  near(ref[0], golden.referenceStats.min, '최솟값');
  near(ref[ref.length - 1], golden.referenceStats.max, '최댓값');
  near(ref[Math.floor(ref.length / 2)], golden.referenceStats.median, '중앙값');
});

test('흔한 모양이 극단적인 모양보다 점수가 높다', () => {
  const common = model.typicality([5, 12, 19, 26, 31, 38], emp);
  const extreme = model.typicality([1, 2, 3, 4, 5, 6], emp);
  assert.ok(common > extreme, `${common} <= ${extreme}`);
});

test('데이터가 없으면 0점, 백분위는 50', () => {
  assert.equal(model.typicality([1, 2, 3, 4, 5, 6], model.fit([])), 0);
  assert.equal(model.typicalityPercentile(0, []), 50);
});

test('은행가 반올림이 파이썬 round() 와 같다', () => {
  // 파이썬: round(0.5)=0, round(1.5)=2, round(2.5)=2, round(3.5)=4 (짝수 쪽으로)
  // JS Math.round 는 각각 1, 2, 3, 4 라서 그대로 쓰면 백분위가 어긋난다.
  const cases = [[0.5, 0], [1.5, 2], [2.5, 2], [3.5, 4], [0.4, 0], [0.6, 1], [2.4, 2], [2.6, 3],
                 [-0.5, 0], [-1.5, -2], [-2.5, -2], [-3.5, -4]];
  for (const [input, want] of cases) {
    assert.equal(model.roundHalfEven(input), want, `roundHalfEven(${input})`);
  }
});

test('quantile 이 파이썬 _quantile 과 같은 인덱스를 고른다', () => {
  const v = [0, 10, 20, 30, 40];          // len 5 → (len-1)=4
  assert.equal(model.quantile(v, 0), 0);
  assert.equal(model.quantile(v, 0.125), 0);    // 4*0.125=0.5 → 파이썬 round(0.5)=0
  assert.equal(model.quantile(v, 0.25), 10);
  assert.equal(model.quantile(v, 0.5), 20);
  assert.equal(model.quantile(v, 1), 40);
  assert.equal(model.quantile([], 0.5), 0);     // 빈 배열
  assert.equal(model.quantile(v, 5), 40);       // 범위 밖은 잘린다
  assert.equal(model.quantile(v, -1), 0);
});

test('빈 회차 목록이면 기본 규칙을 그대로 돌려준다', () => {
  assert.deepEqual(model.calibrate([], 0.9), defaultRules());
});
