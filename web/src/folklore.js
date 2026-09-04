/** 민간속설 모듈 — 통계가 아니라 '기분'을 다루는 부분.
 *
 * 여기 있는 규칙은 어느 것도 당첨 확률을 바꾸지 못한다. 확률은 그대로 1/8,145,060이다.
 * 다만 로또는 어차피 취향 싸움이라, 한국에서 오래 회자된 속설들을 가중치와 태그로
 * 정직하게 구현해 둔다. 켜고 끄는 건 사용자 몫.
 */
import { NUMBER_POOL, TWIN_NUMBERS, sortedNums } from './metrics.js';
import { SEOLLAL } from './seollal.js';

// ---------------------------------------------------------------- 실제 볼 색상
// 동행복권 추첨 볼의 색: 노랑 1~10, 파랑 11~20, 빨강 21~30, 회색 31~40, 초록 41~45
export const COLOR_ZONES = [
  ['노랑', 1, 10], ['파랑', 11, 20], ['빨강', 21, 30], ['회색', 31, 40], ['초록', 41, 45],
];

export function ballColor(n) {
  for (const [name, lo, hi] of COLOR_ZONES) if (n >= lo && n <= hi) return name;
  throw new Error(`1~45 범위를 벗어난 번호: ${n}`);
}

export function colorCounts(nums) {
  const counts = {};
  for (const [name] of COLOR_ZONES) counts[name] = 0;
  for (const n of nums) counts[ballColor(n)]++;
  return counts;
}

export function colorSignature(nums) {
  const counts = colorCounts(nums);
  return Object.entries(counts).filter(([, v]) => v).map(([k, v]) => `${k}${v}`).join(' ');
}

// ------------------------------------------------------- 로또 용지 배열(7열 격자)
export const SLIP_COLUMNS = 7;

/** 마킹 용지에서의 [행, 열]. 1~45를 7열 격자로 놓는다. */
export const slipPosition = n => [Math.floor((n - 1) / SLIP_COLUMNS), (n - 1) % SLIP_COLUMNS];

/** 용지에서 한 줄로 죽 그은 모양(같은 행/열/대각선)인지. 속설상 '피해야 할 모양'. */
export function isSlipLine(nums) {
  const pos = nums.map(slipPosition);
  const rows = new Set(pos.map(([r]) => r));
  const cols = new Set(pos.map(([, c]) => c));
  if (rows.size === 1 || cols.size === 1) return true;
  const diagDown = new Set(pos.map(([r, c]) => r - c));
  const diagUp = new Set(pos.map(([r, c]) => r + c));
  return diagDown.size === 1 || diagUp.size === 1;
}

/** 용지에서 붙어 있는(상하좌우 인접) 칸 쌍의 개수. 많으면 '뭉친 모양'. */
export function slipClusterPenalty(nums) {
  const pos = nums.map(slipPosition);
  let touching = 0;
  for (let i = 0; i < pos.length; i++) {
    for (let j = i + 1; j < pos.length; j++) {
      if (Math.abs(pos[i][0] - pos[j][0]) + Math.abs(pos[i][1] - pos[j][1]) === 1) touching++;
    }
  }
  return touching;
}

// ------------------------------------------------------------------ 숫자 성질들
function computePrimes() {
  return NUMBER_POOL.filter(n => {
    if (n < 2) return false;
    for (let d = 2; d * d <= n; d++) if (n % d === 0) return false;
    return true;
  });
}
export const PRIME_NUMBERS = computePrimes();
export const FIBONACCI_NUMBERS = [1, 2, 3, 5, 8, 13, 21, 34];
export const TRIANGULAR_NUMBERS = [1, 3, 6, 10, 15, 21, 28, 36, 45];
export const PERFECT_SQUARES = [1, 4, 9, 16, 25, 36];

/** 동형수(끝수가 같은 번호) 묶음. 예: 3·13·23. 끝수 → 번호들. */
export function sameEndingGroups(nums) {
  const groups = new Map();
  for (const n of sortedNums(nums)) {
    const d = n % 10;
    if (!groups.has(d)) groups.set(d, []);
    groups.get(d).push(n);
  }
  const out = new Map();
  for (const [d, g] of groups) if (g.length > 1) out.set(d, g);
  return out;
}

