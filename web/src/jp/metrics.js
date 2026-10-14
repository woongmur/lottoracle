/** 일본 로또 조합 하나를 숫자로 뜯어보는 지표들. 파이썬 lottoracle/jp/metrics.py 와 같다.
 *
 * 합계·AC값·연속수·끝수 같은 계산은 번호 범위와 무관해서 한국 쪽 함수를 그대로 쓴다.
 * 범위가 걸린 것(저구간 경계, 10단위 구간, 쌍둥이수)만 게임 규칙표에서 끌어낸다.
 */
import {
  acValue, carryoverCount, consecutivePairs, endingSum, maxConsecutiveRun,
  maxSameEnding, multiplesOfThree, oddCount, sortedNums, spread, totalSum,
} from '../metrics.js';

// 10단위 구간 이름. 미니로또(31까지)는 앞 넷만 쓴다.
export const ZONE_LABELS = ['한 자리', '10번대', '20번대', '30번대', '40번대'];

export const numberPool = game => Array.from({ length: game.pool }, (_, i) => i + 1);

/** 저구간의 끝. 한국 로또가 45 를 1~22 / 23~45 로 가르듯 절반에서 자른다. */
export const lowMax = game => Math.floor(game.pool / 2);

/** 10단위 구간: 1~9, 10~19, … 마지막 구간은 번호 끝에서 자른다. */
export function zoneBounds(game) {
  const out = [[1, 9]];
  for (let lo = 10; lo <= game.pool; lo += 10) out.push([lo, Math.min(lo + 9, game.pool)]);
  return out;
}

/** 쌍둥이수 11·22·33 … 번호 범위 안의 것만. */
export function twinNumbers(game) {
  const out = [];
  for (let n = 11; n <= game.pool; n += 11) out.push(n);
  return out;
}

/** 본숫자 합의 이론 기대값 = 개수 × (범위+1) / 2. 세 게임 모두 정수로 떨어진다. */
export const expectedSum = game => Math.floor((game.pick * (game.pool + 1)) / 2);

export function maxSum(game) {
  let s = 0;
  for (let n = game.pool - game.pick + 1; n <= game.pool; n++) s += n;
  return s;
}

/** 서로 다른 차이는 C(pick,2) 개를 넘을 수 없고, 1~(pool-1) 밖으로도 못 나간다. */
export function maxAc(game) {
  const pairs = (game.pick * (game.pick - 1)) / 2;
  return Math.min(pairs, game.pool - 1) - (game.pick - 1);
}

export const lowCount = (game, nums) => nums.filter(n => n <= lowMax(game)).length;

export const zoneCounts = (game, nums) =>
  zoneBounds(game).map(([lo, hi]) => nums.filter(n => n >= lo && n <= hi).length);

/** 조합 하나의 지표 묶음. 필드는 한국판 profile 과 같다. */
export function profile(game, nums, previous = []) {
  const numbers = sortedNums(nums);
  const odd = oddCount(numbers);
  const low = lowCount(game, numbers);
  return {
    numbers,
    total: totalSum(numbers),
    odd,
    even: numbers.length - odd,
    low,
    high: numbers.length - low,
    zones: zoneCounts(game, numbers),
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

export { summary } from '../metrics.js';
