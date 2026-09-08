/** 태어난 시각을 서울 평균태양시로 옮기고, 태양황경으로 절기와 별자리를 구한다.
 *
 * 파이썬 lottoracle/solartime.py 와 같은 값을 내야 한다 (골든 데이터로 대조).
 *
 * 명리학에서 시주는 '시계가 가리킨 값' 이 아니라 그 자리의 태양 위치로 정한다.
 * 그래서 두 가지를 보정한다.
 *
 *   1) 표준시 이력 — 한국은 표준 자오선이 여러 번 바뀌었고(1954~61 은 동경 127.5도)
 *      서머타임도 12차례 있었다. tzhistory.js 의 표로 그 시점 오프셋을 찾아 UTC 로 되돌린다.
 *   2) 경도 — 서울은 동경 약 127도라 동경 135도 표준시보다 태양이 32분 늦다.
 *
 * 둘은 한 번에 처리된다. 벽시계 시각을 UTC 로 되돌리면 그 시대에 무슨 자오선을
 * 썼든 상관없어지고, 거기에 서울 경도만큼 더하면 서울 평균태양시다.
 *
 * 균시차(±16분)는 넣지 않는다 — 한국 만세력의 일반적인 관행을 따랐다.
 */
import { KST_TRANSITIONS } from './tzhistory.js';

export const SEOUL_LONGITUDE = 126.9784;                       // 서울시청
export const SEOUL_LMT_SECONDS = SEOUL_LONGITUDE / 15 * 3600;  // 약 8시간 27분 55초

const TZ_AT = KST_TRANSITIONS.map(r => r[0]);
const TZ_OFF = KST_TRANSITIONS.map(r => r[1]);

export const SOLAR_TERMS = [
  '춘분', '청명', '곡우', '입하', '소만', '망종',
  '하지', '소서', '대서', '입추', '처서', '백로',
  '추분', '한로', '상강', '입동', '소설', '대설',
  '동지', '소한', '대한', '입춘', '우수', '경칩',
];
// 12궁은 황경 0도(춘분)부터 30도씩. 절기 중 중기와 경계가 같다.
export const ZODIAC_SIGNS = [
  '양자리', '황소자리', '쌍둥이자리', '게자리', '사자자리', '처녀자리',
  '천칭자리', '전갈자리', '궁수자리', '염소자리', '물병자리', '물고기자리',
];

/** 정렬된 배열에서 v 보다 큰 첫 위치 (파이썬 bisect_right). */
function bisectRight(arr, v) {
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (v < arr[mid]) hi = mid; else lo = mid + 1;
  }
  return lo;
}

/** 그 순간 한국이 쓰던 UTC 오프셋(초). */
export function utcOffsetAt(epoch) {
  return TZ_OFF[Math.max(0, bisectRight(TZ_AT, epoch) - 1)];
}

function candidateOffsets(naive) {
  const seen = [];
  for (const off of TZ_OFF) {
    const o = TZ_OFF[Math.max(0, bisectRight(TZ_AT, naive - off) - 1)];
    if (!seen.includes(o)) seen.push(o);
  }
  return seen;
}

