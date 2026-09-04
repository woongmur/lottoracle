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

// 지역 검색은 좌표로 골라야 한다.
//
// 동행복권 주소에는 읍·면·동이 빠져 있다 (실제 자료: 오송팡팡복권방 =
// '충북 청주시 흥덕구 봉산2길 20-9'). 그래서 이름·주소 문자열로 고르면
// '오송'은 가게 이름에 우연히 걸리고 '오송읍'은 하나도 안 걸린다.
// 게다가 17km 떨어진 '지에스25오송타운점'이 이름만 보고 딸려 들어온다.
const 오송 = createStoreIndex({
  draws: [1234],
  stores: {
    팡팡: { name: '오송팡팡복권방', addr: '충북 청주시 흥덕구 봉산2길 20-9',
           lat: 36.61961, lot: 127.31829, r1: [1234], r2: [1203, 1221] },
    타운: { name: '지에스25오송타운점', addr: '충북 청주시 흥덕구 만수길 28-1 편의점',
           lat: 36.614824, lot: 127.51604, r1: [], r2: [1137, 1169] },
  },
});

test('문자열 검색은 표기 차이로 결과가 갈린다 (좌표를 쓰는 이유)', () => {
  assert.equal(오송.search('오송').length, 2);      // 이름에 걸린 것뿐
  assert.equal(오송.search('오송읍').length, 0);    // 주소에 '오송읍'이 없다
});

test('좌표로 고르면 표기가 달라도 같은 곳이 나온다', () => {
  // '오송'이든 '오송읍'이든 지오코딩되는 지점은 사실상 같다.
  const 오송역 = [36.6197, 127.3180];
  const a = 오송.near(오송역[0], 오송역[1], 3000);
  assert.deepEqual(a.map(s => s.name), ['오송팡팡복권방']);

  // 17km 떨어진 동명이점은 반경 밖이라 딸려 들어오지 않는다
  assert.ok(오송.near(오송역[0], 오송역[1], 3000).every(s => s.name !== '지에스25오송타운점'));
  assert.ok(오송.stores.find(s => s.name === '지에스25오송타운점').lat > 0);
});
