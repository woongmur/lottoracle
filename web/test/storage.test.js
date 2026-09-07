/** storage.js — localStorage 저장소. 메모리 백엔드로 검사한다. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createStorage } from '../src/storage.js';

const fresh = () => {
  const map = new Map();
  return createStorage({
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
  });
};

test('프로필 저장·복원·삭제', () => {
  const s = fresh();
  assert.equal(s.loadProfile(), null);
  s.saveProfile({ name: '홍길동', birthDate: '1990-05-21' });
  assert.equal(s.loadProfile().name, '홍길동');
  s.clearProfile();
  assert.equal(s.loadProfile(), null);
});

test('내 번호 저장·조회·삭제', () => {
  const s = fresh();
  assert.deepEqual(s.listPicks(), []);
  const rec = s.addPick([[36, 33, 22, 13, 11, 32], [1, 2, 3, 4, 5, 6]], 1240, '추천');
  assert.deepEqual(rec.lines[0], [11, 13, 22, 32, 33, 36], '정렬해서 저장한다');
  assert.equal(rec.targetDraw, 1240);
  assert.equal(rec.note, '추천');
  assert.ok(rec.id && rec.savedAt);
  assert.equal(s.listPicks().length, 1);
  assert.equal(s.deletePick(rec.id), true);
  assert.equal(s.deletePick(rec.id), false, '두 번 지워도 안전');
  assert.deepEqual(s.listPicks(), []);
});

test('잘못된 조합은 저장하지 않는다', () => {
  const s = fresh();
  assert.throws(() => s.addPick([[1, 1, 2, 3, 4, 5]], 1240), /서로 다른 번호 6개/);
  assert.throws(() => s.addPick([[1, 2, 3, 4, 5, 46]], 1240), /서로 다른 번호 6개/);
  assert.throws(() => s.addPick([[1, 2, 3, 4, 5]], 1240), /서로 다른 번호 6개/);
  assert.throws(() => s.addPick([], 1240), /저장할 조합이 없습니다/);
  assert.throws(() => s.addPick(Array(21).fill([1, 2, 3, 4, 5, 6]), 1240), /최대 20줄/);
  assert.deepEqual(s.listPicks(), [], '실패한 저장은 남지 않는다');
});

test('설정은 허용된 키만 받는다', () => {
  const s = fresh();
  assert.deepEqual(s.saveSettings({ autoRefresh: false, evil: 1 }), { autoRefresh: false });
  assert.deepEqual(s.saveSettings({ autoRefresh: '' }), {}, '빈 값은 지운다');
});

test('손상된 값은 없는 것으로 본다', () => {
  const map = new Map([['lottoracle.picks', '{망가진 JSON']]);
  const s = createStorage({
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, v), removeItem: k => map.delete(k),
  });
  assert.deepEqual(s.listPicks(), []);
  assert.equal(s.loadProfile(), null);
});

test('저장이 막힌 브라우저에서도 죽지 않는다', () => {
  const blocked = {
    getItem: () => { throw new Error('접근 거부'); },
    setItem: () => { throw new Error('접근 거부'); },
    removeItem: () => { throw new Error('접근 거부'); },
  };
  const s = createStorage(blocked);
  assert.equal(s.loadProfile(), null);
  assert.doesNotThrow(() => s.saveProfile({ name: 'x' }));
  assert.doesNotThrow(() => s.clearProfile());
  assert.deepEqual(s.listPicks(), []);
});

test('전체 삭제', () => {
  const s = fresh();
  s.saveProfile({ name: 'a', birthDate: '1990-01-01' });
  s.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  s.clearAll();
  assert.equal(s.loadProfile(), null);
  assert.deepEqual(s.listPicks(), []);
});

// 저장소에는 예전 판이 쓴 값이나 손상된 값이 남아 있을 수 있다.
// 걸러 두지 않으면 화면을 그릴 때 p.lines.map(...) 이 터져 '내 번호' 가 죽는다.
test('lines 가 없거나 어긋난 내 번호 기록은 읽을 때 걸러낸다', () => {
  const map = new Map();
  const backend = {
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
  };
  backend.setItem('lottoracle.picks', JSON.stringify([
    { id: 'a', targetDraw: 1240, lines: [[1, 2, 3, 4, 5, 6]] },   // 정상
    { id: 'b', targetDraw: 1240, numbers: [1, 2, 3, 4, 5, 6] },   // lines 없음
    { id: 'c', targetDraw: 1240, lines: [] },                     // 빈 lines
    { id: 'd', targetDraw: 1240, lines: [[1, 2, 3]] },            // 6개가 아님
    { id: 'e', targetDraw: 1240, lines: [[1, 2, 3, 4, 5, 99]] },  // 범위 밖
    { id: 'f', lines: [[1, 2, 3, 4, 5, 6]] },                     // targetDraw 없음
    null, 'nope', 42,
  ]));
  assert.deepEqual(createStorage(backend).listPicks().map(p => p.id), ['a']);
});

test('정상 기록은 그대로 읽힌다', () => {
  const s = fresh();
  s.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  assert.equal(s.listPicks().length, 1);
  assert.deepEqual(s.listPicks()[0].lines, [[1, 2, 3, 4, 5, 6]]);
});

// ---- 백업

test('내보낸 꾸러미에 프로필·내 번호·설정이 담긴다', () => {
  const s = fresh();
  s.saveProfile({ name: '홍길동', birthDate: '1990-05-21' });
  s.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  s.saveSettings({ autoRefresh: true });
  const dump = s.exportAll();
  assert.equal(dump.app, 'lottoracle');
  assert.equal(dump.format, 1);
  assert.equal(dump.profile.name, '홍길동');
  assert.equal(dump.picks.length, 1);
  assert.equal(dump.settings.autoRefresh, true);
  assert.ok(!('draws' in dump), '회차 캐시는 빼고 내보낸다');
});

test('빈 기기에 그대로 복원된다', () => {
  const a = fresh();
  a.saveProfile({ name: '홍길동', birthDate: '1990-05-21' });
  a.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  const dump = JSON.parse(JSON.stringify(a.exportAll()));   // 파일을 거친 셈

  const b = fresh();
  const r = b.importAll(dump);
  assert.equal(r.added, 1);
  assert.equal(r.profileRestored, true);
  assert.equal(b.loadProfile().name, '홍길동');
  assert.deepEqual(b.listPicks()[0].lines, [[1, 2, 3, 4, 5, 6]]);
});

test('같은 백업을 두 번 넣어도 중복되지 않는다', () => {
  const s = fresh();
  s.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  const dump = s.exportAll();
  const r = s.importAll(dump);
  assert.equal(r.added, 0);
  assert.equal(r.duplicates, 1);
  assert.equal(s.listPicks().length, 1);
});

test('가져오기는 기존 기록을 지우지 않고 합친다', () => {
  const a = fresh();
  a.addPick([[1, 2, 3, 4, 5, 6]], 1240);
  const dump = a.exportAll();

  const b = fresh();
  b.addPick([[7, 8, 9, 10, 11, 12]], 1241);
  b.importAll(dump);
  assert.equal(b.listPicks().length, 2, '원래 있던 기록이 남아 있어야 한다');
});

test('기존 프로필은 허락 없이 덮어쓰지 않는다', () => {
  const s = fresh();
  s.saveProfile({ name: '원래사람', birthDate: '1980-01-01' });
  const dump = { app: 'lottoracle', format: 1, profile: { name: '백업사람' }, picks: [], settings: {} };

  assert.equal(s.importAll(dump).profileRestored, false);
  assert.equal(s.loadProfile().name, '원래사람');

  assert.equal(s.importAll(dump, { replaceProfile: true }).profileRestored, true);
  assert.equal(s.loadProfile().name, '백업사람');
});

test('손상된 기록은 걸러 내고 몇 개를 버렸는지 알려 준다', () => {
  const s = fresh();
  const r = s.importAll({
    app: 'lottoracle',
    format: 1,
    picks: [
      { id: 'ok', targetDraw: 1240, lines: [[1, 2, 3, 4, 5, 6]] },
      { id: 'bad1', targetDraw: 1240, lines: [[1, 2, 3]] },
      { id: 'bad2', lines: [[1, 2, 3, 4, 5, 6]] },
      null,
    ],
  });
  assert.equal(r.added, 1);
  assert.equal(r.skipped, 3);
  assert.equal(s.listPicks().length, 1);
});

test('남의 파일이나 엉뚱한 값은 거절한다', () => {
  const s = fresh();
  for (const bad of [null, 42, 'nope', {}, { app: 'other' }]) {
    assert.throws(() => s.importAll(bad));
  }
});