/** 1970-01-01 부터의 일수 (Howard Hinnant). */
export function daysFromCivil(y, m, d) {
  y -= m <= 2 ? 1 : 0;
  const era = Math.floor((y >= 0 ? y : y - 399) / 400);
  const yoe = y - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

export function civilFromDays(z) {
  z += 719468;
  const era = Math.floor((z >= 0 ? z : z - 146096) / 146097);
  const doe = z - era * 146097;
  const yoe = Math.floor((doe - Math.floor(doe / 1460) + Math.floor(doe / 36524)
    - Math.floor(doe / 146096)) / 365);
  const y = yoe + era * 400;
  const doy = doe - (365 * yoe + Math.floor(yoe / 4) - Math.floor(yoe / 100));
  const mp = Math.floor((5 * doy + 2) / 153);
  const d = doy - Math.floor((153 * mp + 2) / 5) + 1;
  const m = mp + (mp < 10 ? 3 : -9);
  return [y + (m <= 2 ? 1 : 0), m, d];
}

export function epochToParts(epoch) {
  const days = Math.floor(epoch / 86400);
  const rest = epoch - days * 86400;
  const [y, m, d] = civilFromDays(days);
  const hh = Math.floor(rest / 3600);
  const mi = Math.floor((rest - hh * 3600) / 60);
  const ss = Math.floor(rest - hh * 3600 - mi * 60);
  return [y, m, d, hh, mi, ss];
}

/**
 * 벽시계 시각 -> UTC epoch 초.
 *
 * 오프셋이 시각에 달려 있어 한 번에 못 구한다. 후보를 넣어 보고 앞뒤가 맞는 것을
 * 고른다. 서머타임이 끝나 같은 시각이 두 번 오는 구간은 앞쪽을, 건너뛴 구간은
 * 전환 직전 오프셋을 쓴다.
 */
export function wallToUtc(y, mo, d, hh = 0, mi = 0) {
  const naive = daysFromCivil(y, mo, d) * 86400 + hh * 3600 + mi * 60;
  let best = null;
  for (const cand of candidateOffsets(naive)) {
    const utc = naive - cand;
    if (utcOffsetAt(utc) === cand && (best === null || utc < best)) best = utc;
  }
  if (best !== null) return best;
  return naive - utcOffsetAt(naive - TZ_OFF[0]);
}

/** 벽시계 시각 -> 서울 평균태양시(그대로 시/분으로 풀면 보정된 시각). */
export function seoulSolarEpoch(y, mo, d, hh = 0, mi = 0) {
  return wallToUtc(y, mo, d, hh, mi) + SEOUL_LMT_SECONDS;
}

/** 벽시계 대비 몇 분을 옮겼는지. 화면 설명용. */
export function correctionMinutes(y, mo, d, hh = 0, mi = 0) {
  const naive = daysFromCivil(y, mo, d) * 86400 + hh * 3600 + mi * 60;
  return (seoulSolarEpoch(y, mo, d, hh, mi) - naive) / 60;
}

export function julianDay(epoch) {
  return epoch / 86400 + 2440587.5;
}

/** 겉보기 태양황경(도, 0~360). Meeus 천문알고리즘 25장 + 주요 섭동항. */
export function solarLongitude(jd) {
  const t = (jd - 2451545.0) / 36525.0;
  const rad = Math.PI / 180;

  const l0 = 280.46646 + 36000.76983 * t + 0.0003032 * t * t;
  const m = 357.52911 + 35999.05029 * t - 0.0001537 * t * t;
  const mr = m * rad;
  const c = (1.914602 - 0.004817 * t - 0.000014 * t * t) * Math.sin(mr)
    + (0.019993 - 0.000101 * t) * Math.sin(2 * mr)
    + 0.000289 * Math.sin(3 * mr);
  let trueLong = l0 + c;

  const a1 = (351.52 + 22518.7541 * t) * rad;
  const a2 = (253.14 + 45037.5082 * t) * rad;
  const a3 = (157.23 + 32964.4678 * t) * rad;
  const a4 = (297.85 + 445267.1115 * t) * rad;
  const a5 = (252.08 + 20.190 * t) * rad;
  const a6 = (31.80 + 45036.8840 * t) * rad;
  trueLong += 0.00134 * Math.cos(a1) + 0.00154 * Math.cos(a2)
    + 0.00200 * Math.cos(a3) + 0.00179 * Math.sin(a4)
    + 0.00178 * Math.sin(a5) + 0.00090 * Math.cos(a6);

  const omega = (125.04 - 1934.136 * t) * rad;
  const apparent = trueLong - 0.00569 - 0.00478 * Math.sin(omega);
  return ((apparent % 360) + 360) % 360;
}

export function solarLongitudeAt(epoch) {
  return solarLongitude(julianDay(epoch));
}

/**
 * 태양황경이 target 도가 되는 순간(UTC epoch 초).
 *
 * 절기 간격은 14.7~15.7일로 변해서(궤도가 타원) 고정 폭 구간 + 이분법은 근을
 * 놓친다. 남은 각도만큼 시간을 밀어 근처까지 간 뒤 이분법으로 다듬는다.
 */
export function findLongitude(target, guess) {
  const diff = e => (((solarLongitudeAt(e) - target + 180) % 360) + 360) % 360 - 180;

  let e = guess;
  for (let i = 0; i < 20; i += 1) {
    const d = diff(e);
    if (Math.abs(d) < 1e-6) return e;
    e -= d / 0.98564736 * 86400;
  }
  let lo = e - 3600, hi = e + 3600;
  let flo = diff(lo), fhi = diff(hi), grow = 0;
  while (flo * fhi > 0 && grow < 12) {
    lo -= 3600; hi += 3600;
    flo = diff(lo); fhi = diff(hi); grow += 1;
  }
  if (flo * fhi > 0) return e;
  for (let i = 0; i < 60; i += 1) {
    const mid = (lo + hi) / 2;
    const fm = diff(mid);
    if (flo * fm <= 0) { hi = mid; fhi = fm; } else { lo = mid; flo = fm; }
    if (hi - lo < 0.5) break;
  }
  return (lo + hi) / 2;
}

/** 그해 절기 24개의 [이름, UTC epoch 초]. 춘분(황경 0도)부터 15도 간격. */
export function solarTermTimes(year) {
  return SOLAR_TERMS.map((name, i) => {
    const guess = daysFromCivil(year, 3, 20) * 86400 + i * 15.218 * 86400;
    return [name, findLongitude((i * 15) % 360, guess)];
  });
}

/** 황경 -> 절기 구간 번호(0 = 춘분 구간). */
export function termIndex(longitude) {
  return ((Math.floor(longitude / 15) % 24) + 24) % 24;
}

/** 황경 -> 12궁. 춘분 0도가 양자리 시작. */
export function signOf(longitude) {
  return ZODIAC_SIGNS[((Math.floor(longitude / 30) % 12) + 12) % 12];
}
