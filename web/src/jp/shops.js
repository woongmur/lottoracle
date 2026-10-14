/** 일본 복권 판매점(宝くじ売り場) 찾기 — 구글 지도 Embed.
 *
 * 일본 판매점 위치를 공개 데이터로 주는 곳이 없어서(공식 사이트의 판매점 지도는 내부 조회용,
 * OpenStreetMap 에는 전국 574곳뿐) 구글 지도의 검색 결과를 그대로 띄운다.
 * Maps Embed API 는 횟수와 상관없이 무료다. 키는 카카오 키처럼 페이지에 드러나는 것이 정상이며,
 * 구글 콘솔에서 lottoracle.com 리퍼러와 Maps Embed API 로만 쓰이게 묶어 두었다.
 *
 * Embed 검색은 '보이는 지도 범위 안' 에서 찾는다. 그래서 지도 가운데를 내 위치(또는 고른 동네)로
 * 두고 걸어갈 만한 범위로 확대해 띄운다. 위치는 브라우저가 구글로 바로 보내고 여기서는 저장하지 않는다.
 */

export const MAPS_EMBED_KEY = 'AIzaSyDHd976eG3H7Yhli2zNy5EcIa0rs3oQyVQ';
export const QUERY = '宝くじ売り場';
export const ZOOM = 15;                         // 반경 1km 남짓 — 걸어서 갈 거리
export const OFFICIAL_MAP = 'https://www.takarakuji-official.jp/map/';

/** 한국 여행객이 많이 가는 동네. 좌표는 역·번화가 한가운데쯤. */
export const AREAS = [
  { city: '도쿄', items: [
    ['신주쿠', 35.6909, 139.7003], ['시부야', 35.6580, 139.7016], ['긴자', 35.6717, 139.7650],
    ['도쿄역', 35.6812, 139.7671], ['우에노', 35.7138, 139.7774], ['아사쿠사', 35.7148, 139.7967],
    ['이케부쿠로', 35.7295, 139.7109],
  ] },
  { city: '오사카', items: [
    ['난바', 34.6664, 135.5013], ['신사이바시', 34.6750, 135.5011], ['우메다', 34.7025, 135.4959],
  ] },
  { city: '교토', items: [['교토역', 34.9858, 135.7588], ['가와라마치', 35.0037, 135.7690]] },
  { city: '후쿠오카', items: [['하카타', 33.5897, 130.4207], ['텐진', 33.5917, 130.3989]] },
  { city: '그 밖', items: [
    ['나고야역', 35.1709, 136.8815], ['삿포로역', 43.0687, 141.3508], ['스스키노', 43.0555, 141.3530],
    ['나하 국제거리', 26.2160, 127.6890],
  ] },
];

/** 대략 일본 땅 안인가. 밖이면 주변에 일본 판매점이 있을 리 없다(그때는 동네 버튼을 권한다).
 *
 * 사각형 하나로 잡으면 부산·포항이 들어간다. 한반도 동해안이 동경 129.6 도 안쪽이라
 * 본토는 그 동쪽만, 남쪽 섬(오키나와·사키시마)과 쓰시마·고토는 따로 잡는다.
 * 정확한 국경이 아니라 '안내 문구를 띄울지' 만 가르는 용도다.
 */
export function inJapan(lat, lng) {
  if (lat >= 30 && lat <= 46 && lng >= 129.6 && lng <= 146.5) return true;     // 규슈~홋카이도
  if (lat >= 32.5 && lat <= 34.75 && lng >= 128.6 && lng < 129.6) return true;  // 고토·쓰시마
  return lat >= 24 && lat < 30 && lng >= 122.5 && lng <= 131.5;                // 오키나와·사키시마
}

const fix = n => Number(n).toFixed(5);

/** 페이지 안 지도(iframe) 주소. */
export function embedUrl(lat, lng, key = MAPS_EMBED_KEY) {
  const p = new URLSearchParams({
    key, q: QUERY, center: `${fix(lat)},${fix(lng)}`, zoom: String(ZOOM), language: 'ko', region: 'JP',
  });
  return `https://www.google.com/maps/embed/v1/search?${p}`;
}

/** 구글 지도 앱/웹에서 같은 검색을 여는 주소 (키가 없거나 큰 화면으로 보고 싶을 때). */
export const appUrl = (lat, lng) =>
  `https://www.google.com/maps/search/${encodeURIComponent(QUERY)}/@${fix(lat)},${fix(lng)},${ZOOM}z`;
