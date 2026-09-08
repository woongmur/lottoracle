/** 십신·신살·강약 — 팔자 여덟 글자를 '나' 를 중심으로 읽는 층.
 *
 * 파이썬 lottoracle/sipsin.py 와 같은 값을 내야 한다 (골든 데이터로 대조).
 *
 * saju.js 가 세운 여덟 글자는 그 자체로는 이름표일 뿐이다. 명리학은 그중 일간
 * 하나를 '나' 로 놓고 나머지 일곱 글자가 나와 어떤 관계인지를 따진다. 그 관계
 * 이름이 십신이고, 이 층이 있어야 팔자가 비로소 읽힌다.
 *
 * 여기 있는 것도 전부 표에서 나온다. 같은 생일이면 언제나 같은 답이고 명리
 * 교재와 대조할 수 있다. 지어낸 문장은 없다 — 문구는 십신·신살 이름마다 하나씩
 * 붙여 둔 고정 설명이고, 어느 것을 꺼낼지만 계산이 정한다.
 *
 * 유파가 갈리는 곳은 아래 셋뿐이고, 고른 쪽을 화면에도 적어 둔다.
 *
 *   1. 지지의 십신   지지를 지장간 '본기' 로 바꿔서 천간처럼 본다. 그래서 亥는
 *                    임수(양), 巳는 병화(양)로 친다. 자리 순서로 음양을 매기는
 *                    유파를 따르면 정관이 편관이 되는 식으로 달라진다.
 *   2. 신강·신약     인성·비겁을 '돕는 기운', 식상·재성·관성을 '쓰는 기운' 으로
 *                    놓고 개수를 센다. 월지는 계절이라 두 몫으로 친다(득령).
 *                    조후·통근 세기까지 따지는 유파와는 결과가 다를 수 있다.
 *   3. 신살          기운을 북돋우는 쪽(천을귀인·문창귀인·역마·도화·화개)만 쓴다.
 *                    겁주는 살은 넣지 않는다 — 이 사이트는 운세에서도 그렇게 한다.
 */
import { BRANCHES, ELEMENTS, STEM_ELEMENT, STEM_YIN, STEMS } from './saju.js';

// 나(일간)와 상대 글자의 관계 열 가지. 오행 관계 다섯 × 음양이 같은가 두 가지.
export const TEN_GODS = ['비견', '겁재', '식신', '상관', '편재', '정재',
  '편관', '정관', '편인', '정인'];

// 지지 속에 숨은 천간(지장간) 중 그 지지를 대표하는 글자(본기).
// 자=계 축=기 인=갑 묘=을 진=무 사=병 오=정 미=기 신=경 유=신 술=무 해=임
export const BRANCH_MAIN_QI = [9, 5, 0, 1, 4, 2, 3, 5, 6, 7, 4, 8];


// 나를 돕는 쪽(인성·비겁)과 나를 쓰는 쪽(식상·재성·관성).
export const SUPPORTING = ['비견', '겁재', '편인', '정인'];

// 십신을 다섯 갈래로 묶은 이름. 화면에서 '무엇이 많은가' 를 말할 때 쓴다.
export const GOD_GROUP = {
  비견: '비겁', 겁재: '비겁',
  식신: '식상', 상관: '식상',
  편재: '재성', 정재: '재성',
  편관: '관성', 정관: '관성',
  편인: '인성', 정인: '인성',
};
const GROUPS = ['비겁', '식상', '재성', '관성', '인성'];

/**
 * 일간에서 본 상대 천간의 십신.
 *
 * 오행 관계를 (상대 - 나) 로 재면 다섯 가지가 순서대로 떨어진다.
 *   0 같은 오행   1 내가 생함   2 내가 극함   3 나를 극함   4 나를 생함
 * 여기에 음양이 같으면 앞쪽(비견·식신·편재·편관·편인),
 * 다르면 뒤쪽(겁재·상관·정재·정관·정인)이다. '정' 이 붙는 쪽이 짝이 맞는 관계다.
 */
export function tenGod(dayStem, target) {
  const rel = ((STEM_ELEMENT[target] - STEM_ELEMENT[dayStem]) % 5 + 5) % 5;
  const same = STEM_YIN[target] === STEM_YIN[dayStem];
  return TEN_GODS[rel * 2 + (same ? 0 : 1)];
}

