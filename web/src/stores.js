/** 당첨 배출점('명당') 데이터.
 *
 * `data/stores.json` 은 tools/fetch_stores.py 가 동행복권 당첨판매점 검색 API 에서
 * 회차별로 모아 둔 것이다. 방문할 때마다 수백 번 호출할 수 없어 미리 모아 배포한다.
 *
 * 형식: { draws: [회차...], stores: { 판매점ID: {name, addr, region, lat, lot, kind, r1, r2} } }
 *   r1 · r2 = 1등 · 2등을 배출한 회차 번호 목록
 */

/** 두 좌표 사이 거리(m). 하버사인. */
export function distanceMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const rad = d => (d * Math.PI) / 180;
  const dLat = rad(lat2 - lat1), dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return Math.round(2 * R * Math.asin(Math.sqrt(a)));
}

/** 원본 JSON 을 다루기 쉬운 목록으로. 좌표가 없는 기록은 버린다. */
export function createStoreIndex(raw) {
  const draws = raw?.draws || [];
  const stores = Object.entries(raw?.stores || {})
    .map(([id, s]) => ({
      id,
      name: s.name || '이름 미상',
      addr: s.addr || '',
      region: s.region || '',
      lat: s.lat,
      lot: s.lot,
      kind: s.kind || '',
      first: s.r1 || [],
      second: s.r2 || [],
      firstCount: (s.r1 || []).length,
      secondCount: (s.r2 || []).length,
    }))
    // 좌표가 없거나 온라인 구매(동행복권 사이트)는 지도에 찍을 수 없다
    .filter(s => typeof s.lat === 'number' && typeof s.lot === 'number' && !s.name.includes('인터넷'));

  return {
    draws,
    stores,
    coveredFrom: draws.length ? Math.min(...draws) : null,
    coveredTo: draws.length ? Math.max(...draws) : null,
    /** 1등을 두 번 이상 배출한 곳 = 흔히 말하는 '명당'. */
    hallOfFame(minFirst = 2) {
      return stores.filter(s => s.firstCount >= minFirst)
        .sort((a, b) => (b.firstCount - a.firstCount) || (b.secondCount - a.secondCount));
    },
    /** 좌표 주변 반경 안의 배출점을 가까운 순으로. */
    near(lat, lot, radius = 3000, limit = 50) {
      return stores
        .map(s => ({ ...s, distance: distanceMeters(lat, lot, s.lat, s.lot) }))
        .filter(s => s.distance <= radius)
        .sort((a, b) => (b.firstCount - a.firstCount) || (a.distance - b.distance))
        .slice(0, limit);
    },
    /** 이름·주소로 찾기. */
    search(query, limit = 50) {
      const q = String(query || '').trim();
      if (!q) return [];
      return stores.filter(s => s.name.includes(q) || s.addr.includes(q))
        .sort((a, b) => (b.firstCount - a.firstCount) || (b.secondCount - a.secondCount))
        .slice(0, limit);
    },
    byId: id => stores.find(s => s.id === id) || null,
  };
}

/** '1등 3회 · 2등 5회' 같은 한 줄 요약. */
export function summarize(store) {
  const parts = [];
  if (store.firstCount) parts.push(`1등 ${store.firstCount}회`);
  if (store.secondCount) parts.push(`2등 ${store.secondCount}회`);
  return parts.join(' · ') || '기록 없음';
}

/** 배출 회차를 최근 것부터 나열. */
export const recentDraws = (list, limit = 12) =>
  [...list].sort((a, b) => b - a).slice(0, limit);
