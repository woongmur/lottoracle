/** sipsin.js — 십신·신살·강약. 파이썬 lottoracle/sipsin.py 와 대조한다.
 *
 * 문구가 두 언어에서 한 글자라도 달라지면 화면만 조용히 달라진다. 그래서
 * 계산뿐 아니라 문구표까지 통째로 골든과 맞춰 본다.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as sp from '../src/sipsin.js';
import * as sj from '../src/saju.js';

const G = JSON.parse(readFileSync(new URL('./golden/sipsin.json', import.meta.url)));

/** '경진' 같은 두 글자로 기둥 하나. */
function P(name) {
  return { stem: sj.STEMS.indexOf(name[0]), branch: sj.BRANCHES.indexOf(name[1]) };
}
function chart(text) {
  return text.split(' ').map(P);
}
function pillarsOf(args) {
  const s = sj.fourPillars(...args);
  return [s.year, s.month, s.day, s.hour];
}

test('표가 파이썬과 같다', () => {
  assert.deepEqual(sp.TEN_GODS, G.tenGods);
  assert.deepEqual(sp.BRANCH_MAIN_QI, G.branchMainQi);
  assert.deepEqual(sp.SUPPORTING, G.supporting);
  assert.deepEqual(sp.GOD_GROUP, G.godGroup);
  assert.deepEqual(Object.fromEntries(
    Object.entries(sp.NOBLEMAN).map(([k, v]) => [k, v])), G.nobleman);
  assert.deepEqual(Object.fromEntries(
    Object.entries(sp.SCHOLAR).map(([k, v]) => [k, v])), G.scholar);
});

test('십신 100칸이 파이썬과 같다', () => {
  for (let d = 0; d < 10; d += 1) {
    const row = Array.from({ length: 10 }, (_, t) => sp.tenGod(d, t));
    assert.deepEqual(row, G.stemMatrix[d], `일간 ${sj.STEMS[d]}`);
  }
});

test('지지 십신 120칸이 파이썬과 같다', () => {
  for (let d = 0; d < 10; d += 1) {
    const row = Array.from({ length: 12 }, (_, b) => sp.tenGodOfBranch(d, b));
    assert.deepEqual(row, G.branchMatrix[d], `일간 ${sj.STEMS[d]}`);
  }
});

test('문구가 파이썬과 한 글자도 다르지 않다', () => {
  assert.deepEqual(sp.DAY_STEM_TEXT, G.texts.dayStem);
  assert.deepEqual(sp.TEN_GOD_TEXT, G.texts.tenGod);
  assert.deepEqual(sp.SINSAL_TEXT, G.texts.sinsal);
  assert.deepEqual(sp.GROUP_MANY_TEXT, G.texts.groupMany);
  assert.deepEqual(sp.GROUP_NONE_TEXT, G.texts.groupNone);
  assert.deepEqual(sp.STRENGTH_TEXT, G.texts.strength);
  assert.equal(sp.ELEMENTS_FULL_TEXT, G.texts.elementsFull);
});

test('풀이가 파이썬과 같다', () => {
  for (const c of G.cases) {
    const ps = pillarsOf(c.in);
    const r = sp.reading(ps, ps[2].stem, sj.elementsCount(ps));
    const table = r.table.map(t => ({
      pillar: t.pillar, stemChar: t.stemChar, branchChar: t.branchChar,
      stem: t.stem, branch: t.branch,
    }));
    assert.deepEqual(table, c.table, `${c.in} 십신표`);
    assert.deepEqual(r.counts, c.counts, `${c.in} 개수`);
    assert.deepEqual(r.groups, c.groups, `${c.in} 갈래`);
    assert.deepEqual(r.strength, { ...c.strength, text: r.strength.text }, `${c.in} 강약`);
    assert.equal(r.strength.label, c.strength.label, `${c.in} 강약 이름`);
    assert.deepEqual(r.sinsal.map(s => ({ name: s.name, at: s.at })), c.sinsal, `${c.in} 신살`);
    assert.deepEqual(r.strong.map(s => s.name), c.strong, `${c.in} 강한 십신`);
    assert.deepEqual(r.manyGroups.map(s => s.name), c.manyGroups, `${c.in} 많은 갈래`);
    assert.deepEqual(r.noneGroups.map(s => s.name), c.noneGroups, `${c.in} 없는 갈래`);
    assert.equal(r.elementsNote, c.elementsNote, `${c.in} 오행 한 줄`);
  }
});

test('시주를 모를 때도 파이썬과 같다', () => {
  for (const c of G.threePillarCases) {
    const ps = pillarsOf(c.in).slice(0, 3);
    const r = sp.reading(ps, ps[2].stem, sj.elementsCount(ps));
    assert.equal(r.table.length, 3, `${c.in} 세 기둥`);
    assert.deepEqual(r.counts, c.counts, `${c.in} 개수`);
    assert.deepEqual(r.strength.support, c.strength.support, `${c.in} 돕는 기운`);
    assert.deepEqual(r.sinsal.map(s => s.name), c.sinsal.map(s => s.name), `${c.in} 신살`);
  }
});

test('나와 같은 글자는 비견이다', () => {
  for (let d = 0; d < 10; d += 1) assert.equal(sp.tenGod(d, d), '비견');
});

test("'정' 이 붙는 쪽은 음양이 다르다", () => {
  const paired = new Set(['겁재', '상관', '정재', '정관', '정인']);
  for (let d = 0; d < 10; d += 1) {
    for (let t = 0; t < 10; t += 1) {
      const same = sj.STEM_YIN[d] === sj.STEM_YIN[t];
      assert.equal(paired.has(sp.tenGod(d, t)), !same, `${d}->${t}`);
    }
  }
});

test('정화 일간의 해수는 정관이다', () => {
  assert.equal(sp.tenGodOfBranch(sj.STEMS.indexOf('정'), 11), '정관');
});

test('일간은 세지 않는다', () => {
  const ps = chart('경진 정해 정해 갑진');
  const counts = sp.tenGodCounts(ps, ps[2].stem);
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  assert.equal(total, 7, "여덟 글자 중 일간은 '나' 라서 뺀다");
});

test('월지가 두 몫이다', () => {
  const ps = chart('경진 정해 정해 갑진');
  const st = sp.strength(ps, ps[2].stem);
  assert.equal(st.support + st.other, 8);
  assert.equal(sp.strength(ps.slice(0, 3), ps[2].stem).support
    + sp.strength(ps.slice(0, 3), ps[2].stem).other, 6);
});

test('프로필에 풀이가 함께 실려 온다', () => {
  const r = sj.fromProfile({ birthDate: '1990-05-21', birthHour: 4, birthBranch: '인' }, '말');
  assert.ok(r.reading, '풀이가 있어야 한다');
  assert.equal(r.reading.table.length, 4);
  assert.equal(r.reading.dayStem.char, r.dayStem);
});

test('시주를 모르면 세 기둥만 읽는다', () => {
  const r = sj.fromProfile({ birthDate: '1990-05-21', birthHour: null, birthBranch: '' }, '말');
  assert.equal(r.hourKnown, false);
  assert.equal(r.reading.table.length, 3, '모르는 시주를 지어내지 않는다');
  const total = Object.values(r.reading.counts).reduce((a, b) => a + b, 0);
  assert.equal(total, 5);
});
