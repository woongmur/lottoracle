/** 오늘의 운세 — 프로필(이름·생년월일·태어난 시)과 날짜로 결정되는 '기분' 모듈.
 *
 * 확률과는 아무 상관이 없다. 같은 사람은 하루 종일 같은 운세를 본다(날짜+프로필 시드).
 * 문장 규칙:
 *   - 결과를 약속하지 않는다 — '당첨', '대박' 같은 단어는 금칙어(FORBIDDEN_WORDS)로 막는다.
 *   - 좋은 날도 단정하지 않고, 나쁜 날도 겁주지 않는다. 나쁜 날은 내일로 이어 준다.
 *   - 구매를 부추기는 표현을 쓰지 않는다.
 */
import { ZODIAC_NUMBERS, ballColor, birthdayNumbers, zodiacNumbers, zodiacOfYear } from './folklore.js';
import { NUMBER_POOL } from './metrics.js';
import { createRng } from './rng.js';

export const TAGLINE = '숫자는 우연을, 기분은 당신이 정합니다';
export const DISCLAIMER =
  '이 서비스의 운세와 추천 번호는 통계적 근거가 없으며 당첨을 보장하지 않습니다. ' +
  '로또는 매 회차 독립적인 무작위 추첨이고, 1등 확률은 조합과 무관하게 1/8,145,060으로 고정입니다. ' +
  '지출은 잃어도 괜찮은 금액까지만. 도박문제 상담 국번없이 1336.';

// 운세 문장에 절대 쓰지 않는 말. 테스트가 모든 템플릿을 검사한다.
export const FORBIDDEN_WORDS = ['당첨', '대박', '1등', '재물', '횡재', '보장', '반드시', '꼭 ', '구매', '사세요', '사면'];

// 등급 1(낮음)~5(높음). 라벨은 어느 쪽으로도 기분을 크게 흔들지 않게.
export const GRADE_LABELS = {
  5: '기운이 맑은 날', 4: '흐름이 순한 날', 3: '고요히 흐르는 날',
  2: '상황을 살피는 날', 1: '서서히 오르는 조짐',
};
export const GRADE_WEIGHTS = { 5: 2, 4: 3, 3: 3, 2: 2, 1: 1 };   // 살짝 낙관적으로

// 등급별 문장. 흐름 / 태도 / 시선 전환 세 갈래를 섞어 패턴이 보이지 않게 한다.
export const SENTENCES = {
  5: [
    '막힘 없이 흐르는 하루입니다. 눈에 들어오는 숫자를 가볍게 적어 두세요.',
    '마음이 가는 대로 골라도 괜찮은 날입니다. 오래 고민하지 않아도 됩니다.',
    '숫자보다 사람에게서 좋은 소식이 올 수 있는 날입니다. 연락 한 통이 하루를 바꿉니다.',
    '아침에 떠오른 숫자가 저녁까지 따라다니는 날입니다. 그 느낌을 기억해 두세요.',
  ],
  4: [
    '잔잔하게 잘 풀리는 하루입니다. 평소 좋아하던 숫자를 곁에 두세요.',
    '서두르지 않아도 제자리를 찾는 날입니다. 늘 하던 대로가 답입니다.',
    '가까운 사람과의 대화에서 힌트를 얻는 날입니다.',
    '오늘의 숫자 중 하나가 유난히 눈에 밟힐 수 있습니다. 그냥 지나치지 마세요.',
  ],
  3: [
    '특별할 것 없이 고요한 하루입니다. 평소의 리듬을 지키면 충분합니다.',
    '결정은 가볍게, 기대는 느긋하게 가져가는 날입니다.',
    '숫자보다 오늘 할 일에 집중하면 저녁이 편안해집니다.',
    '잔잔한 물처럼 흐르는 날입니다. 큰 변화보다 작은 정리가 어울립니다.',
  ],
  2: [
    '오늘은 상황을 살피는 날입니다. 내일의 흐름이 더 또렷해집니다.',
    '천천히 가도 좋은 날입니다. 서두른 선택보다 하루 묵힌 선택이 낫습니다.',
    '숫자보다 사람이 잘 풀리는 날입니다. 오늘은 그쪽에 마음을 두세요.',
    '구름이 옅게 낀 하루입니다. 내일 다시 하늘을 올려다보세요.',
  ],
  1: [
    '서서히 운이 오르는 조짐이 보입니다. 오늘은 준비하고 내일을 기다리세요.',
    '쉬어가는 날입니다. 오늘 아낀 기운이 내일의 몫이 됩니다.',
    '숫자와 잠시 거리를 두는 날입니다. 오늘은 사람과 음식에서 기분을 챙기세요.',
    '바닥을 지나 올라오는 길목입니다. 내일 다시 들러 보세요.',
  ],
};

