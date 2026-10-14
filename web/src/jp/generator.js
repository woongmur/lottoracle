/** 일본 로또 추천 조합 — 가중 추첨 + 필터. 한국판 generator.js 를 게임 규칙표로 옮긴 것.
 *
 * 난수가 개입하므로 파이썬과 값을 맞추지 않는다(한국판과 같다). 테스트는 결정론·규칙
 * 준수·범위 같은 성질을 본다.
 *
 * 한국판과 다른 점: 보너스 숫자는 추천하지 않는다. 일본 로또는 사는 사람이 보너스를
 * 고르지 않는다(보너스는 2등을 가르는 데만 쓰인다). 그래서 한 줄은 본숫자뿐이다.
 */
import { createRng } from '../rng.js';
import { check, relaxed } from './filters.js';
import { excluded as wishExcluded, multipliers } from './folklore.js';
import { numberPool, twinNumbers } from './metrics.js';
import { defaultWeights, typicality, typicalityPercentile } from './model.js';
import { pairKey } from './stats.js';
import { strategies as allStrategies } from './strategies.js';

export const MIN_WEIGHT = 0.05;   // 어떤 번호도 확률 0이 되지 않게 (기피수만 예외)

const setKey = nums => [...nums].sort((a, b) => a - b).join(',');
const intersectSize = (aSet, bSet) => [...aSet].filter(n => bSet.has(n)).length;

function standardize(values) {
  const xs = [...values.values()];
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const variance = xs.reduce((a, x) => a + (x - mean) ** 2, 0) / xs.length;
  const sd = Math.sqrt(variance);
  const out = new Map();
  for (const [k, v] of values) out.set(k, sd < 1e-9 ? 0.0 : (v - mean) / sd);
  return out;
}

/** 전략 가중치 + 과거 통계 + 속설로 번호별 기본 가중치. */
export function baseWeights(game, strategy, stats, wishes = null, previous = null) {
  const pool = numberPool(game);
  const twins = new Set(twinNumbers(game));
  const zero = () => new Map(pool.map(n => [n, 0.0]));
  let zFreq = zero(), zRecent = zero(), zGap = zero();
  if (stats.drawsUsed) {
    zFreq = standardize(new Map(pool.map(n => [n, stats.frequency.get(n) || 0])));
    zRecent = standardize(new Map(pool.map(n => [n, stats.recent.get(n) || 0])));
    zGap = standardize(new Map(pool.map(n => [n, stats.gap.get(n) || 0])));
  }
  const weights = new Map();
  for (const n of pool) {
    const score = strategy.wFrequency * zFreq.get(n)
      + strategy.wRecent * zRecent.get(n)
      + strategy.wGap * zGap.get(n)
      + (twins.has(n) ? strategy.wTwin : 0.0);
    weights.set(n, Math.max(MIN_WEIGHT, Math.exp(score * 0.6)));
  }
  for (const [n, factor] of multipliers(game, wishes, previous)) {
    weights.set(n, factor === 0.0 ? 0.0 : Math.max(MIN_WEIGHT, weights.get(n) * factor));
  }
  if (![...weights.values()].some(w => w > 0)) {
    throw new Error('기피수가 너무 많아 뽑을 번호가 남지 않았습니다.');
  }
  return weights;
}

/** 이미 뽑힌 번호들과의 궁합수(동반 출현) 가중. 기대 동반 횟수는 게임마다 다르다. */
function companionBoost(game, candidate, chosen, stats, strength) {
  if (!chosen.length || !stats.pairs.size || strength === 0) return 1.0;
  const counts = chosen.map(c => stats.pairs.get(pairKey(candidate, c)) || 0);
  const avg = counts.reduce((a, b) => a + b, 0) / counts.length;
  // 두 번호가 같은 회차에 함께 나올 확률 = pick(pick-1) / (pool(pool-1))
  const expected = stats.drawsUsed
    ? stats.drawsUsed * ((game.pick - 1) / (game.pool - 1)) * (game.pick / game.pool) : 0;
  if (expected <= 0) return 1.0;
  return Math.max(MIN_WEIGHT, Math.exp((strength * 0.5 * (avg - expected)) / expected));
}

function weightedSample(game, pool, k, weights, stats, strategy, chosen, rng) {
  const remaining = [...pool];
  const picked = [];
  for (let i = 0; i < k && remaining.length; i++) {
    const ws = remaining.map(n =>
      weights.get(n) * companionBoost(game, n, [...chosen, ...picked], stats, strategy.wCompanion));
    const idx = rng.weightedIndex(ws);
    picked.push(remaining[idx]);
    remaining.splice(idx, 1);
  }
  return picked;
}

