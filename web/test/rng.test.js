/** rng.js — 파이썬과 값은 다르지만 '같은 시드면 같은 결과'와 분포 성질은 지켜야 한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRng, hashSeed } from '../src/rng.js';

test('같은 시드는 같은 수열을 낸다', () => {
  const a = createRng(12345), b = createRng(12345);
  for (let i = 0; i < 500; i++) assert.equal(a.random(), b.random());
});

test('다른 시드는 다른 수열을 낸다', () => {
  const a = createRng(1), b = createRng(2);
  const seqA = Array.from({ length: 20 }, () => a.random());
  const seqB = Array.from({ length: 20 }, () => b.random());
  assert.notDeepEqual(seqA, seqB);
});

test('문자열 시드도 결정론적이다', () => {
  const a = createRng('fortune|2026-09-03|홍길동');
  const b = createRng('fortune|2026-09-03|홍길동');
  assert.equal(a.random(), b.random());
  assert.notEqual(hashSeed('a'), hashSeed('b'));
  assert.equal(hashSeed('같은문자열'), hashSeed('같은문자열'));
});

test('random() 은 [0,1) 범위에 고르게 든다', () => {
  const rng = createRng(7);
  const buckets = new Array(10).fill(0);
  const N = 100000;
  for (let i = 0; i < N; i++) {
    const v = rng.random();
    assert.ok(v >= 0 && v < 1, `범위 밖: ${v}`);
    buckets[Math.floor(v * 10)]++;
  }
  for (const [i, count] of buckets.entries()) {
    const ratio = count / N;
    assert.ok(ratio > 0.085 && ratio < 0.115, `${i}번 구간 편중: ${ratio}`);
  }
});

test('sample 은 중복 없이 k개를 뽑고 원본을 건드리지 않는다', () => {
  const rng = createRng(3);
  const pool = Array.from({ length: 45 }, (_, i) => i + 1);
  const copy = [...pool];
  for (let i = 0; i < 200; i++) {
    const picked = rng.sample(pool, 6);
    assert.equal(picked.length, 6);
    assert.equal(new Set(picked).size, 6);
    for (const n of picked) assert.ok(n >= 1 && n <= 45);
  }
  assert.deepEqual(pool, copy);
  assert.equal(rng.sample([1, 2], 5).length, 2);   // 풀보다 크게 요청해도 안전
});

test('weighted 는 가중치를 따른다', () => {
  const rng = createRng(11);
  const counts = { a: 0, b: 0, c: 0 };
  for (let i = 0; i < 30000; i++) counts[rng.weighted(['a', 'b', 'c'], [8, 1, 1])]++;
  assert.ok(counts.a / 30000 > 0.75, `a 비중이 낮다: ${counts.a / 30000}`);
  assert.ok(counts.b > 0 && counts.c > 0, '0 아닌 가중치는 뽑혀야 한다');
});

test('가중치 0 인 항목은 절대 안 뽑힌다', () => {
  const rng = createRng(5);
  for (let i = 0; i < 5000; i++) {
    assert.notEqual(rng.weighted(['안됨', '됨'], [0, 1]), '안됨');
  }
});

test('가중치 합이 0이면 균등 추첨으로 떨어진다', () => {
  const rng = createRng(9);
  const seen = new Set();
  for (let i = 0; i < 300; i++) seen.add(rng.weighted(['x', 'y', 'z'], [0, 0, 0]));
  assert.equal(seen.size, 3);
});

test('choice 는 항상 목록 안의 값을 준다', () => {
  const rng = createRng(2);
  const pool = [10, 20, 30];
  for (let i = 0; i < 500; i++) assert.ok(pool.includes(rng.choice(pool)));
});
