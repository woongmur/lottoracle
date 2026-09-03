/** 조합 하나를 숫자로 뜯어보는 지표들 (대한민국 로또 6/45 기준). */

export const NUMBER_POOL = Array.from({ length: 45 }, (_, i) => i + 1);
export const PICK = 6;
export const LOW_MAX = 22;                       // 저구간 1~22 / 고구간 23~45
// 5개 구간: 1~9, 10~19, 20~29, 30~39, 40~45
export const ZONE_BOUNDS = [[1, 9], [10, 19], [20, 29], [30, 39], [40, 45]];
export const TWIN_NUMBERS = [11, 22, 33, 44];    // 속칭 '쌍둥이수'

/** 오름차순 사본. 원본을 건드리지 않는다. */
export const sortedNums = nums => [...nums].sort((a, b) => a - b);

export const totalSum = nums => nums.reduce((a, b) => a + b, 0);
export const oddCount = nums => nums.filter(n => n % 2).length;
export const lowCount = nums => nums.filter(n => n <= LOW_MAX).length;

export const zoneCounts = nums =>
  ZONE_BOUNDS.map(([lo, hi]) => nums.filter(n => n >= lo && n <= hi).length);

/** AC값 = (서로 다른 차이의 개수) - 5. 6개 조합에서 0~10, 당첨조합은 7~10에 몰린다. */
export function acValue(nums) {
  const ordered = sortedNums(nums);
  const diffs = new Set();
  for (let i = 0; i < ordered.length; i++)
    for (let j = i + 1; j < ordered.length; j++) diffs.add(Math.abs(ordered[i] - ordered[j]));
  return diffs.size - (ordered.length - 1);
}

/** 가장 긴 연속수 길이. 예: [3,4,5,20,31,44] -> 3 */
export function maxConsecutiveRun(nums) {
  const ordered = sortedNums(nums);
  let best = 1, run = 1;
  for (let i = 1; i < ordered.length; i++) {
    run = ordered[i] - ordered[i - 1] === 1 ? run + 1 : 1;
    if (run > best) best = run;
  }
  return best;
}

export function consecutivePairs(nums) {
  const ordered = sortedNums(nums);
  let count = 0;
  for (let i = 1; i < ordered.length; i++) if (ordered[i] - ordered[i - 1] === 1) count++;
  return count;
}

export const endingDigits = nums => nums.map(n => n % 10);
/** 끝수합. 당첨조합은 대체로 15~35. */
export const endingSum = nums => totalSum(endingDigits(nums));

export function maxSameEnding(nums) {
  const counts = new Map();
  for (const d of endingDigits(nums)) counts.set(d, (counts.get(d) || 0) + 1);
  return Math.max(...counts.values());
}

export const multiplesOfThree = nums => nums.filter(n => n % 3 === 0).length;

/** 이월수: 직전 회차 당첨번호와 겹치는 개수. */
export function carryoverCount(nums, previous = []) {
  const prev = new Set(previous);
  return new Set(nums.filter(n => prev.has(n))).size;
}

export const spread = nums => Math.max(...nums) - Math.min(...nums);

/** 조합 하나의 지표 묶음. */
export function profile(nums, previous = []) {
  const numbers = sortedNums(nums);
  const odd = oddCount(numbers);
  const low = lowCount(numbers);
  return {
    numbers,
    total: totalSum(numbers),
    odd,
    even: numbers.length - odd,
    low,
    high: numbers.length - low,
    zones: zoneCounts(numbers),
    ac: acValue(numbers),
    maxRun: maxConsecutiveRun(numbers),
    consecutive: consecutivePairs(numbers),
    endSum: endingSum(numbers),
    sameEnding: maxSameEnding(numbers),
    mult3: multiplesOfThree(numbers),
    spread: spread(numbers),
    carryover: carryoverCount(numbers, previous),
  };
}

/** 파이썬 Profile.summary() 와 같은 문장. */
export function summary(p) {
  return `합계 ${p.total} · 홀짝 ${p.odd}:${p.even} · 고저 ${p.low}:${p.high} · ` +
    `AC ${p.ac} · 끝수합 ${p.endSum} · 연속 ${p.consecutive} · ` +
    `구간 ${p.zones.join('-')} · 이월 ${p.carryover}`;
}