export const KEYWORDS = ['여유', '호기심', '정리', '기다림', '배려', '집중', '산책', '대화', '휴식', '기록', '온기', '느긋함'];
export const TIPS = [
  '따뜻한 차 한 잔으로 하루를 시작해 보세요.',
  '오래 미뤄 둔 답장을 오늘 보내 보세요.',
  '저녁엔 짧게라도 걸어 보세요.',
  '책상 위를 한 번 정리해 보세요.',
  '좋아하는 노래를 한 곡 끝까지 들어 보세요.',
  '오늘 고마웠던 사람에게 한마디 건네 보세요.',
  '잠들기 전 오늘 좋았던 일 하나를 떠올려 보세요.',
  '점심은 평소보다 천천히 드셔 보세요.',
];

// 태어난 시(時) → 12지지. 요즘 한국 사주에서 통용되는 30분 보정 기준
// (한국 표준시가 동경 135도 기준이라 실제 태양시보다 약 30분 빠른 것을 반영).
export const HOUR_BRANCHES = ['자', '축', '인', '묘', '진', '사', '오', '미', '신', '유', '술', '해'];
const BRANCH_ANIMALS = ['쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양', '원숭이', '닭', '개', '돼지'];
export const BRANCH_ANIMAL = Object.fromEntries(HOUR_BRANCHES.map((b, i) => [b, BRANCH_ANIMALS[i]]));
export const BRANCH_RANGE = {
  '자': '23:30~01:30', '축': '01:30~03:30', '인': '03:30~05:30', '묘': '05:30~07:30',
  '진': '07:30~09:30', '사': '09:30~11:30', '오': '11:30~13:30', '미': '13:30~15:30',
  '신': '15:30~17:30', '유': '17:30~19:30', '술': '19:30~21:30', '해': '21:30~23:30',
};

/** 시:분 → 12지지 한 글자 (30분 보정). null 이면 빈 문자열. */
export function branchOfTime(hour, minute = 0) {
  if (hour === null || hour === undefined || hour === '') return '';
  const total = (((Number(hour) * 60 + Number(minute) + 30) % 1440) + 1440) % 1440;
  return HOUR_BRANCHES[Math.floor(total / 120)];
}

/** 정시 기준 12지지. */
export const hourBranch = hour => branchOfTime(hour, 0);

/** '진', '진시', '용' 같은 입력을 지지 한 글자로. 모르면 빈 문자열, 틀리면 예외. */
export function normalizeBranch(text) {
  const token = String(text ?? '').trim().replaceAll('시', '');
  if (!token) return '';
  if (HOUR_BRANCHES.includes(token)) return token;
  for (const [b, animal] of Object.entries(BRANCH_ANIMAL)) if (token === animal) return b;
  throw new Error(`태어난 시는 자·축·인·묘·진·사·오·미·신·유·술·해 중 하나여야 합니다: ${text}`);
}

/** GUI 선택지: [{value:'자', label:'자시 (23:30~01:30) · 쥐'}, ...] */
export const branchChoices = () =>
  HOUR_BRANCHES.map(b => ({ value: b, label: `${b}시 (${BRANCH_RANGE[b]}) · ${BRANCH_ANIMAL[b]}` }));

const pad2 = n => String(n).padStart(2, '0');
export const isoDate = d => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;

// ------------------------------------------------------------------ 프로필
/**
 * 운세와 추천 입력을 함께 채우는 사용자 프로필. 이 기기에만 저장된다.
 * 입력이 잘못되면 예외를 던진다.
 */
export function createProfile(opts = {}) {
  const name = String(opts.name ?? '').trim().slice(0, 20);
  let birthDate = String(opts.birthDate ?? '').trim();
  if (birthDate) {
    const m = /^(\d{4})[-./]?(\d{1,2})[-./]?(\d{1,2})$/.exec(birthDate);
    if (!m) throw new Error('생년월일은 YYYY-MM-DD 형식으로 입력하세요.');
    const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
    const dt = new Date(y, mo - 1, d);
    if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) {
      throw new Error(`생년월일이 올바르지 않습니다: ${birthDate}`);
    }
    if (y < 1900 || y > new Date().getFullYear()) throw new Error('생년은 1900년 이후여야 합니다.');
    birthDate = `${y}-${pad2(mo)}-${pad2(d)}`;
  }

  let birthHour = opts.birthHour;
  if (birthHour === '' || birthHour === null || birthHour === undefined) {
    birthHour = null;
  } else {
    const h = Number(birthHour);
    if (!Number.isInteger(h) || h < 0 || h > 23) throw new Error('태어난 시는 0~23 사이여야 합니다.');
    birthHour = h;
  }

  let birthBranch = normalizeBranch(opts.birthBranch);
  if (!birthBranch && birthHour !== null) birthBranch = branchOfTime(birthHour);

  const year = birthDate ? Number(birthDate.slice(0, 4)) : null;
  const zodiac = year ? zodiacOfYear(year) : '';
  const hourAnimal = birthBranch ? BRANCH_ANIMAL[birthBranch] : '';
  return {
    name, birthDate, birthBranch, birthHour, zodiac, hourAnimal,
    hourLabel: birthBranch ? `${birthBranch}시(${hourAnimal})` : '',
    isEmpty: !birthDate,
  };
}

