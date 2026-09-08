/** 사주팔자 — 태어난 순간을 네 기둥 여덟 글자로.
 *
 * 파이썬 lottoracle/saju.py 와 같은 값을 내야 한다 (골든 데이터로 대조).
 *
 * 여기 있는 건 전부 답이 있는 계산이다. 만세력과 대조하면 맞다/틀리다를 말할 수
 * 있다. 이 글자들을 '나' 중심으로 읽는 층(십신·신살·강약)은 sipsin.js 에 있다 —
 * 그쪽도 표에서 나오는 값이지만 유파가 갈리는 지점이 있어 따로 뒀다.
 *
 * 기준
 *   년주  입춘부터 새 해. 설날이 아니다 — 앱이 보여 주는 띠(설날 기준)와 어긋나는
 *         구간이 생긴다. 예: 1990-02-01 은 말띠지만 사주 년주는 기사(뱀).
 *   월주  절(節) 기준. 달력 월이 아니라 입춘·경칩·청명... 12개 절기로 나눈다.
 *         절이 든 날이라도 절입 '시각' 을 지나야 다음 달이다.
 *   일주  60갑자가 하루씩 끊기지 않고 도는 것. 2000-01-01 이 무오일(54번).
 *   시주  서울 평균태양시로 시지를 정하고 천간은 일간에서 유도한다(오자둔).
 *
 * 천문(황경·절기·입춘)은 진짜 UTC 로, 달력(날짜·시각)은 태양시 시계로 본다.
 * 하나로 뭉뚱그리면 절 경계가 8시간 넘게 어긋난다.
 */
import {
  epochToParts, seoulSolarEpoch, signOf, solarLongitudeAt, daysFromCivil, wallToUtc,
  findLongitude,
} from './solartime.js';
import { reading } from './sipsin.js';

export const STEMS = '갑을병정무기경신임계';
export const BRANCHES = '자축인묘진사오미신유술해';
export const STEM_HANJA = '甲乙丙丁戊己庚辛壬癸';
export const BRANCH_HANJA = '子丑寅卯辰巳午未申酉戌亥';
export const BRANCH_ANIMALS = ['쥐', '소', '호랑이', '토끼', '용', '뱀',
  '말', '양', '원숭이', '닭', '개', '돼지'];

export const ELEMENTS = ['목', '화', '토', '금', '수'];
export const STEM_ELEMENT = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4];   // 갑을=목 병정=화 ...
const BRANCH_ELEMENT = [4, 2, 0, 0, 2, 1, 1, 2, 3, 3, 2, 4];  // 자=수 축=토 인=목 ...
export const STEM_YIN = [false, true, false, true, false, true, false, true, false, true];

// 2000-01-01 이 60갑자 54번(무오)이다.
const DAY_ANCHOR_DAYS = daysFromCivil(2000, 1, 1);
const DAY_ANCHOR_INDEX = 54;

function pillar(stem, branch) {
  return {
    stem,
    branch,
    name: STEMS[stem] + BRANCHES[branch],
    hanja: STEM_HANJA[stem] + BRANCH_HANJA[branch],
    stemName: STEMS[stem],
    branchName: BRANCHES[branch],
    animal: BRANCH_ANIMALS[branch],
    stemElement: ELEMENTS[STEM_ELEMENT[stem]],
    branchElement: ELEMENTS[BRANCH_ELEMENT[branch]],
    yin: STEM_YIN[stem],
  };
}

function fromIndex(i) {
  const n = ((i % 60) + 60) % 60;
  return pillar(n % 10, n % 12);
}

const LICHUN_CACHE = new Map();

/** 그 해 입춘(황경 315도)의 순간. 2월 4일 언저리다. */
export function lichunEpoch(year) {
  if (!LICHUN_CACHE.has(year)) {
    LICHUN_CACHE.set(year, findLongitude(315, daysFromCivil(year, 2, 4) * 86400));
  }
  return LICHUN_CACHE.get(year);
}

/** 입춘을 새 해의 시작으로 본다 — 설날이 아니다. */
export function yearPillar(utcEpoch, localYear) {
  const year = utcEpoch >= lichunEpoch(localYear) ? localYear : localYear - 1;
  return fromIndex(year - 4);
}

/** 절(節) 기준. 입춘(315도)부터 인월이고 30도마다 다음 지지. 천간은 오호둔. */
export function monthPillar(utcEpoch, yearStem) {
  const lon = solarLongitudeAt(utcEpoch);
  const step = Math.floor((((lon - 315) % 360) + 360) % 360 / 30);
  const branch = (2 + step) % 12;
  const first = (yearStem % 5) * 2 + 2;      // 그 해 인월의 천간
  return pillar((first + step) % 10, branch);
}

/** 60갑자가 하루씩 끊기지 않고 돈다. 서울 태양시의 날짜로 센다. */
export function dayPillar(solarEpoch) {
  const days = Math.floor(solarEpoch / 86400);
  return fromIndex(DAY_ANCHOR_INDEX + (days - DAY_ANCHOR_DAYS));
}

/** 23~01시가 자시, 01~03시가 축시 ... 두 시간씩. */
export function hourBranchOf(hour) {
  return Math.floor((hour + 1) / 2) % 12;
}

