/** filters.js 가 파이썬 lottoracle.filters 와 같은 판정·문구를 내는지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as f from '../src/filters.js';

const golden = JSON.parse(readFileSync(new URL('./golden/filters.json', import.meta.url)));
const PREVIOUS = [11, 13, 22, 32, 33, 36];

test('기본 규칙값이 파이썬과 같다', () => {
  assert.deepEqual(f.defaultRules(), golden.base);
});

test('완화 단계 1~3 이 파이썬과 같다', () => {
  for (const step of [1, 2, 3]) {
    assert.deepEqual(f.relaxed(f.defaultRules(), step), golden.relaxed[String(step)], `${step}단계`);
  }
});

test('판정과 위반 사유 문구가 파이썬과 같다', () => {
  const rules = f.defaultRules();
  for (const c of golden.cases) {
    const v = f.check(c.numbers, rules, PREVIOUS);
    assert.equal(v.ok, c.verdict.ok, `${c.numbers} 통과 여부`);
    assert.deepEqual(v.violations, c.verdict.violations, `${c.numbers} 사유`);
  }
});

test('완화는 원본 규칙을 바꾸지 않는다', () => {
  const rules = f.defaultRules();
  const before = JSON.stringify(rules);
  f.relaxed(rules, 2);
  assert.equal(JSON.stringify(rules), before);
});

test('완화할수록 위반이 줄어든다', () => {
  const nums = [1, 2, 3, 4, 5, 6];
  const base = f.defaultRules();
  assert.equal(f.passes(nums, base), false);
  const counts = [0, 1, 2, 3, 4, 5].map(s => f.check(nums, f.relaxed(base, s)).violations.length);
  for (let i = 1; i < counts.length; i++) {
    assert.ok(counts[i] <= counts[i - 1], `완화 ${i}단계에서 위반이 늘었다: ${counts}`);
  }
});