/** 이웃수: 직전 회차 당첨번호 ±1. '파동이 옆으로 번진다'는 속설. */
export function neighborNumbers(previous) {
  if (!previous) return new Set();
  const all = [...previous.numbers, previous.bonus];
  const out = new Set();
  for (const n of all) for (const x of [n - 1, n + 1]) if (x >= 1 && x <= 45) out.add(x);
  for (const n of previous.numbers) out.delete(n);
  return out;
}

// -------------------------------------------------------------------- 꿈해몽수
// 한국에서 흔히 회자되는 '꿈 → 번호' 대응. 근거는 없고, 재미로 쓰는 것이다.
export const DREAM_NUMBERS = {
  '돼지': [3, 7, 13, 27, 33, 37],
  '용': [1, 8, 9, 18, 28, 38],
  '조상': [4, 14, 24, 34, 44],
  '똥': [7, 17, 21, 27, 37, 43],
  '불': [5, 9, 19, 25, 29, 39],
  '물': [2, 6, 12, 22, 26, 42],
  '바다': [2, 12, 22, 32, 42, 45],
  '뱀': [6, 16, 23, 26, 36, 41],
  '호랑이': [3, 10, 13, 23, 30, 43],
  '아기': [1, 11, 15, 21, 31, 41],
  '돈': [7, 8, 17, 18, 27, 28],
  '무지개': [5, 7, 15, 25, 35, 45],
  '장례': [4, 9, 14, 19, 24, 40],
  '이빨': [2, 11, 20, 22, 29, 32],
  '산': [5, 10, 15, 20, 35, 40],
  '비': [6, 16, 26, 36, 44, 45],
};

/** 꿈 키워드에서 번호 뭉치를 찾는다. 부분 일치 허용('돼지꿈' -> '돼지'). */
export function dreamNumbers(keyword) {
  if (!keyword) return [];
  const text = String(keyword).trim();
  const hits = new Set();
  for (const [key, nums] of Object.entries(DREAM_NUMBERS)) {
    if (text.includes(key)) for (const n of nums) hits.add(n);
  }
  return [...hits].sort((a, b) => a - b);
}

// ------------------------------------------------------------- 생일수 / 띠수
export const ZODIAC_NUMBERS = {
  '쥐': [1, 13, 25, 37], '소': [2, 14, 26, 38], '호랑이': [3, 15, 27, 39],
  '토끼': [4, 16, 28, 40], '용': [5, 17, 29, 41], '뱀': [6, 18, 30, 42],
  '말': [7, 19, 31, 43], '양': [8, 20, 32, 44], '원숭이': [9, 21, 33, 45],
  '닭': [10, 22, 34], '개': [11, 23, 35], '돼지': [12, 24, 36],
};
export const ZODIAC_ORDER = ['원숭이', '닭', '개', '돼지', '쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양'];

export const zodiacOfYear = year => ZODIAC_ORDER[((year % 12) + 12) % 12];

/** 생년월일에서 띠. 띠는 음력 해를 따른다.
 *
 * 음력으로 적었으면 연도가 곧 음력 해라 그대로 쓰면 된다.
 * 양력이면 그해 설날보다 앞인지 봐야 한다 — 앞이면 아직 지난 해의 띠다.
 * 예: 1990-01-15(양력)은 1990년 설날(1/27)보다 앞이라 말띠가 아니라 뱀띠.
 *
 * 설날을 모르는 연도(표 밖)는 연도만으로 정한다. 없는 것보다는 낫다.
 */
export function zodiacOfBirth(birthDate, lunar = false) {
  const s = String(birthDate || '');
  if (s.length < 4) return '';
  let year = Number(s.slice(0, 4));
  if (!Number.isInteger(year)) return '';
  if (!lunar && s.length >= 10) {
    const seollal = SEOLLAL[year];
    if (seollal && s.slice(5, 10) < seollal) year -= 1;
  }
  return zodiacOfYear(year);
}

