/** 일본 복권 판매점(宝くじ売り場) 찾기 — 구글 지도 Embed.
 *
 * 일본 판매점 위치를 공개 데이터로 주는 곳이 없어서(공식 사이트의 판매점 지도는 내부 조회용,
 * OpenStreetMap 에는 전국 574곳뿐) 구글 지도의 검색 결과를 그대로 띄운다.
 * Maps Embed API 는 횟수와 상관없이 무료다. 키는 카카오 키처럼 페이지에 드러나는 것이 정상이며,
 * 구글 콘솔에서 lottoracle.com 리퍼러와 Maps Embed API 로만 쓰이게 묶어 두었다.
 *
 * 검색어에 '어디' 가 들어가야 핀이 찍힌다. lottoracle.com 에서 실제로 띄워 비교해 보니
 * '宝くじ売り場' 에 지도 가운데 좌표만 주면 신주쿠 한복판에서도 핀이 0개였고,
 * '宝くじ売り場 新宿駅' · '宝くじ売り場 大阪市浪速区' 처럼 지명을 붙이면 주변 판매점이 찍혔다.
 * 그래서
 *   - 동네 버튼은 일본어 지명을 붙여 찾고,
 *   - 내 위치는 국토지리원 역지오코더(키 없음·무료)로 좌표를 시·구 코드로 바꾼 뒤
 *     시·구 이름(data/jp/muni.json)을 붙여 찾는다. 지도 가운데는 내 위치 그대로.
 * 위치는 브라우저가 국토지리원·구글로 바로 보내고 여기서는 저장하지 않는다.
 */

export const MAPS_EMBED_KEY = 'AIzaSyDHd976eG3H7Yhli2zNy5EcIa0rs3oQyVQ';
export const QUERY = '宝くじ売り場';
export const ZOOM = 15;                         // 반경 1km 남짓 — 걸어서 갈 거리
export const OFFICIAL_MAP = 'https://www.takarakuji-official.jp/map/';

/** 탭을 열었을 때와 일본 밖에서 '내 위치' 를 눌렀을 때 보여 줄 일본 전체. */
export const JAPAN = { lat: 36.2, lng: 138.25, zoom: 5 };

/** 한국 여행객이 많이 가는 동네. [이름, 위도, 경도, 검색에 붙일 일본어 지명] */
export const AREAS = [
  { city: '도쿄', items: [
    ['신주쿠', 35.6909, 139.7003, '新宿駅'], ['시부야', 35.6580, 139.7016, '渋谷駅'],
    ['긴자', 35.6717, 139.7650, '銀座'], ['도쿄역', 35.6812, 139.7671, '東京駅'],
    ['우에노', 35.7138, 139.7774, '上野駅'], ['아사쿠사', 35.7148, 139.7967, '浅草'],
    ['이케부쿠로', 35.7295, 139.7109, '池袋駅'],
  ] },
  { city: '오사카', items: [
    ['난바', 34.6664, 135.5013, '難波'], ['신사이바시', 34.6750, 135.5011, '心斎橋'],
    ['우메다', 34.7025, 135.4959, '梅田'],
  ] },
  { city: '교토', items: [['교토역', 34.9858, 135.7588, '京都駅'], ['가와라마치', 35.0037, 135.7690, '河原町']] },
  { city: '후쿠오카', items: [['하카타', 33.5897, 130.4207, '博多駅'], ['텐진', 33.5917, 130.3989, '天神']] },
  { city: '그 밖', items: [
    ['나고야역', 35.1709, 136.8815, '名古屋駅'], ['삿포로역', 43.0687, 141.3508, '札幌駅'],
    ['스스키노', 43.0555, 141.3530, 'すすきの'], ['나하 국제거리', 26.2160, 127.6890, '那覇 国際通り'],
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
const query = place => (place ? `${QUERY} ${place}` : QUERY);

/** 페이지 안 지도(iframe) 주소. place 는 검색어에 붙일 일본어 지명(없으면 핀이 잘 안 찍힌다). */
export function embedUrl(lat, lng, place = '', zoom = ZOOM, key = MAPS_EMBED_KEY) {
  const p = new URLSearchParams({
    key, q: query(place), center: `${fix(lat)},${fix(lng)}`, zoom: String(zoom), language: 'ko', region: 'JP',
  });
  return `https://www.google.com/maps/embed/v1/search?${p}`;
}

/** 구글 지도 앱/웹에서 같은 검색을 여는 주소 (큰 화면으로 보거나 길찾기로 바로 갈 때). */
export const appUrl = (lat, lng, place = '', zoom = ZOOM) =>
  `https://www.google.com/maps/search/${encodeURIComponent(query(place))}/@${fix(lat)},${fix(lng)},${zoom}z`;

export const REVERSE_GEOCODER = 'https://mreversegeocoder.gsi.go.jp/reverse-geocoder/LonLatToAddress';

/** 국토지리원 응답의 시·구 코드를 '東京都新宿区' 같은 이름으로. 표는 data/jp/muni.json. */
export function muniName(code, table) {
  const key = String(Number(code));            // '01101' 과 '1101' 을 같게
  return Number.isFinite(Number(code)) && table[key] ? table[key] : '';
}

/** 좌표 → 시·구 이름. 못 구하면 빈 문자열(그때는 지명 없이 찾는다). */
export async function placeOf(lat, lng, { fetchImpl = fetch, muniUrl = './data/jp/muni.json', timeoutMs = 6000 } = {}) {
  const ctl = typeof AbortController === 'function' ? new AbortController() : null;
  const timer = ctl ? setTimeout(() => ctl.abort(), timeoutMs) : null;
  try {
    const [geo, table] = await Promise.all([
      fetchImpl(`${REVERSE_GEOCODER}?lat=${fix(lat)}&lon=${fix(lng)}`, ctl ? { signal: ctl.signal } : {}).then(r => r.json()),
      fetchImpl(muniUrl).then(r => r.json()),
    ]);
    return muniName(geo?.results?.muniCd, table);
  } catch {
    return '';
  } finally {
    if (timer) clearTimeout(timer);
  }
}
