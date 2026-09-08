/** daeun.js — 대운. 파이썬 lottoracle/daeun.py 와 대조한다.
 *
 * 절입 시각이 초 단위로 어긋나면 대운수가 하루 차이로 갈리므로 시각까지 맞춰 본다.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import * as dn from '../src/daeun.js';
import * as sj from '../src/saju.js';

const G = JSON.parse(readFileSync(new URL('./golden/daeun.json', import.meta.url)));

test('방향 20칸이 파이썬과 같다', () => {
  for (let st = 0; st < 10; st += 1) {
    assert.deepEqual([dn.isForward(st, true), dn.isForward(st, false)],
      G.direction[st], `년간 ${sj.STEMS[st]}`);
  }
});

test('절입 시각이 파이썬과 1초 안에서 같다', () => {
  for (const c of G.jeol) {
    const e = sj.fourPillars(...c.in).utcEpoch;
    const [nn, nt] = sj.nextJeol(e);
    const [pn, pt] = sj.prevJeol(e);
    assert.equal(nn, c.next[0], `${c.in} 다음 절 이름`);
    assert.equal(pn, c.prev[0], `${c.in} 지난 절 이름`);
    assert.ok(Math.abs(nt - c.next[1]) < 1, `${c.in} 다음 절 시각`);
    assert.ok(Math.abs(pt - c.prev[1]) < 1, `${c.in} 지난 절 시각`);
  }
});

test('대운이 파이썬과 같다', () => {
  for (const c of G.cases) {
    const s = sj.fourPillars(...c.in);
    const d = dn.daeun(s.year, s.month, s.day.stem, s.utcEpoch, c.gender, 30.0);
    const tag = `${c.in} ${c.gender}`;
    assert.equal(d.forward, c.forward, `${tag} 방향`);
    assert.equal(d.reason, c.reason, `${tag} 사유`);
    assert.equal(d.start.jeol, c.start.jeol, `${tag} 절`);
    assert.equal(d.start.number, c.start.number, `${tag} 대운수`);
    assert.ok(Math.abs(d.start.days - c.start.days) < 0.02, `${tag} 날수`);
    assert.deepEqual(d.list.map(r => ({
      index: r.index, from: r.from, to: r.to, name: r.name, hanja: r.hanja,
      stemGod: r.stemGod, branchGod: r.branchGod, now: r.now,
    })), c.list, `${tag} 대운표`);
    assert.equal(d.current ? d.current.name : null, c.current, `${tag} 지금`);
    assert.equal(d.beforeFirst, c.beforeFirst, `${tag} 첫 대운 전`);
  }
});

test('문구가 파이썬과 같다', () => {
  assert.equal(dn.INTRO, G.texts.intro);
  assert.equal(dn.BEFORE_FIRST, G.texts.beforeFirst);
  assert.equal(dn.NO_GENDER, G.texts.noGender);
  assert.equal(dn.COUNT, G.count);
});

test('중기는 절로 잡히지 않는다', () => {
  const jeol = new Set(['입춘', '경칩', '청명', '입하', '망종', '소서',
    '입추', '백로', '한로', '입동', '대설', '소한']);
  const base = sj.fourPillars(2000, 1, 1, 12, 0).utcEpoch;
  for (let k = 0; k < 200; k += 1) {
    assert.ok(jeol.has(sj.nextJeol(base + k * 86400 * 3)[0]), `${k}번째`);
  }
});

test('월주에서 한 칸씩 옮긴다', () => {
  const s = sj.fourPillars(2000, 11, 25, 8, 30);       // 월주 정해
  assert.deepEqual(dn.pillarsFrom(s.month, true).slice(0, 3).map(p => p.name),
    ['무자', '기축', '경인']);
  assert.deepEqual(dn.pillarsFrom(s.month, false).slice(0, 3).map(p => p.name),
    ['병술', '을유', '갑신']);
});

test('60갑자 번호를 되짚는다', () => {
  for (let i = 0; i < 60; i += 1) {
    assert.equal(dn.gzIndex({ stem: i % 10, branch: i % 12 }), i);
  }
});

test('성별을 모르면 세우지 않는다', () => {
  const s = sj.fourPillars(2000, 11, 25, 8, 30);
  for (const g of ['', '몰라', null, undefined]) {
    assert.equal(dn.daeun(s.year, s.month, s.day.stem, s.utcEpoch, g), null, String(g));
  }
});

test('지금 어느 칸인지 한 곳만 짚는다', () => {
  const s = sj.fourPillars(2000, 11, 25, 8, 30);
  const d = dn.daeun(s.year, s.month, s.day.stem, s.utcEpoch, '남', 25.8);
  assert.equal(d.current.name, '경인');
  assert.equal(d.list.filter(r => r.now).length, 1);
  assert.equal(dn.daeun(s.year, s.month, s.day.stem, s.utcEpoch, '남', 2.0).current, null);
  assert.equal(dn.daeun(s.year, s.month, s.day.stem, s.utcEpoch, '남', 95.0).current, null);
});

test('프로필에 실려 대운까지 간다', () => {
  const p = { birthDate: '2000-11-25', birthBranch: '진', birthHour: null, gender: '남' };
  const r = sj.fromProfile(p, '용', '2026-09-08');
  assert.equal(r.daeun.current.name, '경인');
});

test('성별이 없어도 팔자는 그대로다', () => {
  const base = { birthDate: '2000-11-25', birthBranch: '진', birthHour: null };
  const a = sj.fromProfile({ ...base }, '용', '2026-09-08');
  const b = sj.fromProfile({ ...base, gender: '남' }, '용', '2026-09-08');
  assert.equal(a.eightChars, b.eightChars);
  assert.deepEqual(a.reading, b.reading);
  assert.equal(a.daeun, null);
  assert.ok(b.daeun);
});
