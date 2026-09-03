/** metrics.js 가 파이썬 lottoracle.metrics 와 같은 값을 내는지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as m from '../src/metrics.js';

const golden = JSON.parse(readFileSync(new URL('./golden/metrics.json', import.meta.url)));

test('상수가 파이썬과 같다', () => {
  assert.equal(m.NUMBER_POOL.length, 45);
  assert.equal(m.NUMBER_POOL[0], 1);
  assert.equal(m.NUMBER_POOL[44], 45);
  assert.equal(m.PICK, 6);
  assert.equal(m.LOW_MAX, 22);
  assert.deepEqual(m.TWIN_NUMBERS, [11, 22, 33, 44]);
});

test('모든 골든 케이스의 지표가 일치한다 (직전 회차 없음)', () => {
  for (const c of golden.cases) {
    const p = m.profile(c.numbers);
    for (const key of Object.keys(c.noPrev)) {
      if (key === 'summary') continue;
      assert.deepEqual(p[key], c.noPrev[key], `${c.numbers} 의 ${key}`);
    }
    assert.equal(m.summary(p), c.noPrev.summary, `${c.numbers} 의 summary`);
  }
});

test('모든 골든 케이스의 지표가 일치한다 (직전 회차 있음)', () => {
  for (const c of golden.cases) {
    const p = m.profile(c.numbers, golden.previous);
    for (const key of Object.keys(c.withPrev)) {
      if (key === 'summary') continue;
      assert.deepEqual(p[key], c.withPrev[key], `${c.numbers} 의 ${key}`);
    }
    assert.equal(m.summary(p), c.withPrev.summary);
  }
});

test('입력 배열을 건드리지 않는다', () => {
  const input = [45, 1, 23, 22, 8, 17];
  const copy = [...input];
  m.profile(input, [11, 13]);
  assert.deepEqual(input, copy);
});

test('AC값 경계', () => {
  assert.equal(m.acValue([1, 2, 3, 4, 5, 6]), 0);
  assert.equal(m.acValue([1, 2, 3, 4, 5, 45]), 4);
  for (let i = 0; i < 200; i++) {
    const pool = [...m.NUMBER_POOL];
    const pick = [];
    for (let k = 0; k < 6; k++) pick.push(...pool.splice(Math.floor(Math.random() * pool.length), 1));
    const ac = m.acValue(pick);
    assert.ok(ac >= 0 && ac <= 10, `AC ${ac} 범위 밖: ${pick}`);
  }
});

test('연속수 계산', () => {
  assert.equal(m.maxConsecutiveRun([3, 4, 5, 20, 31, 44]), 3);
  assert.equal(m.maxConsecutiveRun([1, 3, 5, 7, 9, 11]), 1);
  assert.equal(m.maxConsecutiveRun([1, 2, 3, 4, 5, 6]), 6);
  assert.equal(m.consecutivePairs([3, 4, 5, 20, 31, 44]), 2);
  assert.equal(m.consecutivePairs([1, 3, 5, 7, 9, 11]), 0);
});

test('이월수는 중복 입력에도 집합으로 센다', () => {
  assert.equal(m.carryoverCount([11, 13, 22], [11, 13, 22, 32]), 3);
  assert.equal(m.carryoverCount([1, 2, 3], []), 0);
});
