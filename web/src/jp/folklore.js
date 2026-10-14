/** 일본 로또용 속설 가중. 파이썬 lottoracle/jp/folklore.py 와 같다.
 *
 *   행운수   사용자가 넣은 번호(운세 번호 포함) — ×1.6. 범위 밖 번호는 버린다
 *   기피수   사용자가 뺀 번호 — 0 (절대 안 나온다)
 *   이웃수   직전 회차 번호(보너스 포함) ±1, 본숫자 자신은 빼고 — ×1.25
 *   쌍둥이수 11·22·33 — ×1.15
 *
 * 꿈해몽·띠 번호·볼 색상·용지 모양은 한국 로또(1~45, 동행복권 용지)에 묶인 속설이라 넣지 않는다.
 */
import { numberPool, twinNumbers } from './metrics.js';

export const LUCKY_WEIGHT = 1.6;
export const NEIGHBOR_WEIGHT = 1.25;
export const TWIN_WEIGHT = 1.15;

export const createWishes = ({ lucky = [], avoid = [], enabled = true } = {}) =>
  ({ lucky: [...lucky], avoid: [...avoid], enabled });

/** 범위 안 번호만, 중복 없이 오름차순. */
export const inPool = (game, nums) =>
  [...new Set(nums.map(Number).filter(n => Number.isInteger(n) && n >= 1 && n <= game.pool))]
    .sort((a, b) => a - b);

export function neighborNumbers(game, previous) {
  if (!previous) return new Set();
  const out = new Set();
  for (const n of [...previous.numbers, ...previous.bonus]) {
    for (const m of [n - 1, n + 1]) if (m >= 1 && m <= game.pool) out.add(m);
  }
  for (const n of previous.numbers) out.delete(n);
  return out;
}

export function multipliers(game, wishes, previous) {
  const base = new Map(numberPool(game).map(n => [n, 1.0]));
  if (!wishes || !wishes.enabled) return base;
  for (const n of inPool(game, wishes.lucky)) base.set(n, base.get(n) * LUCKY_WEIGHT);
  for (const n of neighborNumbers(game, previous)) base.set(n, base.get(n) * NEIGHBOR_WEIGHT);
  for (const n of twinNumbers(game)) base.set(n, base.get(n) * TWIN_WEIGHT);
  for (const n of inPool(game, wishes.avoid)) base.set(n, 0.0);
  return base;
}

/** 기피수 — 추천에서 아예 뺀다. */
export const excluded = (game, wishes) => (wishes && wishes.enabled ? inPool(game, wishes.avoid) : []);
