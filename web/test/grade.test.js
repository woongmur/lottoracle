/** grade.js — 등수 판정과 당첨금 계산. 파이썬 backtest.grade / engine._graded_rows 대응. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as g from '../src/grade.js';

const draws = JSON.parse(readFileSync(new URL('../data/draws.json', import.meta.url)));
const WIN = [11, 13, 22, 32, 33, 36];
const BONUS = 8;
const DRAW_BARE = { no: 1239, numbers: WIN, bonus: BONUS };
const DRAW_FULL = {
  ...DRAW_BARE,
  prizes: [
    { rank: 1, winners: 13, amount: 2214789375 }, { rank: 2, winners: 71, amount: 67587470 },
    { rank: 3, winners: 3081, amount: 1557518 }, { rank: 4, winners: 152825, amount: 50000 },
    { rank: 5, winners: 2570542, amount: 5000 },
  ],
};

test('등수 판정이 정확하다', () => {
  const cases = [
    [[11, 13, 22, 32, 33, 36], 1, '6개'],
    [[11, 13, 22, 32, 33, 8], 2, '5개+보너스'],
    [[11, 13, 22, 32, 33, 45], 3, '5개'],
    [[11, 13, 22, 32, 44, 45], 4, '4개'],
    [[11, 13, 22, 43, 44, 45], 5, '3개'],
    [[11, 13, 41, 43, 44, 45], 0, '2개'],
    [[1, 2, 3, 4, 5, 7], 0, '0개'],
  ];
  for (const [nums, want, label] of cases) {
    assert.equal(g.rankOf(nums, DRAW_BARE), want, `${label} → ${want}등`);
  }
});

test('보너스는 5개 맞았을 때만 등수를 가른다', () => {
  assert.equal(g.rankOf([11, 13, 22, 32, 44, 8], DRAW_BARE), 4);   // 4개 + 보너스는 여전히 4등
  assert.equal(g.rankOf([11, 13, 22, 43, 44, 8], DRAW_BARE), 5);   // 3개 + 보너스는 5등
});

test('회차에 실제 당첨금이 있으면 그 금액을 쓴다', () => {
  const r = g.grade([[11, 13, 22, 32, 33, 36], [11, 13, 22, 32, 33, 45]], DRAW_FULL);
  assert.equal(r.actualPrize, true);
  assert.equal(r.results[0].prize, 2214789375);
  assert.equal(r.results[1].prize, 1557518);
  assert.equal(r.totalPrize, 2214789375 + 1557518);
  assert.equal(r.bestRank, 1);
});

test('실제 당첨금이 없으면 평균치로 계산하고 그렇게 알린다', () => {
  const r = g.grade([[11, 13, 22, 32, 33, 36]], DRAW_BARE);
  assert.equal(r.actualPrize, false);
  assert.equal(r.results[0].prize, g.RANK_PRIZE[1]);
});

test('낙첨만 있으면 bestRank 는 0', () => {
  const r = g.grade([[1, 2, 3, 4, 5, 7]], DRAW_FULL);
  assert.equal(r.bestRank, 0);
  assert.equal(r.totalPrize, 0);
});

test('결과에 맞힌 번호와 보너스 여부가 담긴다', () => {
  const r = g.grade([[36, 33, 32, 22, 13, 11], [8, 1, 2, 3, 4, 5]], DRAW_FULL);
  assert.deepEqual(r.results[0].numbers, WIN, '입력 순서와 무관하게 정렬된다');
  assert.deepEqual(r.results[0].hit, WIN);
  assert.equal(r.results[0].bonusHit, false);
  assert.equal(r.results[1].bonusHit, true);
  assert.deepEqual(r.results[1].hit, []);
});

test('실제 회차 데이터로 채점해도 등수 분포가 상식적이다', () => {
  const recent = draws.slice(-50);
  for (const d of recent) {
    const self = g.grade([d.numbers], d);
    assert.equal(self.bestRank, 1, `${d.no}회 당첨번호 자신은 1등이어야 한다`);
    if (d.prizes && d.prizes.length === 5) {
      assert.equal(self.actualPrize, true, `${d.no}회는 실제 금액이 있어야 한다`);
      assert.equal(self.results[0].prize, d.prizes[0].amount);
    }
  }
});

test('상금·확률 상수가 파이썬과 같다', () => {
  assert.deepEqual(g.RANK_PRIZE, { 1: 2000000000, 2: 55000000, 3: 1500000, 4: 50000, 5: 5000 });
  assert.equal(g.TICKET_PRICE, 1000);
  assert.equal(g.RANK_LABEL[0], '낙첨');
  assert.ok(Math.abs(g.RANK_ODDS[1] - 1 / 8145060) < 1e-15);
});
