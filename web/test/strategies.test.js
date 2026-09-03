/** strategies.js 의 정의값이 파이썬 lottoracle.strategies 와 같은지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DEFAULT_STRATEGIES, byKey } from '../src/strategies.js';

const golden = JSON.parse(readFileSync(new URL('./golden/strategies.json', import.meta.url)));

test('전략 순서와 개수가 같다', () => {
  assert.deepEqual(DEFAULT_STRATEGIES.map(s => s.key), golden.keys);
});

test('전략별 가중치·규칙이 모두 같다', () => {
  golden.items.forEach((want, i) => {
    const got = DEFAULT_STRATEGIES[i];
    for (const key of Object.keys(want)) {
      assert.deepEqual(got[key], want[key], `${want.key} 의 ${key}`);
    }
  });
});

test('byKey 는 전략을 찾고, 모르는 키는 거절한다', () => {
  assert.equal(byKey('balance').name, '안정형 밸런스');
  assert.equal(byKey('aggressive').carryoverTarget, 0);
  assert.throws(() => byKey('없는전략'), /알 수 없는 전략/);
});

test('이월수 전략은 이월 상한이 풀려 있다', () => {
  assert.deepEqual(byKey('carryover').rules.carryoverRange, [1, 3]);
  assert.deepEqual(byKey('aggressive').rules.carryoverRange, [0, 0]);
});
