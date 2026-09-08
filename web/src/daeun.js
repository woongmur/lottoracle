/** 대운 — 10년마다 바뀌는 큰 흐름.
 *
 * 파이썬 lottoracle/daeun.py 와 같은 값을 내야 한다 (골든 데이터로 대조).
 *
 * 팔자는 태어난 순간에 고정된다. 대운은 거기서 시간이 흐르는 축이라, 사람들이
 * 사주에서 가장 자주 다시 보는 자리다("지금 내가 어디쯤인가").
 *
 * 세 가지를 정하면 끝난다. 전부 표와 산수다.
 *
 *   방향   년간이 양이고 남자, 또는 년간이 음이고 여자면 순행. 반대면 역행.
 *          여기서만 성별이 필요하다 — 팔자 여덟 글자와 십신은 성별과 무관하다.
 *   시작   순행이면 태어난 순간부터 '다음' 절입까지, 역행이면 '지난' 절입부터
 *          태어난 순간까지의 날수를 세어 3일을 1년으로 친다(대운수).
 *   간지   월주에서 60갑자를 한 칸씩 순행/역행으로 옮긴다. 한 칸이 10년이다.
 *
 * 유파가 갈리는 곳은 대운수의 끝수 처리다. 여기서는 날수를 3으로 나눠 반올림
 * 한다(나머지 1일은 버리고 2일은 올리는 관행과 같은 값). 화면에는 잰 날수를
 * 그대로 함께 적어서, 다른 만세력과 하루 이틀 다를 때 왜 그런지 보이게 했다.
 */
import { BRANCH_ANIMALS, BRANCH_HANJA, BRANCHES, STEM_HANJA, STEM_YIN, STEMS, nextJeol, prevJeol } from './saju.js';
import { TEN_GOD_TEXT, tenGod, tenGodOfBranch } from './sipsin.js';

// 몇 칸까지 보여 줄까. 대운수(1~10)에 80년을 더하면 90 언저리라 한 생애를 덮는다.
export const COUNT = 8;

export const INTRO = '대운은 10년마다 바뀌는 큰 흐름입니다. 태어난 달(월주)에서 60갑자를 '
  + '한 칸씩 옮겨 가며 정하고, 어느 쪽으로 옮길지는 년간의 음양과 성별로 갈립니다.';
export const BEFORE_FIRST = '첫 대운에 들기 전까지는 태어난 달(월주)의 기운이 그대로 이어진다고 봅니다.';
export const NO_GENDER = '대운은 방향이 성별로 갈려서 성별을 알아야 세울 수 있습니다. '
  + '프로필에 넣으면 함께 보여 드립니다. 지금 보이는 여덟 글자와 십신은 '
  + '성별과 무관하니 그대로입니다.';

/** 천간·지지 -> 60갑자 번호. 십간과 십이지가 맞물리는 자리는 하나뿐이다. */
export function gzIndex(pillar) {
  for (let i = 0; i < 60; i += 1) {
    if (i % 10 === pillar.stem && i % 12 === pillar.branch) return i;
  }
  throw new Error('60갑자에 없는 짝');
}

/** 순행인가. 년간이 양이고 남자, 또는 년간이 음이고 여자면 순행이다. */
export function isForward(yearStem, male) {
  return (!STEM_YIN[yearStem]) === male;
}

export function directionReason(yearStem, male) {
  const yin = STEM_YIN[yearStem];
  return `년간이 ${yin ? '음' : '양'}(${STEMS[yearStem]})이고 `
    + `${male ? '남자' : '여자'}라 ${isForward(yearStem, male) ? '순행' : '역행'}입니다`;
}

/**
 * 대운이 언제부터인가. 절입까지의 날수를 3으로 나눈다.
 *
 * 3일이 1년이므로 하루는 4개월, 두 시간은 10일이다. 여기서는 초 단위로 잰
 * 간격을 그대로 나눠서 년·개월까지 낸 다음, 관행대로 반올림한 대운수도 함께 낸다.
 */
export function startAt(utcEpoch, forward) {
  const [name, target] = (forward ? nextJeol : prevJeol)(utcEpoch);
  const days = Math.abs(target - utcEpoch) / 86400;
  const years = days / 3;
  return {
    jeol: name,
    days: Math.round(days * 100) / 100,
    years: Math.round(years * 1000) / 1000,
    number: Math.round(years),              // 화면과 나이 구간에 쓰는 대운수
    months: Math.round((years % 1) * 12),
  };
}

/** 월주에서 한 칸씩. 순행이면 다음 갑자, 역행이면 이전 갑자. */
export function pillarsFrom(month, forward, count = COUNT) {
  const base = gzIndex(month);
  const step = forward ? 1 : -1;
  return Array.from({ length: count }, (_, k) => {
    const i = (((base + step * (k + 1)) % 60) + 60) % 60;
    const stem = i % 10, branch = i % 12;
    return {
      stem, branch,
      name: STEMS[stem] + BRANCHES[branch],
      hanja: STEM_HANJA[stem] + BRANCH_HANJA[branch],
      animal: BRANCH_ANIMALS[branch],
    };
  });
}

/** 지금 몇 번째 대운인가. 첫 대운 전이거나 표 밖이면 null. */
export function currentIndex(number, age, count = COUNT) {
  if (age === null || age === undefined || age < number) return null;
  const k = Math.floor((age - number) / 10);
  return k < count ? k : null;
}

/** 대운 한 벌. 성별을 모르면 null — 방향을 찍어 맞힐 수는 없다. */
export function daeun(year, month, dayStem, utcEpoch, gender, age = null) {
  if (gender !== '남' && gender !== '여') return null;
  const male = gender === '남';
  const forward = isForward(year.stem, male);
  const start = startAt(utcEpoch, forward);
  const now = currentIndex(start.number, age);

  const list = pillarsFrom(month, forward).map((p, k) => {
    const stemGod = tenGod(dayStem, p.stem);
    const branchGod = tenGodOfBranch(dayStem, p.branch);
    return {
      index: k + 1,
      from: start.number + 10 * k,
      to: start.number + 10 * (k + 1),
      name: p.name,
      hanja: p.hanja,
      animal: p.animal,
      stemGod,
      branchGod,
      word: TEN_GOD_TEXT[stemGod][0],
      now: now === k,
    };
  });

  const out = {
    forward,
    reason: directionReason(year.stem, male),
    gender,
    start,
    list,
    current: now === null ? null : list[now],
    beforeFirst: age !== null && age !== undefined && age < start.number,
  };
  if (out.current) out.currentText = TEN_GOD_TEXT[out.current.stemGod][1];
  return out;
}