/** 천간은 일간에서 유도(오자둔). 23시대(야자시)는 다음 날 자시로 본다. */
export function hourPillar(solarEpoch, dayStem) {
  const hh = epochToParts(solarEpoch)[3];
  const branch = hourBranchOf(hh);
  const base = hh >= 23 ? (dayStem + 1) % 10 : dayStem;
  const first = (base % 5) * 2;
  return pillar((first + branch) % 10, branch);
}

/** 여덟 글자를 목화토금수로 세어 본다. 지장간은 아직 넣지 않는다. */
export function elementsCount(pillars) {
  const out = {};
  for (const e of ELEMENTS) out[e] = 0;
  for (const p of pillars) {
    out[p.stemElement] += 1;
    out[p.branchElement] += 1;
  }
  return out;
}

/**
 * 두 시각으로 팔자를 세운다.
 *   utcEpoch    진짜 UTC 순간. 황경을 구해 입춘·절 경계를 가른다.
 *   solarEpoch  서울 태양시 시계. 날짜(일주)와 시각(시지)을 읽는다.
 */
export function fourPillarsAt(utcEpoch, solarEpoch, correction = 0) {
  const [ly, mo, d, hh, mi] = epochToParts(solarEpoch);
  const year = yearPillar(utcEpoch, ly);
  const month = monthPillar(utcEpoch, year.stem);
  const day = dayPillar(solarEpoch);
  const hour = hourPillar(solarEpoch, day.stem);
  // 시지 경계는 홀수 시각(23,01,03,...)에 있다. 홀수 시면 방금 그 지지에
  // 들어온 것이라 다음 경계까지 120-mi, 짝수 시면 한 시간 전에 들어와 60-mi.
  const edge = hh % 2 === 0 ? 60 - mi : 120 - mi;
  const pillars = [year, month, day, hour];
  return {
    year, month, day, hour, pillars,
    eightChars: pillars.map(p => p.name).join(''),
    hanja: pillars.map(p => p.hanja).join(' '),
    dayStem: STEMS[day.stem],
    elements: elementsCount(pillars),
    sign: signOf(solarLongitudeAt(utcEpoch)),
    solarTime: `${String(ly).padStart(4, '0')}-${String(mo).padStart(2, '0')}-`
      + `${String(d).padStart(2, '0')} ${String(hh).padStart(2, '0')}:${String(mi).padStart(2, '0')}`,
    correctionMinutes: Math.round(correction * 10) / 10,
    lateNight: hh >= 23,
    hourEdgeMinutes: edge,
  };
}

/** 벽시계 시각(태어난 곳 시계가 가리킨 값)으로 팔자를 세운다. */
export function fourPillars(y, mo, d, hh = 0, mi = 0) {
  const naive = daysFromCivil(y, mo, d) * 86400 + hh * 3600 + mi * 60;
  const utc = wallToUtc(y, mo, d, hh, mi);
  const solar = seoulSolarEpoch(y, mo, d, hh, mi);
  return fourPillarsAt(utc, solar, (solar - naive) / 60);
}

// 프로필의 '태어난 시' 는 12지지 선택지라 정확한 분이 없다. 선택지 구간의
// 한가운데를 쓴다 — 그 구간 표(23:30~01:30 …)가 이미 서울 보정을 머금은
// 벽시계 범위라, 여기에 보정을 걸면 같은 지지로 되돌아온다.
export const BRANCH_MID_HOUR = {
  자: [0, 30], 축: [2, 30], 인: [4, 30], 묘: [6, 30],
  진: [8, 30], 사: [10, 30], 오: [12, 30], 미: [14, 30],
  신: [16, 30], 유: [18, 30], 술: [20, 30], 해: [22, 30],
};

/**
 * 프로필 -> 화면에 넘길 사주 묶음. 생년월일이 없으면 null.
 *
 * 태어난 시를 모르면 정오로 세우고 시주는 없는 것으로 표시한다 — 모르는 값을
 * 아는 척하지 않는다. 일주도 자정 근처를 피해야 해서 정오가 안전하다.
 */
export function fromProfile(profile, folkZodiac = '') {
  if (!profile || !profile.birthDate) return null;
  const [y, mo, d] = profile.birthDate.split('-').map(Number);

  let hh = 12, mi = 0, known = false;
  if (profile.birthHour !== null && profile.birthHour !== undefined) {
    hh = profile.birthHour; mi = 0; known = true;
  } else if (profile.birthBranch && BRANCH_MID_HOUR[profile.birthBranch]) {
    [hh, mi] = BRANCH_MID_HOUR[profile.birthBranch]; known = true;
  }

  const s = fourPillars(y, mo, d, hh, mi);
  const out = { ...s };
  out.hourKnown = known;
  out.exactTime = profile.birthHour !== null && profile.birthHour !== undefined;
  let pillars = s.pillars;
  if (!known) {
    out.hour = null;
    out.eightChars = out.eightChars.slice(0, 6);
    pillars = [s.year, s.month, s.day];
    out.elements = elementsCount(pillars);
  }
  // 십신·신살은 여덟 글자를 '나' 중심으로 읽는 층이라 여기서 얹는다.
  // 시주를 모르면 세 기둥으로만 센다 — 모르는 글자를 넣고 세면 답이 달라진다.
  out.reading = reading(pillars, s.day.stem, out.elements);
  out.folkZodiac = folkZodiac;
  out.zodiacDiffers = !!folkZodiac && folkZodiac !== s.year.animal;
  return out;
}
