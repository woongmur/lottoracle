/** 가중 추첨 + 필터링으로 추천 조합을 만든다. */
import { check, relaxed } from './filters.js';
import { accepts, excluded as folkloreExcluded, luckScore, luckTags, multipliers } from './folklore.js';
import { NUMBER_POOL, PICK, TWIN_NUMBERS } from './metrics.js';
import { defaultWeights, typicality, typicalityPercentile } from './model.js';
import { pairKey } from './stats.js';
import { createRng } from './rng.js';
import { DEFAULT_STRATEGIES } from './strategies.js';

export const MIN_WEIGHT = 0.05;   // 어떤 번호도 확률 0이 되지 않게 (모든 번호는 나올 수 있다)

/** 조합을 집합 비교용 문자열 키로. 파이썬 frozenset 대용. */
const setKey = nums => [...nums].sort((a, b) => a - b).join(',');
const intersectSize = (aSet, bSet) => [...aSet].filter(n => bSet.has(n)).length;

/** 번호별 값을 평균 0 / 표준편차 1로 정규화. */
function standardize(values) {
  const xs = [...values.values()];
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const variance = xs.reduce((a, x) => a + (x - mean) ** 2, 0) / xs.length;
  const sd = Math.sqrt(variance);
  const out = new Map();
  for (const [k, v] of values) out.set(k, sd < 1e-9 ? 0.0 : (v - mean) / sd);
  return out;
}

/** 전략 가중치 + 과거 통계 + 민간속설로 번호별 기본 가중치를 만든다. */
export function baseWeights(strategy, stats, folklore = null, previous = null) {
  const zero = () => new Map(NUMBER_POOL.map(n => [n, 0.0]));
  let zFreq = zero(), zRecent = zero(), zGap = zero();
  if (stats.drawsUsed) {
    zFreq = standardize(new Map(NUMBER_POOL.map(n => [n, stats.frequency.get(n) || 0])));
    zRecent = standardize(new Map(NUMBER_POOL.map(n => [n, stats.recent.get(n) || 0])));
    zGap = standardize(new Map(NUMBER_POOL.map(n => [n, stats.gap.get(n) || 0])));
  }

  const weights = new Map();
  for (const n of NUMBER_POOL) {
    const score = strategy.wFrequency * zFreq.get(n)
      + strategy.wRecent * zRecent.get(n)
      + strategy.wGap * zGap.get(n)
      + (TWIN_NUMBERS.includes(n) ? strategy.wTwin : 0.0);
    weights.set(n, Math.max(MIN_WEIGHT, Math.exp(score * 0.6)));
  }

  for (const [n, factor] of multipliers(folklore, previous)) {
    // 기피수(factor 0)는 0으로 두고, 나머지는 하한을 지킨다.
    weights.set(n, factor === 0.0 ? 0.0 : Math.max(MIN_WEIGHT, weights.get(n) * factor));
  }
  if (![...weights.values()].some(w => w > 0)) {
    throw new Error('기피수가 너무 많아 뽑을 번호가 남지 않았습니다.');
  }
  return weights;
}

/** 이미 뽑힌 번호들과의 궁합수(동반 출현) 가중. */
function companionBoost(candidate, chosen, stats, strength) {
  if (!chosen.length || !stats.pairs.size || strength === 0) return 1.0;
  const counts = chosen.map(c => stats.pairs.get(pairKey(candidate, c)) || 0);
  const avg = counts.reduce((a, b) => a + b, 0) / counts.length;
  const expected = stats.drawsUsed ? stats.drawsUsed * (5 / 44) * (6 / 45) : 0;
  if (expected <= 0) return 1.0;
  return Math.max(MIN_WEIGHT, Math.exp((strength * 0.5 * (avg - expected)) / expected));
}

/** 비복원 가중 추출. 한 개 뽑을 때마다 궁합수 가중을 다시 계산한다. */
function weightedSample(pool, k, weights, stats, strategy, chosen, rng) {
  const remaining = [...pool];
  const picked = [];
  for (let i = 0; i < k && remaining.length; i++) {
    const ws = remaining.map(n =>
      weights.get(n) * companionBoost(n, [...chosen, ...picked], stats, strategy.wCompanion));
    const idx = rng.weightedIndex(ws);
    picked.push(remaining[idx]);
    remaining.splice(idx, 1);
  }
  return picked;
}

/** 전략이 요구하는 고정 번호(이월수 / 직전 보너스볼)를 정한다. */
function forcedNumbers(strategy, previous, weights, stats, rng) {
  const forced = [];
  if (!previous) return forced;
  if (strategy.usePrevBonus) forced.push(previous.bonus);
  if (strategy.carryoverTarget > 0) {
    const pool = previous.numbers.filter(n => !forced.includes(n));
    forced.push(...weightedSample(
      pool, Math.min(strategy.carryoverTarget, pool.length), weights, stats, strategy, forced, rng));
  }
  return forced;
}

function pickBonus(numbers, weights, rng) {
  const chosen = new Set(numbers);
  const pool = NUMBER_POOL.filter(n => !chosen.has(n));
  const ws = pool.map(n => weights.get(n));
  if (ws.reduce((a, b) => a + b, 0) <= 0) return rng.choice(pool);   // 기피수로 후보가 다 0이면 균등
  return rng.weighted(pool, ws);
}