/** 전략이 요구하는 고정 번호(이월수 / 직전 보너스). 로또7 은 보너스가 둘이라 하나를 고른다. */
function forcedNumbers(game, strategy, previous, weights, stats, rng) {
  const forced = [];
  if (!previous) return forced;
  if (strategy.usePrevBonus && previous.bonus.length) forced.push(rng.choice(previous.bonus));
  if (strategy.carryoverTarget > 0) {
    const pool = previous.numbers.filter(n => !forced.includes(n));
    forced.push(...weightedSample(
      game, pool, Math.min(strategy.carryoverTarget, pool.length), weights, stats, strategy, forced, rng));
  }
  return forced;
}

/**
 * 한 줄. 한국판 generateLine 과 같은 3단계:
 * 규칙을 통과하는 후보 모으기(못 모으면 완화) → 전형성 소프트맥스 선택 → 줄끼리 겹침 제한.
 */
export function generateLine(game, strategy, stats, options = {}) {
  const {
    previous = null, rng = createRng(), bannedSets = [], maxAttempts = 4000,
    wishes = null, emp = null, reference = [], temperature = 1.0, maxOverlap = null,
    rulesOverride = null, scoreWeights = defaultWeights(),
  } = options;
  let { candidates = 40 } = options;
  const pick = game.pick;
  const overlapCap = maxOverlap ?? Math.floor(pick / 2);

  const weights = baseWeights(game, strategy, stats, wishes, previous);
  const prevNumbers = previous ? previous.numbers : [];
  const excludedSet = new Set(wishExcluded(game, wishes));
  const banned = bannedSets.map(s => new Set(s));
  const bannedKeys = new Set(bannedSets.map(setKey));
  const baseRules = rulesOverride || strategy.rules;
  const found = [];
  const seen = new Set();
  if (emp === null) candidates = 1;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const step = Math.floor(attempt / Math.max(1, Math.floor(maxAttempts / 6)));
    let rules = step === 0 ? baseRules : relaxed(game, baseRules, step);
    if (!previous) rules = { ...rules, carryoverRange: [0, pick] };

    let forced = forcedNumbers(game, strategy, previous, weights, stats, rng)
      .filter(n => !excludedSet.has(n));
    if (forced.length > pick) forced = forced.slice(0, pick);
    const pool = numberPool(game).filter(n => !forced.includes(n) && !excludedSet.has(n));
    const rest = weightedSample(game, pool, pick - forced.length, weights, stats, strategy, forced, rng);
    const nums = [...forced, ...rest].sort((a, b) => a - b);
    const key = setKey(nums);
    if (nums.length < pick || bannedKeys.has(key) || seen.has(key)) continue;

    const overlapLimit = step < 3 ? overlapCap : pick;
    const numSet = new Set(nums);
    if (banned.some(b => intersectSize(numSet, b) > overlapLimit)) continue;

    const verdict = check(game, nums, rules, prevNumbers);
    if (!verdict.ok) continue;
    seen.add(key);
    found.push({ numbers: nums, profile: verdict.profile, step, attempt });
    if (found.length >= candidates) break;
  }

  if (!found.length) {
    throw new Error(`[${strategy.name}] 조건을 만족하는 조합을 찾지 못했습니다. 기피수를 줄여 보세요.`);
  }

  const scores = found.map(f => (emp ? typicality(f.numbers, emp, prevNumbers, scoreWeights) : 0.0));
  let chosen = 0;
  if (emp !== null && found.length > 1) {
    const t = Math.max(0.05, temperature);
    const top = Math.max(...scores);
    chosen = rng.weightedIndex(scores.map(sc => Math.exp((sc - top) / t)));
  }
  const pickOne = found[chosen];
  const score = scores[chosen];
  return {
    strategy,
    numbers: pickOne.numbers,
    profile: pickOne.profile,
    relaxedStep: pickOne.step,
    attempts: pickOne.attempt,
    typicality: score,
    percentile: emp ? typicalityPercentile(score, reference) : 50.0,
    poolSize: found.length,
  };
}

/**
 * 서로 다른 전략으로 lines줄. 줄끼리 maxOverlap 개 넘게 겹치지 않게 한다
 * (기본은 고르는 개수의 절반: 로또6 3 · 로또7 3 · 미니로또 2).
 */
export function recommend(game, stats, options = {}) {
  const {
    previous = null, strategies = allStrategies(game), lines = 5, seed = null,
    wishes = null, emp = null, reference = [], candidates = 40, temperature = 1.0,
    maxOverlap = null, rulesOverride = null, scoreWeights = defaultWeights(),
  } = options;
  const rng = createRng(seed);
  const out = [];
  const used = [];
  for (let i = 0; i < lines; i++) {
    const strategy = strategies[i % strategies.length];
    const rules = rulesOverride
      ? { ...rulesOverride, carryoverRange: strategy.rules.carryoverRange }
      : null;
    const line = generateLine(game, strategy, stats, {
      previous, rng, bannedSets: used, wishes, emp, reference,
      candidates, temperature, maxOverlap, rulesOverride: rules, scoreWeights,
    });
    used.push(line.numbers);
    out.push(line);
  }
  return out;
}