/** 지지의 십신. 지지를 본기 천간으로 바꾼 뒤 천간과 똑같이 본다. */
export function tenGodOfBranch(dayStem, branch) {
  return tenGod(dayStem, BRANCH_MAIN_QI[branch]);
}

export const PILLAR_LABELS = ['년', '월', '일', '시'];

/** 네 기둥의 여덟 글자에 십신을 매긴다. 일간만 '나' 다. */
export function tenGodsTable(pillars, dayStem) {
  return pillars.map((p, i) => ({
    pillar: PILLAR_LABELS[i],
    stemChar: STEMS[p.stem],
    branchChar: BRANCHES[p.branch],
    stem: i === 2 ? '일간' : tenGod(dayStem, p.stem),
    branch: tenGodOfBranch(dayStem, p.branch),
    isSelf: i === 2,
  }));
}

/** 십신이 몇 번씩 나왔나. 일간 자신은 '나' 라 세지 않는다. */
export function tenGodCounts(pillars, dayStem) {
  const out = {};
  for (const g of TEN_GODS) out[g] = 0;
  pillars.forEach((p, i) => {
    if (i !== 2) out[tenGod(dayStem, p.stem)] += 1;
    out[tenGodOfBranch(dayStem, p.branch)] += 1;
  });
  return out;
}

/** 십신 열 가지를 비겁·식상·재성·관성·인성 다섯 갈래로 합친다. */
export function groupCounts(counts) {
  const out = {};
  for (const g of GROUPS) out[g] = 0;
  for (const [name, n] of Object.entries(counts)) out[GOD_GROUP[name]] += n;
  return out;
}

// ---- 강약 -------------------------------------------------------------

/**
 * 나를 돕는 기운과 쓰는 기운의 개수로 신강·신약을 가른다.
 *
 * 월지는 태어난 계절이라 나머지 글자보다 무겁게 친다(득령). 두 몫으로 셌다.
 * 비율로 재는 이유는 시주를 모르면 글자 수가 줄기 때문이다.
 *
 * 이건 간단히 세는 방식이다. 통근 세기와 조후까지 따지는 유파와는 결과가
 * 다를 수 있어서, 화면에는 개수를 그대로 같이 보여 준다.
 */
export function strength(pillars, dayStem) {
  let support = 0, other = 0;
  const add = (god, weight) => {
    if (SUPPORTING.includes(god)) support += weight; else other += weight;
  };
  pillars.forEach((p, i) => {
    if (i !== 2) add(tenGod(dayStem, p.stem), 1);       // 일간은 '나' 라 세지 않는다
    // 두 몫으로 세는 건 월'지' 뿐이다. 계절을 가리키는 글자가 그것이라서다.
    add(tenGodOfBranch(dayStem, p.branch), i === 1 ? 2 : 1);
  });
  const total = support + other;
  const ratio = total ? support / total : 0;
  const label = ratio >= 0.55 ? '신강' : (ratio <= 0.40 ? '신약' : '중화');
  return { label, support, other, ratio: Math.round(ratio * 1000) / 1000 };
}

// ---- 신살 -------------------------------------------------------------

// 천을귀인 — 일간에서 본다. 갑무경은 축미, 을기는 자신, 병정은 해유,
// 임계는 사묘, 신(辛)은 인오.
export const NOBLEMAN = {
  0: [1, 7], 4: [1, 7], 6: [1, 7],
  1: [0, 8], 5: [0, 8],
  2: [11, 9], 3: [11, 9],
  8: [5, 3], 9: [5, 3],
  7: [2, 6],
};
// 문창귀인 — 일간이 생하는 기운의 자리. 글재주·공부와 엮어 본다.
export const SCHOLAR = { 0: 5, 1: 6, 2: 8, 3: 9, 4: 8, 5: 9, 6: 11, 7: 0, 8: 2, 9: 3 };

// 삼합국별 역마·도화·화개. 년지와 일지를 기준으로 본다.
const TRIAD = [
  [[8, 0, 4], { 역마: 2, 도화: 9, 화개: 4 }],      // 신자진 수국
  [[2, 6, 10], { 역마: 8, 도화: 3, 화개: 10 }],    // 인오술 화국
  [[5, 9, 1], { 역마: 11, 도화: 6, 화개: 1 }],     // 사유축 금국
  [[11, 3, 7], { 역마: 5, 도화: 0, 화개: 7 }],     // 해묘미 목국
];