export const emptyProfile = () => createProfile({});

/** 띠수 + 생일수 + 태어난 시의 띠수. 추천 입력의 '내 편' 번호. */
export function personalNumbers(profile) {
  const pool = new Set(zodiacNumbers(profile.zodiac));
  for (const n of birthdayNumbers(profile.birthDate)) pool.add(n);
  if (profile.hourAnimal) for (const n of (ZODIAC_NUMBERS[profile.hourAnimal] || [])) pool.add(n);
  return [...pool].filter(n => NUMBER_POOL.includes(n)).sort((a, b) => a - b);
}

/** 저장·복원용. */
export const profileToJSON = p => ({
  name: p.name, birthDate: p.birthDate, birthBranch: p.birthBranch, birthHour: p.birthHour,
});
export const profileFromJSON = raw => createProfile(raw || {});

/** 추천 폼에 그대로 넣을 값. 생일·띠는 프로필에서, 행운수는 오늘의 숫자에서. */
export function recommendInputs(profile, today = null) {
  const f = dailyFortune(profile, today);
  return { birthday: profile.birthDate, zodiac: profile.zodiac, lucky: [...f.numbers] };
}

// ------------------------------------------------------------------- 운세
const seedOf = (...parts) => parts.map(p => String(p ?? '')).join('|');

function pickGrade(rng) {
  const grades = [5, 4, 3, 2, 1];
  return rng.weighted(grades, grades.map(g => GRADE_WEIGHTS[g]));
}

/** 오늘의 숫자: 개인 번호에서 1~2개 + 나머지는 무작위. 전부 서로 다르게. */
function pickNumbers(rng, personal, count = 3) {
  const chosen = new Set();
  if (personal.length) {
    const take = Math.min(personal.length, rng.choice([1, 2]));
    for (const n of rng.sample(personal, take)) chosen.add(n);
  }
  const rest = NUMBER_POOL.filter(n => !chosen.has(n));
  for (const n of rng.sample(rest, count - chosen.size)) chosen.add(n);
  return [...chosen].sort((a, b) => a - b);
}

/** 프로필과 날짜로 결정되는 오늘의 운세. 프로필이 비어 있으면 날짜만으로 만든다. */
export function dailyFortune(profile = null, today = null) {
  const day = today ? (typeof today === 'string' ? today : isoDate(today)) : isoDate(new Date());
  const p = profile || emptyProfile();
  const branch = p.birthBranch;
  const rng = createRng(seedOf('fortune', day, p.birthDate, branch, p.name));
  const grade = pickGrade(rng);
  const sentence = rng.choice(SENTENCES[grade]);
  const numbers = pickNumbers(rng, personalNumbers(p));
  const color = rng.choice(['노랑', '파랑', '빨강', '회색', '초록']);
  const keyword = rng.choice(KEYWORDS);
  const tip = rng.choice(TIPS);
  const tags = [];
  if (p.zodiac) tags.push(`${p.zodiac}띠`);
  if (branch) tags.push(`${branch}시(${p.hourAnimal})생`);
  return {
    date: day,
    grade,
    label: GRADE_LABELS[grade],
    sentence,
    numbers,
    colors: numbers.map(ballColor),
    color,
    keyword,
    tip,
    zodiac: p.zodiac,
    hourBranch: branch,
    hourAnimal: p.hourAnimal,
    name: p.name,
    tags,
    tagline: TAGLINE,
  };
}

/**
 * 띠로만 보는 오늘. 프로필 없이도 볼 수 있다.
 * 개인 운세(dailyFortune)와는 씨앗이 달라 서로 다른 결과가 나온다. 같은 화면에서
 * 두 값이 어긋나 보이지 않도록, 프로필이 있으면 그 띠를 exclude 로 빼고 보여 준다.
 */
export function zodiacTable(today = null, exclude = '') {
  const day = today ? (typeof today === 'string' ? today : isoDate(today)) : isoDate(new Date());
  const order = ['쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양', '원숭이', '닭', '개', '돼지'];
  return order.filter(z => z !== exclude).map(z => {
    const rng = createRng(seedOf('zodiac', day, z));
    const grade = pickGrade(rng);
    const sentence = rng.choice(SENTENCES[grade]);
    const numbers = pickNumbers(rng, ZODIAC_NUMBERS[z], 2);
    return {
      zodiac: z,
      grade,
      label: GRADE_LABELS[grade],
      short: sentence.split('. ')[0].replace(/\.$/, '') + '.',
      numbers,
      colors: numbers.map(ballColor),
    };
  });
}

/** 금칙어 검사용: 화면에 나갈 수 있는 모든 문장. */
export function allSentences() {
  return [
    ...Object.values(GRADE_LABELS),
    ...Object.values(SENTENCES).flat(),
    ...TIPS, ...KEYWORDS, TAGLINE,
  ];
}

export const forbiddenHits = text => FORBIDDEN_WORDS.filter(w => String(text).includes(w));
