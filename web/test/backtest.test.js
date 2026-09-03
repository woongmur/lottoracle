/** backtest.js — 과거 회차로 추천 성적을 검증하는 부분. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as bt from '../src/backtest.js';
import { createRng } from '../src/rng.js';
import { NUMBER_POOL, PICK } from '../src/metrics.js';

const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
// 가벼운 추천기: 무작위 5줄. 백테스트 골격만 검사한다.
const randomRecommender = (history, rng) =>
  Array.from({ length: 5 }, () => rng.sample(NUMBER_POOL, PICK));

test('지정한 회차 수만큼 돌고 장수가 맞는다', () => {
  const r = bt.run(draws, randomRecommender, { rounds: 20, seed: 1 });
  assert.equal(r.rounds, 20);
  assert.equal(bt.tickets(r), 100);
  assert.equal(bt.spent(r), 100000);
});

test('등수 집계 합이 전체 장수와 같다', () => {
  const r = bt.run(draws, randomRecommender, { rounds: 30, seed: 2 });
  const sum = o => Object.values(o).reduce((a, b) => a + b, 0);
  assert.equal(sum(r.modelRanks), bt.tickets(r));
  assert.equal(sum(r.randomRanks), bt.tickets(r));
});

test('같은 시드는 같은 결과를 낸다', () => {
  const a = bt.run(draws, randomRecommender, { rounds: 15, seed: 7 });
  const b = bt.run(draws, randomRecommender, { rounds: 15, seed: 7 });
  assert.deepEqual(a.modelRanks, b.modelRanks);
  assert.equal(a.modelPrize, b.modelPrize);
});

test('과거 데이터가 모자란 회차는 건너뛴다', () => {
  const few = draws.slice(0, 60);
  const r = bt.run(few, randomRecommender, { rounds: 50, seed: 1, minHistory: 50 });
  assert.ok(r.rounds < 50, `기록이 짧으면 덜 돌아야 한다: ${r.rounds}`);
  assert.ok(r.rounds > 0);
});

test('추천기에 미래 데이터가 새지 않는다', () => {
  const seen = [];
  bt.run(draws, (history, rng) => {
    seen.push(history[history.length - 1].no);
    return [rng.sample(NUMBER_POOL, PICK)];
  }, { rounds: 5, seed: 1 });
  const targets = draws.slice(-5).map(d => d.no);
  seen.forEach((lastSeen, i) => {
    assert.equal(lastSeen, targets[i] - 1, `${targets[i]}회 추천에 직전 회차까지만 보여야 한다`);
  });
});

test('endNo 를 주면 그 이후 회차는 아예 없는 셈이 된다', () => {
  const seen = [];
  bt.run(draws, (history, rng) => {
    seen.push(history[history.length - 1].no);
    return [rng.sample(NUMBER_POOL, PICK)];
  }, { rounds: 3, seed: 1, endNo: 1000 });
  assert.ok(Math.max(...seen) < 1000);
});

test('요약 페이로드가 화면 규격에 맞는다', () => {
  const p = bt.payload(bt.run(draws, randomRecommender, { rounds: 20, seed: 3 }));
  assert.equal(p.rows.length, 5);
  assert.deepEqual(p.rows.map(r => r.rank), ['1등', '2등', '3등', '4등', '5등']);
  for (const row of p.rows) {
    assert.ok(Number.isInteger(row.model) && Number.isInteger(row.random));
    assert.ok(row.expected >= 0);
  }
  assert.ok(p.modelRoi >= 0 && p.randomRoi >= 0);
  assert.ok(p.best.length <= 10);
  for (const b of p.best) assert.equal(b.numbers.length, 6);
});

test('이론 기대 횟수가 확률과 맞는다', () => {
  const r = bt.run(draws, randomRecommender, { rounds: 100, seed: 5 });
  const exp = bt.expectedRanks(r);
  // 5등(3개 일치)은 500장이면 대략 11장쯤 기대된다
  assert.ok(exp[5] > 10 && exp[5] < 13, `5등 기대치가 이상하다: ${exp[5]}`);
  assert.ok(exp[1] < 0.001, '1등 기대치는 0에 가까워야 한다');
});

test('무작위 추천의 5등 횟수가 이론 기대와 크게 다르지 않다', () => {
  const r = bt.run(draws, randomRecommender, { rounds: 200, seed: 11 });
  const exp = bt.expectedRanks(r)[5];
  const got = r.randomRanks[5];
  assert.ok(Math.abs(got - exp) < exp * 1.5 + 5, `5등 ${got}회 vs 기대 ${exp.toFixed(1)}회`);
});

test('진행 상황을 알려 준다', () => {
  const seen = [];
  bt.run(draws, randomRecommender, { rounds: 10, seed: 1, onProgress: (d, t) => seen.push([d, t]) });
  assert.equal(seen.length, 10);
  assert.deepEqual(seen[0], [1, 10]);
  assert.deepEqual(seen[9], [10, 10]);
});
