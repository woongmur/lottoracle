/** 일본 로또 번호 저장 — 한국 번호와 다른 서랍, 백업·복원, 손상값 거르기. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createStorage } from '../src/storage.js';

function memory() {
  const map = new Map();
  return { getItem: k => (map.has(k) ? map.get(k) : null), setItem: (k, v) => map.set(k, String(v)), removeItem: k => map.delete(k), map };
}

test('게임마다 번호 개수·범위를 검사해 저장한다', () => {
  const st = createStorage(memory());
  const r = st.addJpPick('loto7', [[37, 1, 2, 3, 4, 5, 6]], 699, '2026-10-16', '추천');
  assert.deepEqual(r.lines, [[1, 2, 3, 4, 5, 6, 37]]);
  assert.equal(r.game, 'loto7');
  assert.equal(r.targetDate, '2026-10-16');
  st.addJpPick('miniloto', [[1, 2, 3, 4, 31]], 1409);
  assert.throws(() => st.addJpPick('loto6', [[1, 2, 3, 4, 5, 44]], 2146), /1~43/);
  assert.throws(() => st.addJpPick('miniloto', [[1, 2, 3, 4, 5, 6]], 1409), /5개/);
  assert.throws(() => st.addJpPick('loto8', [[1, 2, 3]], 1), /모르는 게임/);
  assert.equal(st.listJpPicks().length, 2);
});

test('한국 번호와 섞이지 않는다', () => {
  const st = createStorage(memory());
  st.addPick([[1, 2, 3, 4, 5, 6]], 1246);
  st.addJpPick('loto6', [[1, 2, 3, 4, 5, 6]], 2146);
  assert.equal(st.listPicks().length, 1);
  assert.equal(st.listJpPicks().length, 1);
  assert.equal(st.listPicks()[0].game, undefined, '한국 쪽에는 game 칸이 없다');
});

test('손상된 값은 읽을 때 거른다', () => {
  const mem = memory();
  mem.setItem('lottoracle.jppicks', JSON.stringify([
    { id: 'a', game: 'loto7', targetDraw: 1, lines: [[1, 2, 3, 4, 5, 6, 7]] },
    { id: 'b', game: 'loto7', targetDraw: 1, lines: [[1, 2, 3, 4, 5, 6]] },        // 6개
    { id: 'c', game: 'miniloto', targetDraw: 1, lines: [[1, 2, 3, 4, 32]] },        // 범위 밖
    { id: 'd', game: 'loto6', targetDraw: 1, lines: [[1, 1, 2, 3, 4, 5]] },         // 중복
    { id: 'e', targetDraw: 1, lines: [[1, 2, 3, 4, 5, 6]] },                        // 게임 없음
  ]));
  assert.deepEqual(createStorage(mem).listJpPicks().map(p => p.id), ['a']);
});

test('지우기·백업·복원·모두 지우기', () => {
  const st = createStorage(memory());
  const a = st.addJpPick('loto6', [[1, 2, 3, 4, 5, 6]], 2146);
  st.addJpPick('loto7', [[1, 2, 3, 4, 5, 6, 7]], 699);
  const dump = st.exportAll();
  assert.equal(dump.jpPicks.length, 2);

  const other = createStorage(memory());
  const r = other.importAll(JSON.parse(JSON.stringify(dump)));
  assert.equal(r.jpAdded, 2);
  assert.equal(other.importAll(dump).jpAdded, 0, '같은 백업을 다시 넣어도 중복되지 않는다');
  assert.equal(other.importAll({ app: 'lottoracle', picks: [] }).jpAdded, 0, '일본 칸이 없는 예전 백업');

  assert.equal(st.deleteJpPick(a.id), true);
  assert.equal(st.deleteJpPick('없음'), false);
  assert.equal(st.listJpPicks().length, 1);
  st.clearAll();
  assert.equal(st.listJpPicks().length, 0);
});

test('설정에 모드와 마지막 게임을 남긴다', () => {
  const st = createStorage(memory());
  st.saveSettings({ mode: 'jp', jpGame: 'miniloto', nope: 1 });
  assert.deepEqual(st.loadSettings(), { mode: 'jp', jpGame: 'miniloto' });
});