export function zodiacNumbers(nameOrYear) {
  if (!nameOrYear) return [];
  let token = String(nameOrYear).trim().replaceAll('띠', '');
  if (/^\d+$/.test(token)) token = zodiacOfYear(Number(token));
  return ZODIAC_NUMBERS[token] ? [...ZODIAC_NUMBERS[token]] : [];
}

/** 생일에서 뽑아내는 번호: 월, 일, 일의 자릿수 합, 연도 뒷 두 자리. */
export function birthdayNumbers(text) {
  if (!text) return [];
  const parts = String(text).match(/\d+/g);
  if (!parts) return [];
  const out = new Set();
  if (parts.length >= 3) {
    const y0 = Number(parts[0]), m = Number(parts[1]), d = Number(parts[2]);
    const y = y0 > 1000 ? y0 : 2000 + y0;
    const dt = new Date(y, m - 1, d);          // 유효성만 확인
    if (dt.getFullYear() === y && dt.getMonth() === m - 1 && dt.getDate() === d) {
      for (const x of [m, d, Math.floor(d / 10) + (d % 10), y % 100]) {
        if (x >= 1 && x <= 45) out.add(x);
      }
    }
  }
  for (const p of parts) {
    const x = Number(p);
    if (x >= 1 && x <= 45) out.add(x);
  }
  return [...out].sort((a, b) => a - b);
}

// ------------------------------------------------------------------- 설정/적용
/** 속설 옵션 묶음. 전부 꺼도 코드는 정상 동작한다. */
export function createFolklore(opts = {}) {
  return {
    enabled: true,
    lucky: [],                 // 행운수 — 가중치 상승
    avoid: [],                 // 기피수 — 아예 제외 (예: 4 = 죽을 사)
    dream: '',                 // 꿈 키워드
    birthday: '',              // 생일 (YYYY-MM-DD)
    zodiac: '',                // 띠 또는 태어난 해
    luckyWeight: 1.6,
    dreamWeight: 1.4,
    neighborWeight: 1.25,      // 이웃수(직전 ±1)
    twinWeight: 1.15,          // 쌍둥이수 11·22·33·44
    colorBalance: true,        // 5색이 한쪽으로 쏠리지 않게
    maxPerColor: 3,
    minColors: 3,
    avoidSlipLines: true,      // 용지 직선/대각선 모양 회피
    maxSlipCluster: 3,         // 용지에서 붙어 있는 칸 쌍의 상한
    ...opts,
  };
}

/** 행운수 + 꿈수 + 생일수 + 띠수를 합친 '내 편' 번호. */
export function wishNumbers(fl) {
  if (!fl) return [];
  const merged = new Set(fl.lucky);
  for (const n of dreamNumbers(fl.dream)) merged.add(n);
  for (const n of birthdayNumbers(fl.birthday)) merged.add(n);
  for (const n of zodiacNumbers(fl.zodiac)) merged.add(n);
  const avoid = new Set(fl.avoid);
  return [...merged].filter(n => !avoid.has(n)).sort((a, b) => a - b);
}

export const excluded = fl => new Set((fl?.avoid || []).filter(n => n >= 1 && n <= 45));

export function describe(fl) {
  const out = [];
  if (fl.lucky.length) out.push(`행운수 [${fl.lucky.join(', ')}]`);
  if (fl.avoid.length) out.push(`기피수 [${fl.avoid.join(', ')}] 제외`);
  if (fl.dream) {
    const got = dreamNumbers(fl.dream);
    out.push(`꿈(${fl.dream}) → ${got.length ? `[${got.join(', ')}]` : '해당 없음'}`);
  }
  if (fl.birthday) out.push(`생일수 [${birthdayNumbers(fl.birthday).join(', ')}]`);
  if (fl.zodiac) out.push(`띠수(${fl.zodiac}) [${zodiacNumbers(fl.zodiac).join(', ')}]`);
  if (fl.colorBalance) out.push(`5색 균형(한 색 최대 ${fl.maxPerColor}개)`);
  if (fl.avoidSlipLines) out.push('용지 직선·대각선 모양 회피');
  return out;
}