function triadOf(branch) {
  for (const [group, table] of TRIAD) if (group.includes(branch)) return table;
  throw new Error(`삼합국에 없는 지지: ${branch}`);
}

const SINSAL_ORDER = ['천을귀인', '문창귀인', '역마', '도화', '화개'];

/**
 * 사주에 든 신살. 어느 기둥에 있는지까지 적는다.
 *
 * 역마·도화·화개는 기준 지지(년지·일지)에서 뽑은 글자가 사주 안에 있는지로
 * 본다. 년지 기준과 일지 기준이 다른 글자를 가리키면 둘 다 본다.
 */
export function sinsal(pillars, dayStem) {
  const branches = pillars.map(p => p.branch);
  const labels = PILLAR_LABELS.slice(0, pillars.length);
  const found = new Map();

  const hit = (name, target) => {
    labels.forEach((lab, i) => {
      if (branches[i] !== target) return;
      if (!found.has(name)) found.set(name, []);
      if (!found.get(name).includes(lab)) found.get(name).push(lab);
    });
  };

  for (const target of NOBLEMAN[dayStem]) hit('천을귀인', target);
  hit('문창귀인', SCHOLAR[dayStem]);

  const bases = [branches[0]];                  // 년지
  if (branches.length > 2) bases.push(branches[2]);   // 일지
  for (const base of bases) {
    for (const [name, target] of Object.entries(triadOf(base))) hit(name, target);
  }

  return SINSAL_ORDER.filter(n => found.has(n))
    .map(n => ({ name: n, at: found.get(n).map(lab => `${lab}지`) }));
}

// ---- 문구 -------------------------------------------------------------
//
// 아래는 전부 고정 문장이다. 어느 것을 꺼낼지만 위의 계산이 정한다.
// 단정하지 않는다, 겁주지 않는다, 로또 당첨과 엮지 않는다 — 운세 모듈과 같은 규칙.

// 일간 열 가지. [물상, 성정]
export const DAY_STEM_TEXT = {
  갑: ['큰 나무', '곧게 자라는 나무입니다. 위로 뻗는 기질이라 시작하는 힘이 좋고 '
    + '밀어붙이는 뚝심이 있습니다. 대신 한번 정한 방향을 바꾸기는 쉽지 않습니다.'],
  을: ['풀과 덩굴', '휘어져도 부러지지 않는 기운입니다. 상황에 맞춰 자세를 바꾸는 '
    + '유연함과 끈기가 있습니다. 겉은 부드럽지만 좀처럼 꺾이지 않습니다.'],
  병: ['한낮의 해', '사방을 비추는 큰 불입니다. 밝고 솔직하며 사람을 끌어당깁니다. '
    + '감정이 그대로 드러나는 편이라 숨기는 것을 잘 못 합니다.'],
  정: ['촛불과 달빛', '은은하게 오래 가는 불입니다. 겉은 부드럽고 속은 뜨겁습니다. '
    + '사람과 상황을 세심하게 살피고, 한번 마음먹으면 잘 꺾이지 않습니다.'],
  무: ['넓은 땅과 산', '묵직하게 버티는 기운입니다. 웬만한 일에 흔들리지 않아 '
    + '사람들이 기대는 자리에 서게 됩니다. 대신 움직임이 더딜 수 있습니다.'],
  기: ['밭의 흙', '품어서 길러 내는 기운입니다. 남을 돌보고 조율하는 데 능하고 '
    + '속이 깊습니다. 생각을 안으로 삼키는 편이라 속내를 알기 어렵습니다.'],
  경: ['무쇠와 원석', '단단하고 결단이 빠른 기운입니다. 옳고 그름이 분명하고 '
    + '추진력이 있습니다. 다듬어질수록 빛나는 대신 초년에 부딪힘이 있습니다.'],
  신: ['보석과 칼날', '다듬어진 쇠입니다. 예민하고 정교하며 완성도를 따집니다. '
    + '깔끔한 대신 스스로에게도 남에게도 기준이 높습니다.'],
  임: ['바다와 큰 강', '넓게 흐르는 물입니다. 생각이 크고 포용력이 있으며 '
    + '머리 회전이 빠릅니다. 한곳에 머무는 것을 답답해합니다.'],
  계: ['빗물과 이슬', '스며드는 물입니다. 섬세하고 감이 좋으며 티 내지 않고 '
    + '돕습니다. 마음이 여려 주변 기운을 그대로 받습니다.'],
};

