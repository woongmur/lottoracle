/** 일본 복권방 — 구글 지도 주소 만들기와 일본 안 판정. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { AREAS, QUERY, ZOOM, appUrl, embedUrl, inJapan } from '../src/jp/shops.js';

test('Embed 주소: 검색어·가운데·확대·한국어', () => {
  const u = new URL(embedUrl(35.6909, 139.7003, 'KEY'));
  assert.equal(u.origin + u.pathname, 'https://www.google.com/maps/embed/v1/search');
  assert.equal(u.searchParams.get('key'), 'KEY');
  assert.equal(u.searchParams.get('q'), QUERY);
  assert.equal(u.searchParams.get('center'), '35.69090,139.70030');
  assert.equal(u.searchParams.get('zoom'), String(ZOOM));
  assert.equal(u.searchParams.get('language'), 'ko');
  assert.equal(u.searchParams.get('region'), 'JP');
});

test('앱 주소는 같은 검색을 그 자리에서 연다', () => {
  assert.equal(appUrl(34.6664, 135.5013),
    `https://www.google.com/maps/search/${encodeURIComponent(QUERY)}/@34.66640,135.50130,${ZOOM}z`);
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
