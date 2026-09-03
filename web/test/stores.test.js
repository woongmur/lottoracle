/** stores.js — 당첨 배출점 데이터 다루기. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createStoreIndex, distanceMeters, summarize, recentDraws } from '../src/stores.js';

const RAW = {
  draws: [1237, 1238, 1239],
  stores: {
    a: { name: '명당복권', addr: '서울 마포구 와우산로 149', region: '서울',
         lat: 37.5546, lot: 126.9297, kind: '자동', r1: [1237, 1239], r2: [1238] },
    b: { name: '동네복권', addr: '서울 강동구 천호대로 10', region: '서울',
         lat: 37.5385, lot: 127.1234, kind: '수동', r1: [1239], r2: [] },
    c: { name: '부산복권', addr: '부산 해운대구 1', region: '부산',
         lat: 35.1587, lot: 129.1604, kind: '자동', r1: [], r2: [1237, 1238] },
    noCoord: { name: '좌표없음', addr: '어딘가', region: '서울',
               lat: null, lot: null, kind: '', r1: [1238], r2: [] },
    online: { name: '인터넷 복권판매사이트', addr: '동행복권(dhlottery.co.kr)', region: '',
              lat: 37.5, lot: 127.0, kind: '', r1: [1237, 1238, 1239], r2: [] },
  },
};
const idx = createStoreIndex(RAW);

test('좌표 없는 기록과 온라인 구매는 버린다', () => {
  assert.equal(idx.stores.length, 3);
  assert.ok(!idx.stores.some(s => s.name === '좌표없음'));
  // 인터넷 구매는 실제 가게가 아니라 지도에 찍을 수 없다
  assert.ok(!idx.stores.some(s => s.name.includes('인터넷')));
  assert.ok(!idx.hallOfFame(2).some(s => s.name.includes('인터넷')));
});

test('수집 범위를 알려 준다', () => {
  assert.equal(idx.coveredFrom, 1237);
  assert.equal(idx.coveredTo, 1239);
});

test('1등 배출 횟수를 센다', () => {
  const a = idx.byId('a');
  assert.equal(a.firstCount, 2);
  assert.equal(a.secondCount, 1);
  assert.deepEqual(a.first, [1237, 1239]);
});

test('명당은 1등 2회 이상, 많은 순', () => {
  const fame = idx.hallOfFame(2);
  assert.equal(fame.length, 1);
  assert.equal(fame[0].name, '명당복권');
  assert.equal(idx.hallOfFame(1).length, 2, '기준을 낮추면 늘어난다');
});

test('거리 계산이 상식적이다', () => {
  // 서울시청 ~ 강남역 약 8~9km
  const d = distanceMeters(37.5665, 126.9780, 37.4979, 127.0276);
  assert.ok(d > 7000 && d < 10000, `${d}m`);
  assert.equal(distanceMeters(37.5, 127, 37.5, 127), 0);
});

test('주변 검색은 반경 안에서 1등 많은 순', () => {
  const near = idx.near(37.5546, 126.9297, 30000);
  assert.equal(near.length, 2, '부산은 반경 밖');
  assert.equal(near[0].name, '명당복권');
  assert.equal(near[0].distance, 0);
  assert.ok(near[1].distance > 0);
  assert.equal(idx.near(37.5546, 126.9297, 100).length, 1, '반경을 좁히면 준다');
});

test('이름·주소로 찾는다', () => {
  assert.equal(idx.search('명당')[0].name, '명당복권');
  assert.equal(idx.search('해운대')[0].name, '부산복권');
  assert.deepEqual(idx.search(''), []);
  assert.deepEqual(idx.search('없는가게'), []);
});

test('요약 문구', () => {
  assert.equal(summarize(idx.byId('a')), '1등 2회 · 2등 1회');
  assert.equal(summarize(idx.byId('c')), '2등 2회');
  assert.equal(summarize({ firstCount: 0, secondCount: 0 }), '기록 없음');
});

test('배출 회차는 최근 것부터', () => {
  assert.deepEqual(recentDraws([1237, 1239, 1238]), [1239, 1238, 1237]);
  assert.deepEqual(recentDraws([1, 2, 3, 4], 2), [4, 3]);
});

test('빈 데이터에서도 죽지 않는다', () => {
  const empty = createStoreIndex(null);
  assert.deepEqual(empty.stores, []);
  assert.equal(empty.coveredFrom, null);
  assert.deepEqual(empty.hallOfFame(), []);
  assert.deepEqual(empty.near(37, 127), []);
});