// 십신 열 가지. [한 단어, 설명]
export const TEN_GOD_TEXT = {
  비견: ['자립', '나와 같은 기운입니다. 스스로 서려는 힘, 함께 가는 동료, '
    + '그리고 대등한 경쟁을 뜻합니다.'],
  겁재: ['승부', '나와 같지만 결이 다른 기운입니다. 밀어붙이는 추진력과 승부욕, '
    + '나누는 마음과 부딪힘이 함께 있습니다.'],
  식신: ['표현', '내가 내놓는 기운입니다. 꾸준히 만들어 내는 힘, 먹고사는 즐거움, '
    + '여유 있는 표현을 뜻합니다.'],
  상관: ['재능', '내가 내놓는 기운 중 튀는 쪽입니다. 말솜씨와 재주, 틀을 깨는 '
    + '감각이 있습니다. 참는 것을 답답해합니다.'],
  편재: ['활동', '내가 다루는 몫 중 크게 도는 쪽입니다. 활동 범위가 넓고 '
    + '기회를 잡는 감각이 있습니다. 씀씀이도 함께 큽니다.'],
  정재: ['실속', '내가 다루는 몫 중 꾸준한 쪽입니다. 성실하게 쌓고 지키는 힘, '
    + '약속을 지키는 실속을 뜻합니다.'],
  편관: ['돌파', '나를 누르는 힘 중 센 쪽입니다. 결단과 위기 돌파력을 주는 대신 '
    + '스스로를 몰아붙이는 압박이 되기도 합니다.'],
  정관: ['책임', '나를 바르게 잡아 주는 힘입니다. 규칙을 지키는 성품, 책임감, '
    + '조직과 명예를 뜻합니다.'],
  편인: ['직관', '나를 돕는 기운 중 독특한 쪽입니다. 직관과 전문성, 남들이 잘 '
    + '가지 않는 분야에서의 깊이를 뜻합니다.'],
  정인: ['배움', '나를 돕는 기운입니다. 공부와 문서, 윗사람의 도움, 마음의 '
    + '안정을 뜻합니다.'],
};

// 신살 다섯. [한 단어, 설명]
export const SINSAL_TEXT = {
  천을귀인: ['귀인', '명리학에서 가장 좋게 보는 자리입니다. 어려울 때 돕는 사람이 '
    + '나타나거나 일이 풀려 나가는 복으로 읽습니다.'],
  문창귀인: ['문창', '글과 공부에 붙는 자리입니다. 배우고 정리하고 표현하는 일이 '
    + '잘 맞는다고 봅니다.'],
  역마: ['이동', '움직임의 자리입니다. 이사·출장·해외처럼 자리를 옮기는 일이 '
    + '잦거나, 그런 일에서 잘 풀린다고 봅니다.'],
  도화: ['매력', '사람을 끄는 자리입니다. 인기와 표현력으로 읽습니다. '
    + '예전에는 흉하게 봤지만 요즘은 매력으로 봅니다.'],
  화개: ['몰입', '한곳에 깊이 파고드는 자리입니다. 예술·종교·연구처럼 '
    + '혼자 오래 붙드는 일과 인연이 있다고 봅니다.'],
};

// 다섯 갈래가 많을 때. 셋 이상이면 '치우쳤다' 고 본다.
export const GROUP_MANY_TEXT = {
  비겁: '자기 색이 뚜렷하고 남에게 기대지 않으려 합니다. 함께하는 일에서는 '
    + '역할을 나누는 것이 편합니다.',
  식상: '표현하고 만들어 내는 기운이 강합니다. 재주가 겉으로 드러나고, '
    + '틀에 갇히면 답답해합니다.',
  재성: '현실 감각과 활동 범위가 넓습니다. 눈앞의 일을 잘 챙기는 대신 '
    + '벌여 놓는 일도 많아집니다.',
  관성: '책임과 규칙을 무겁게 여깁니다. 맡은 자리를 지키는 힘이 있고, '
    + '스스로를 몰아붙이는 편입니다.',
  인성: '배우고 받아들이는 기운이 강합니다. 생각이 깊은 대신 '
    + '실행보다 궁리가 길어질 수 있습니다.',
};
// 다섯 갈래가 아예 없을 때.
export const GROUP_NONE_TEXT = {
  비겁: '혼자 버티기보다 사람을 곁에 두는 편이 낫다고 봅니다.',
  식상: '표현할 자리를 일부러 만들어 두는 편이 낫다고 봅니다.',
  재성: '돈과 현실 문제는 미루지 말고 그때그때 챙기는 편이 낫다고 봅니다.',
  관성: '스스로 규칙을 정해 두는 편이 낫다고 봅니다.',
  인성: '배우고 쉬는 시간을 따로 떼어 두는 편이 낫다고 봅니다.',
};

