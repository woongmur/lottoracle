/** 일본 복권방 — 구글 지도 주소 만들기와 일본 안 판정. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { AREAS, JAPAN, QUERY, ZOOM, appUrl, embedUrl, inJapan, muniName, placeOf } from '../src/jp/shops.js';

const MUNI = JSON.parse(readFileSync(new URL('../data/jp/muni.json', import.meta.url)));

test('Embed 주소: 지명을 붙인 검색어·가운데·확대·한국어', () => {
  const u = new URL(embedUrl(35.6909, 139.7003, '新宿駅', ZOOM, 'KEY'));
  assert.equal(u.origin + u.pathname, 'https://www.google.com/maps/embed/v1/search');
  assert.equal(u.searchParams.get('key'), 'KEY');
  assert.equal(u.searchParams.get('q'), `${QUERY} 新宿駅`);
  assert.equal(u.searchParams.get('center'), '35.69090,139.70030');
  assert.equal(u.searchParams.get('zoom'), String(ZOOM));
  assert.equal(u.searchParams.get('language'), 'ko');
  assert.equal(u.searchParams.get('region'), 'JP');
  const japan = new URL(embedUrl(JAPAN.lat, JAPAN.lng, '', JAPAN.zoom, 'KEY'));
  assert.equal(japan.searchParams.get('q'), QUERY, '일본 전체는 지명 없이');
  assert.equal(japan.searchParams.get('zoom'), '5');
});

test('앱 주소는 같은 검색을 그 자리에서 연다', () => {
  assert.equal(appUrl(34.6664, 135.5013, '難波'),
    `https://www.google.com/maps/search/${encodeURIComponent(QUERY + ' 難波')}/@34.66640,135.50130,${ZOOM}z`);
});

test('동네 좌표는 모두 일본 안, 서울·부산은 밖', () => {
  for (const a of AREAS) for (const [name, lat, lng] of a.items) assert.ok(inJapan(lat, lng), name);
  assert.equal(inJapan(37.5665, 126.9780), false);   // 서울
  assert.equal(inJapan(35.1796, 129.0756), false);   // 부산
  assert.equal(inJapan(36.0190, 129.3435), false);   // 포항
  assert.equal(inJapan(33.4996, 126.5312), false);   // 제주
  assert.equal(inJapan(26.2124, 127.6809), true);    // 나하
  assert.equal(inJapan(34.2030, 129.2870), true);    // 쓰시마
  assert.equal(inJapan(32.7503, 129.8777), true);    // 나가사키
  assert.equal(inJapan(43.0642, 141.3469), true);    // 삿포로
});

test('동네 버튼은 모두 일본어 지명을 붙인다', () => {
  for (const a of AREAS) for (const [name, , , ja] of a.items) assert.ok(ja && /[\u3040-\u30ff\u4e00-\u9fff]/.test(ja), name);
});

test('시·구 코드표: 국토지리원 코드 → 도도부현+시구정촌', () => {
  assert.ok(Object.keys(MUNI).length > 1800);
  assert.equal(muniName('13104', MUNI), '東京都新宿区');
  assert.equal(muniName('27111', MUNI), '大阪府大阪市浪速区');
  assert.equal(muniName('01101', MUNI), '北海道札幌市中央区', '앞자리 0 이 있어도');
  assert.equal(muniName('47201', MUNI), '沖縄県那覇市');
  assert.notEqual(muniName('13206', MUNI), muniName('34208', MUNI), '같은 이름(府中市)도 도도부현으로 갈린다');
  assert.equal(muniName('99999', MUNI), '');
  assert.equal(muniName(undefined, MUNI), '');
});

test('좌표 → 지명: 국토지리원 응답을 표로 바꾸고, 실패하면 빈 문자열', async () => {
  const ok = async url => ({ json: async () => (url.includes('gsi') ? { results: { muniCd: '27111', lv01Nm: '難波三丁目' } } : MUNI) });
  assert.equal(await placeOf(34.6664, 135.5013, { fetchImpl: ok }), '大阪府大阪市浪速区');
  const bad = async () => { throw new Error('offline'); };
  assert.equal(await placeOf(34.6664, 135.5013, { fetchImpl: bad }), '');
  const empty = async url => ({ json: async () => (url.includes('gsi') ? {} : MUNI) });
  assert.equal(await placeOf(0, 0, { fetchImpl: empty }), '', '바다 한가운데 등 결과 없음');
});
