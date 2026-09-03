/** stats.js 가 파이썬 lottoracle.stats 와 같은 통계를 내는지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as s from '../src/stats.js';
import { NUMBER_POOL } from '../src/metrics.js';

const golden = JSON.parse(readFileSync(new URL('./golden/stats.json', import.meta.url)));
const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
const st = s.build(draws, golden.recentWindow);

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('회차 수와 평균 출현이 같다', () => {
  assert.equal(st.drawsUsed, golden.drawsUsed);
  close(s.meanFrequency(st), golden.meanFrequency);
});

test('번호별 전체 출현 횟수가 모두 같다', () => {
  for (const n of NUMBER_POOL) {
    assert.equal(st.frequency.get(n) || 0, golden.frequency[String(n)], `${n}번`);
  }
});

test('최근 창 출현과 미출현 회차 수가 모두 같다', () => {
  for (const n of NUMBER_POOL) {
    assert.equal(st.recent.get(n) || 0, golden.recent[String(n)], `${n}번 최근`);
    assert.equal(st.gap.get(n), golden.gap[String(n)], `${n}번 미출현`);
  }
});

test('보너스 출현 횟수가 같다', () => {
  for (const n of NUMBER_POOL) {
    assert.equal(st.bonusFrequency.get(n) || 0, golden.bonusFrequency[String(n)], `${n}번 보너스`);
  }
});

test('핫/콜드 상위 10개가 파이썬과 같은 순서다', () => {
  assert.deepEqual(s.hot(st, 10), golden.hot10);
  assert.deepEqual(s.cold(st, 10), golden.cold10);
});

test('궁합수와 번호쌍 집계가 같다', () => {
  assert.deepEqual(s.companions(st, 7, 6), golden.companionsOf7);
  for (const [key, count] of Object.entries(golden.pairSamples)) {
    const [a, b] = key.split('-').map(Number);
    assert.equal(st.pairs.get(s.pairKey(a, b)) || 0, count, `${key} 쌍`);
  }
});

test('회차 전체 평균치가 같다', () => {
  const ps = s.profileStats(draws);
  const g = golden.profileStats;
  assert.equal(ps.count, g.count);
  close(ps.meanSum, g.meanSum);
  assert.deepEqual(ps.sumRange80, g.sumRange80);
  close(ps.endSumMean, g.endSumMean);
  close(ps.consecutiveRatio, g.consecutiveRatio);
  for (const [name, dist] of [
    ['oddDistribution', g.oddDistribution], ['lowDistribution', g.lowDistribution],
    ['acDistribution', g.acDistribution], ['carryoverDistribution', g.carryoverDistribution],
  ]) {
    for (const [k, v] of Object.entries(dist)) {
      assert.equal(ps[name].get(Number(k)) || 0, v, `${name}[${k}]`);
    }
  }
});

test('빈 입력에서도 안전하다', () => {
  const empty = s.build([], 30);
  assert.equal(empty.drawsUsed, 0);
  assert.equal(empty.gap.get(1), 0);
  assert.equal(s.meanFrequency(empty), 0);
  assert.throws(() => s.profileStats([]), /회차 데이터가 없습니다/);
});

test('입력 배열 순서를 바꾸지 않는다', () => {
  const shuffled = [draws[5], draws[0], draws[2]];
  const copy = [...shuffled];
  s.build(shuffled, 2);
  assert.deepEqual(shuffled, copy);
});
