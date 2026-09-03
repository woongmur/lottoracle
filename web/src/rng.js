/** 시드 난수 — 같은 시드면 같은 결과가 나온다.
 *
 * 파이썬 random.Random 은 메르센 트위스터라 JS 에 같은 구현이 없다. 그래서 값 자체는
 * 파이썬판과 다르지만, 각각은 결정론적이라 기능은 같다. (web/README.md 참고)
 */

/** 문자열·숫자 무엇이든 32비트 시드로. FNV-1a 변형. */
export function hashSeed(value) {
  const text = String(value ?? '');
  let h = 2166136261 >>> 0;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

/** mulberry32 — 작고 빠르며 주기가 충분한 PRNG. */
export function createRng(seed = null) {
  let state = (seed === null || seed === undefined ? (Math.random() * 4294967296) >>> 0
    : hashSeed(seed)) >>> 0;

  /** [0, 1) 실수. */
  function random() {
    state = (state + 0x6D2B79F5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /** [0, n) 정수. */
  const int = n => Math.floor(random() * n);

  /** 목록에서 하나. 파이썬 random.choice. */
  const choice = seq => seq[int(seq.length)];

  /** 가중치대로 하나 뽑아 인덱스를 준다. 합이 0 이하면 균등. */
  function weightedIndex(weights) {
    const total = weights.reduce((a, b) => a + b, 0);
    if (!(total > 0)) return int(weights.length);
    let r = random() * total;
    for (let i = 0; i < weights.length; i++) {
      r -= weights[i];
      if (r <= 0) return i;
    }
    return weights.length - 1;
  }

  /** 가중치대로 하나. 파이썬 random.choices(seq, weights=..., k=1)[0]. */
  const weighted = (seq, weights) => seq[weightedIndex(weights)];

  /** 비복원 무작위 추출 k개. 파이썬 random.sample. */
  function sample(seq, k) {
    const pool = [...seq];
    const out = [];
    for (let i = 0; i < k && pool.length; i++) out.push(...pool.splice(int(pool.length), 1));
    return out;
  }

  return { random, int, choice, weighted, weightedIndex, sample };
}