export const STRENGTH_TEXT = {
  신강: '나를 돕는 기운이 많습니다. 밀고 나가는 힘이 좋아 스스로 일을 벌이고 '
    + '끌고 가는 쪽이 맞습니다. 다만 고집이 세질 수 있어 덜어 내는 자리 — '
    + '내놓고(식상) 쓰고(재성) 맡는(관성) 일 — 가 있으면 편해집니다.',
  중화: '돕는 기운과 쓰는 기운이 얼추 맞습니다. 한쪽으로 쏠리지 않아 '
    + '상황에 맞춰 자세를 바꾸기 쉽고, 환경이 바뀌어도 크게 흔들리지 '
    + '않는다고 봅니다.',
  신약: '쓰는 기운이 많습니다. 주변을 살피고 맞춰 주는 힘이 좋은 대신 '
    + '혼자 다 짊어지면 지칩니다. 도와주는 자리 — 배우고(인성) 함께하는'
    + '(비겁) 자리 — 를 곁에 두면 편해집니다.',
};

export const ELEMENTS_FULL_TEXT = '목·화·토·금·수가 하나도 빠지지 않았습니다. 한쪽으로 쏠리지 '
  + '않아 어떤 환경에 놓여도 무난하게 적응한다고 봅니다.';

/** 오행 분포 한 줄. 다 있으면 그 자체가 좋은 말이고, 없으면 어느 것이 없는지. */
function elementsNote(elements) {
  const missing = ELEMENTS.filter(e => !elements[e]);
  if (!missing.length) return ELEMENTS_FULL_TEXT;
  let most = ELEMENTS[0];
  for (const e of ELEMENTS) if ((elements[e] || 0) > (elements[most] || 0)) most = e;
  return `${missing.join('·')}가 없고 ${most}이 가장 많습니다. 없는 기운은 `
    + '그 자리를 사람이나 환경에서 채우게 된다고 봅니다.';
}

/**
 * 팔자 한 벌을 읽어서 화면에 넘길 묶음으로 만든다.
 *
 * pillars 는 [년주, 월주, 일주, 시주]. 태어난 시를 모르면 세 기둥만 넘긴다 —
 * 모르는 값을 지어내지 않으려고 시주는 아예 빼고 센다.
 */
export function reading(pillars, dayStem, elements) {
  const counts = tenGodCounts(pillars, dayStem);
  const groups = groupCounts(counts);
  const st = strength(pillars, dayStem);
  const stemChar = STEMS[dayStem];
  const [image, nature] = DAY_STEM_TEXT[stemChar];

  // 두 번 이상 나온 십신을 많은 순서로. 같으면 십신 차례대로 — 순서가 흔들리면
  // 같은 생일에 다른 화면이 나온다.
  const strong = TEN_GODS.filter(g => counts[g] >= 2)
    .sort((a, b) => counts[b] - counts[a] || TEN_GODS.indexOf(a) - TEN_GODS.indexOf(b));

  return {
    dayStem: { char: stemChar, image, nature, element: ELEMENTS[STEM_ELEMENT[dayStem]] },
    table: tenGodsTable(pillars, dayStem),
    counts,
    groups,
    strong: strong.map(g => ({
      name: g, count: counts[g], word: TEN_GOD_TEXT[g][0], text: TEN_GOD_TEXT[g][1],
    })),
    manyGroups: GROUPS.filter(g => groups[g] >= 3)
      .map(g => ({ name: g, count: groups[g], text: GROUP_MANY_TEXT[g] })),
    noneGroups: GROUPS.filter(g => groups[g] === 0)
      .map(g => ({ name: g, text: GROUP_NONE_TEXT[g] })),
    strength: { ...st, text: STRENGTH_TEXT[st.label] },
    sinsal: sinsal(pillars, dayStem).map(s => ({
      ...s, word: SINSAL_TEXT[s.name][0], text: SINSAL_TEXT[s.name][1],
    })),
    elementsNote: elementsNote(elements),
  };
}