/** 번호별 속설 가중 배수. 속설을 끄면 전부 1.0. */
export function multipliers(fl, previous = null) {
  const base = new Map(NUMBER_POOL.map(n => [n, 1.0]));
  if (!fl || !fl.enabled) return base;

  const lucky = new Set(fl.lucky);
  for (const n of wishNumbers(fl)) {
    base.set(n, base.get(n) * (lucky.has(n) ? fl.luckyWeight : fl.dreamWeight));
  }
  for (const n of neighborNumbers(previous)) base.set(n, base.get(n) * fl.neighborWeight);
  for (const n of TWIN_NUMBERS) base.set(n, base.get(n) * fl.twinWeight);
  for (const n of excluded(fl)) base.set(n, 0.0);
  return base;
}

/** 속설 기준의 모양 검사. lenient=true 면 완화 단계에서 통과시킨다. */
export function accepts(fl, nums, lenient = false) {
  if (!fl || !fl.enabled || lenient) return true;
  if (fl.avoidSlipLines && isSlipLine(nums)) return false;
  if (slipClusterPenalty(nums) > fl.maxSlipCluster) return false;
  if (fl.colorBalance) {
    const counts = Object.values(colorCounts(nums));
    if (Math.max(...counts) > fl.maxPerColor) return false;
    if (counts.filter(v => v).length < fl.minColors) return false;
  }
  return true;
}

/** 조합에 걸린 속설을 사람이 읽을 문장으로. */
export function luckTags(fl, nums, previous = null) {
  const tags = [];
  const wish = new Set(fl && fl.enabled ? wishNumbers(fl) : []);
  const numSet = new Set(nums);

  const hitWish = [...numSet].filter(n => wish.has(n)).sort((a, b) => a - b);
  if (hitWish.length) tags.push(`행운·꿈수 적중 [${hitWish.join(', ')}]`);

  const hitTwin = TWIN_NUMBERS.filter(n => numSet.has(n));
  if (hitTwin.length) tags.push(`쌍둥이수 [${hitTwin.join(', ')}]`);

  const neighbors = neighborNumbers(previous);
  const hitNeighbor = [...numSet].filter(n => neighbors.has(n)).sort((a, b) => a - b);
  if (hitNeighbor.length) tags.push(`이웃수(직전 ±1) [${hitNeighbor.join(', ')}]`);

  const groups = sameEndingGroups(nums);
  if (groups.size) {
    tags.push('동형수 ' + [...groups.values()].map(g => g.join('·')).join(', '));
  }

  const hitPrime = PRIME_NUMBERS.filter(n => numSet.has(n));
  if (hitPrime.length >= 3) tags.push(`소수 ${hitPrime.length}개`);
  const hitFib = FIBONACCI_NUMBERS.filter(n => numSet.has(n)).sort((a, b) => a - b);
  if (hitFib.length >= 2) tags.push(`피보나치수 [${hitFib.join(', ')}]`);

  tags.push(`볼 색상 ${colorSignature(nums)}`);
  return tags;
}

/** 0~100의 '기분 점수'. 확률과는 아무 상관이 없다 — 정말로. */
export function luckScore(fl, nums, previous = null) {
  let score = 50;
  const numSet = new Set(nums);
  const wish = new Set(fl && fl.enabled ? wishNumbers(fl) : []);
  score += 8 * [...numSet].filter(n => wish.has(n)).length;
  score += 5 * TWIN_NUMBERS.filter(n => numSet.has(n)).length;
  const neighbors = neighborNumbers(previous);
  score += 4 * [...numSet].filter(n => neighbors.has(n)).length;
  const counts = Object.values(colorCounts(nums));
  score += 6 * counts.filter(v => v).length;          // 색이 고루 퍼질수록 가점
  score -= 7 * Math.max(0, Math.max(...counts) - 3);
  score -= 5 * Math.max(0, slipClusterPenalty(nums) - 2);
  if (isSlipLine(nums)) score -= 20;
  return Math.max(0, Math.min(100, score));
}