/**
 * 한 줄을 만든다.
 *
 * 1) 가중 추첨으로 규칙을 통과하는 후보를 candidates개 모은다 (못 모으면 규칙 완화).
 * 2) 실데이터 경험분포(emp)가 있으면 전형성 점수로 소프트맥스 선택한다.
 *    temperature 가 낮을수록 가장 흔한 모양을, 높을수록 다양하게 고른다.
 * 3) 이미 뽑힌 줄과 maxOverlap개 넘게 겹치는 후보는 버린다.
 */
export function generateLine(strategy, stats, options = {}) {
  const {
    previous = null, rng = createRng(), exclude = [], bannedSets = [],
    maxAttempts = 4000, folklore = null, emp = null, reference = [],
    temperature = 1.0, maxOverlap = 3, rulesOverride = null,
    scoreWeights = defaultWeights(),
  } = options;
  let { candidates = 40 } = options;

  const weights = baseWeights(strategy, stats, folklore, previous);
  const prevNumbers = previous ? previous.numbers : [];
  const excludedSet = new Set([...exclude, ...(folklore ? folkloreExcluded(folklore) : [])]);
  const banned = bannedSets.map(s => new Set(s));
  const bannedKeys = new Set(bannedSets.map(setKey));
  const baseRules = rulesOverride || strategy.rules;
  const found = [];                 // {numbers, profile, step, attempt}
  const seen = new Set();
  if (emp === null) candidates = 1;  // 점수화할 근거가 없으면 첫 통과 후보를 그대로 쓴다

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const step = Math.floor(attempt / Math.max(1, Math.floor(maxAttempts / 6)));  // 실패가 쌓이면 완화
    let rules = step === 0 ? baseRules : relaxed(baseRules, step);
    // 직전 회차를 모르면 이월수 조건은 의미가 없다.
    if (!previous) rules = { ...rules, carryoverRange: [0, PICK] };

    let forced = forcedNumbers(strategy, previous, weights, stats, rng)
      .filter(n => !excludedSet.has(n));
    if (forced.length > PICK) forced = forced.slice(0, PICK);
    const pool = NUMBER_POOL.filter(n => !forced.includes(n) && !excludedSet.has(n));
    const rest = weightedSample(pool, PICK - forced.length, weights, stats, strategy, forced, rng);
    const nums = [...forced, ...rest].sort((a, b) => a - b);
    const key = setKey(nums);
    if (nums.length < PICK || bannedKeys.has(key) || seen.has(key)) continue;

    const overlapLimit = step < 3 ? maxOverlap : PICK;
    const numSet = new Set(nums);
    if (banned.some(b => intersectSize(numSet, b) > overlapLimit)) continue;
    if (!accepts(folklore, nums, step >= 3)) continue;

    const verdict = check(nums, rules, prevNumbers);
    if (!verdict.ok) continue;
    seen.add(key);
    found.push({ numbers: nums, profile: verdict.profile, step, attempt });
    if (found.length >= candidates) break;
  }

  if (!found.length) {
    throw new Error(`[${strategy.name}] 조건을 만족하는 조합을 찾지 못했습니다. 규칙을 완화하세요.`);
  }

  // ---- 전형성으로 선택 ----
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
    bonus: pickBonus(pickOne.numbers, weights, rng),
    profile: pickOne.profile,
    relaxedStep: pickOne.step,
    attempts: pickOne.attempt,
    luck: luckScore(folklore, pickOne.numbers, previous),
    omens: luckTags(folklore, pickOne.numbers, previous),
    typicality: score,
    percentile: emp ? typicalityPercentile(score, reference) : 50.0,
    poolSize: found.length,
  };
}

/**
 * 서로 다른 전략으로 lines줄을 뽑는다. 줄끼리 조합이 겹치지 않게 한다.
 *
 * rulesOverride 를 주면(예: model.calibrate 결과) 전략별 규칙 대신 그것을 쓰되,
 * 이월수 범위만은 전략이 요구하는 값을 유지한다.
 */
export function recommend(stats, options = {}) {
  const {
    previous = null, strategies = DEFAULT_STRATEGIES, lines = 5, seed = null,
    exclude = [], folklore = null, emp = null, reference = [], candidates = 40,
    temperature = 1.0, maxOverlap = 3, rulesOverride = null,
    scoreWeights = defaultWeights(),
  } = options;

  const rng = createRng(seed);
  const out = [];
  const used = [];
  for (let i = 0; i < lines; i++) {
    const strategy = strategies[i % strategies.length];
    const rules = rulesOverride
      ? { ...rulesOverride, carryoverRange: strategy.rules.carryoverRange }
      : null;
    const line = generateLine(strategy, stats, {
      previous, rng, exclude, bannedSets: used, folklore, emp, reference,
      candidates, temperature, maxOverlap, rulesOverride: rules, scoreWeights,
    });
    used.push(line.numbers);
    out.push(line);
  }
  return out;
}
