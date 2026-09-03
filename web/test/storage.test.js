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
