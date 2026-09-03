/** folklore.js 가 파이썬 lottoracle.folklore 와 같은 값·문구를 내는지 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as fk from '../src/folklore.js';
import { NUMBER_POOL } from '../src/metrics.js';

const golden = JSON.parse(readFileSync(new URL('./golden/folklore.json', import.meta.url)));
const PREV = { no: 1239, numbers: [11, 13, 22, 32, 33, 36], bonus: 8 };
const FL = fk.createFolklore({ lucky: [7, 13], avoid: [4], dream: '돼지꿈', birthday: '1990-05-21', zodiac: '말' });
const FL_OFF = fk.createFolklore({ enabled: false });

test('볼 색상과 숫자 성질 상수가 같다', () => {
  for (const [n, want] of Object.entries(golden.ballColor)) {
    assert.equal(fk.ballColor(Number(n)), want, `${n}번 색`);
  }
  assert.deepEqual(fk.PRIME_NUMBERS, golden.primes);
  assert.deepEqual(fk.FIBONACCI_NUMBERS, golden.fibonacci);
  assert.throws(() => fk.ballColor(0), /범위를 벗어난/);
  assert.throws(() => fk.ballColor(46), /범위를 벗어난/);
});

test('용지 좌표와 이웃수가 같다', () => {
  for (const [n, want] of Object.entries(golden.slipPositions)) {
    assert.deepEqual(fk.slipPosition(Number(n)), want, `${n}번 좌표`);
  }
  assert.deepEqual([...fk.neighborNumbers(PREV)].sort((a, b) => a - b), golden.neighborsOfPrev);
  assert.equal(fk.neighborNumbers(null).size, 0);
});

test('꿈수·띠수·생일수가 같다', () => {
  for (const [k, want] of Object.entries(golden.dream)) assert.deepEqual(fk.dreamNumbers(k), want, `꿈 "${k}"`);
  for (const [k, want] of Object.entries(golden.zodiac)) assert.deepEqual(fk.zodiacNumbers(k), want, `띠 "${k}"`);
  for (const [k, want] of Object.entries(golden.birthday)) assert.deepEqual(fk.birthdayNumbers(k), want, `생일 "${k}"`);
  for (const [y, want] of Object.entries(golden.zodiacOfYear)) {
    assert.equal(fk.zodiacOfYear(Number(y)), want, `${y}년생 띠`);
  }
});

test('잘못된 생일은 조용히 무시한다', () => {
  // 13월 40일은 무효한 날짜라 월·일 도출은 건너뛰고, 1~45 범위의 숫자만 주워 담는다
  assert.deepEqual(fk.birthdayNumbers('1990-13-40'), [13, 40]);
  assert.deepEqual(fk.birthdayNumbers('90-05-21'), [3, 5, 21]);   // 두 자리 연도도 처리
  assert.deepEqual(fk.birthdayNumbers('어제'), []);
  assert.deepEqual(fk.birthdayNumbers(''), []);
});

test('조합별 색상·용지·동형수·판정·점수·태그가 모두 같다', () => {
  for (const c of golden.cases) {
    const n = c.numbers;
    assert.deepEqual(fk.colorCounts(n), c.colorCounts, `${n} 색상 개수`);
    assert.equal(fk.colorSignature(n), c.colorSignature, `${n} 색상 표기`);
    assert.equal(fk.isSlipLine(n), c.isSlipLine, `${n} 용지 직선`);
    assert.equal(fk.slipClusterPenalty(n), c.slipCluster, `${n} 용지 뭉침`);
    const groups = Object.fromEntries([...fk.sameEndingGroups(n)].map(([k, v]) => [String(k), v]));
    assert.deepEqual(groups, c.sameEndingGroups, `${n} 동형수`);
    assert.equal(fk.accepts(FL, n), c.acceptsOn, `${n} 속설 통과`);
    assert.equal(fk.accepts(FL, n, true), c.acceptsLenient, `${n} 완화 통과`);
    assert.equal(fk.luckScore(FL, n, PREV), c.luckScoreOn, `${n} 기분점수`);
    assert.equal(fk.luckScore(FL_OFF, n, PREV), c.luckScoreOff, `${n} 기분점수(속설 끔)`);
    assert.deepEqual(fk.luckTags(FL, n, PREV), c.luckTags, `${n} 태그`);
  }
});

test('행운수 묶음·제외수·설명 문구가 같다', () => {
  assert.deepEqual(fk.wishNumbers(FL), golden.wishNumbers);
  assert.deepEqual([...fk.excluded(FL)].sort((a, b) => a - b), golden.excluded);
  assert.deepEqual(fk.describe(FL), golden.describe);
});

test('번호별 가중 배수가 같다 (켬/끔/직전 회차 없음)', () => {
  const cases = [
    [fk.multipliers(FL, PREV), golden.multipliersOn, '켬'],
    [fk.multipliers(FL_OFF, PREV), golden.multipliersOff, '끔'],
    [fk.multipliers(FL, null), golden.multipliersNoPrev, '직전 없음'],
  ];
  for (const [got, want, label] of cases) {
    for (const n of NUMBER_POOL) {
      const a = got.get(n), b = want[String(n)];
      assert.ok(Math.abs(a - b) < 1e-12, `${label} ${n}번: ${a} != ${b}`);
    }
  }
});

test('기피수는 배수 0, 행운수는 1보다 크다', () => {
  const m = fk.multipliers(FL, PREV);
  assert.equal(m.get(4), 0);
  assert.ok(m.get(7) > 1);
  assert.ok(m.get(13) > 1);
});

test('행운수와 기피수가 겹치면 기피수가 이긴다', () => {
  const fl = fk.createFolklore({ lucky: [4, 7], avoid: [4] });
  assert.ok(!fk.wishNumbers(fl).includes(4));
  assert.equal(fk.multipliers(fl, null).get(4), 0);
});

test('속설을 끄면 모든 배수가 1.0', () => {
  const m = fk.multipliers(FL_OFF, PREV);
  for (const n of NUMBER_POOL) assert.equal(m.get(n), 1.0);
  assert.equal(fk.accepts(FL_OFF, [1, 2, 3, 4, 5, 6]), true);
});
