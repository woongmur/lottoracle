/** saju.js — 사주팔자. 파이썬 lottoracle/saju.py 와 대조한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as sj from '../src/saju.js';
import { epochToParts } from '../src/solartime.js';

const G = JSON.parse(readFileSync(new URL('./golden/saju.json', import.meta.url)));

test('글자표가 파이썬과 같다', () => {
  assert.equal(sj.STEMS, G.stems);
  assert.equal(sj.BRANCHES, G.branches);
  assert.deepEqual(sj.ELEMENTS, G.elements);
  assert.deepEqual(sj.BRANCH_ANIMALS, G.animals);
});

test('입춘 시각이 파이썬과 1초 안에서 같다', () => {
  for (const [year, epoch] of Object.entries(G.lichun)) {
    assert.ok(Math.abs(sj.lichunEpoch(Number(year)) - epoch) < 1, `${year} 입춘`);
  }
});

test('팔자가 파이썬과 같다', () => {
  for (const c of G.cases) {
    const r = sj.fourPillars(...c.in);
    assert.equal(r.eightChars, c.eightChars, `${c.in} 팔자`);
    assert.equal(r.hanja, c.hanja, `${c.in} 한자`);
    assert.equal(r.sign, c.sign, `${c.in} 별자리`);
    assert.equal(r.solarTime, c.solarTime, `${c.in} 태양시`);
    assert.equal(r.lateNight, c.lateNight, `${c.in} 야자시`);
    assert.ok(Math.abs(r.correctionMinutes - c.correctionMinutes) < 0.05, `${c.in} 보정`);
    assert.ok(Math.abs(r.hourEdgeMinutes - c.hourEdgeMinutes) < 0.05, `${c.in} 경계`);
    assert.deepEqual(r.elements, c.elements, `${c.in} 오행`);
    for (const k of ['year', 'month', 'day', 'hour']) {
      assert.equal(r[k].name, c[k].name, `${c.in} ${k}주`);
      assert.equal(r[k].stemElement, c[k].stemElement, `${c.in} ${k} 천간오행`);
      assert.equal(r[k].branchElement, c[k].branchElement, `${c.in} ${k} 지지오행`);
      assert.equal(r[k].yin, c[k].yin, `${c.in} ${k} 음양`);
    }
  }
});

// ---- 성질 검사

test('60갑자가 겹치지 않고 한 바퀴 돈다', () => {
  const base = sj.dayPillar(0);
  const names = new Set();
  for (let k = 0; k < 60; k += 1) names.add(sj.dayPillar(k * 86400).name);
  assert.equal(names.size, 60);
  assert.equal(sj.dayPillar(60 * 86400).name, base.name, '61일째면 제자리');
});

test('일주는 하루마다 하나씩 넘어간다', () => {
  for (let k = 1; k < 200; k += 1) {
    const a = sj.dayPillar((k - 1) * 86400 + 43200);
    const b = sj.dayPillar(k * 86400 + 43200);
    assert.equal((a.stem + 1) % 10, b.stem, `${k}일째 천간`);
    assert.equal((a.branch + 1) % 12, b.branch, `${k}일째 지지`);
  }
});

test('시지 경계 — 23~01시가 자시', () => {
  assert.equal(sj.hourBranchOf(23), 0);
  assert.equal(sj.hourBranchOf(0), 0);
  assert.equal(sj.hourBranchOf(1), 1);
  assert.equal(sj.hourBranchOf(12), 6);
});

test('입춘 앞뒤로 년주가 갈린다 — 설날이 아니다', () => {
  assert.equal(sj.fourPillars(1998, 2, 1, 12, 0).year.name, '정축');   // 아직 1997년
  assert.equal(sj.fourPillars(1998, 2, 10, 12, 0).year.name, '무인');  // 1998년
});

test('오행은 언제나 여덟 글자', () => {
  for (const args of [[1900, 1, 1, 0, 0], [1954, 6, 15, 13, 20], [2026, 12, 31, 23, 59]]) {
    const r = sj.fourPillars(...args);
    const total = Object.values(r.elements).reduce((a, b) => a + b, 0);
    assert.equal(total, 8, `${args}`);
  }
});

test('보정이 태양시 날짜를 되돌리기도 한다', () => {
  // 벽시계 00:10 은 서울 태양시로 전날 23:37. 일주가 전날 것이 된다.
  const r = sj.fourPillars(2026, 1, 5, 0, 10);
  assert.equal(r.solarTime, '2026-01-04 23:37');
  assert.equal(r.day.name, sj.fourPillars(2026, 1, 4, 12, 0).day.name);
});
