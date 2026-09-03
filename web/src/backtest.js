/** 백테스트 — 이 프로그램의 가장 정직한 부분.
 *
 * 과거 회차마다 '그 직전까지의 데이터'만 써서 추천을 만들고 실제 당첨번호와 맞춰 본다.
 * 결과는 순수 무작위 추첨과 구별되지 않아야 정상이고, 실제로 그렇다.
 */
import { grade, RANK_LABEL, RANK_ODDS, TICKET_PRICE } from './grade.js';
import { NUMBER_POOL, PICK } from './metrics.js';
import { createRng } from './rng.js';

/**
 * 마지막 rounds 회차를 대상으로, 각 회차 직전까지의 데이터로 추천해 채점한다.
 *
 * @param recommender (history, rng) => 조합 배열
 * @param onProgress  (done, total) => void — 오래 걸리므로 화면에 진행을 알린다
 */
export function run(draws, recommender, options = {}) {
  const {
    rounds = 52, linesPerRound = 5, seed = null, endNo = null,
    minHistory = 50, onProgress = null,
  } = options;

  let ordered = [...draws].sort((a, b) => a.no - b.no);
  if (endNo !== null) ordered = ordered.filter(d => d.no <= endNo);
  const targets = ordered.slice(-rounds);
  const rng = createRng(seed);

  const zeroRanks = () => ({ 0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0 });
  const result = {
    rounds: 0, linesPerRound,
    modelRanks: zeroRanks(), randomRanks: zeroRanks(),
    modelPrize: 0, randomPrize: 0,
    bestModel: [],                 // {no, rank, numbers}
  };

  const byIndex = new Map(ordered.map((d, i) => [d.no, i]));
  targets.forEach((target, i) => {
    const history = ordered.slice(0, byIndex.get(target.no));
    if (history.length < minHistory) return;
    result.rounds++;

    // 회차마다 새 난수기를 주어 재현 가능하게 한다 (파이썬과 같은 구조).
    const modelLines = recommender(history, createRng(rng.random())).slice(0, linesPerRound);
    for (const g of grade(modelLines, target).results) {
      result.modelRanks[g.rank]++;
      result.modelPrize += g.prize;
      if (g.rank) result.bestModel.push({ no: target.no, rank: g.rank, numbers: g.numbers });
    }

    const randomLines = Array.from({ length: linesPerRound }, () => rng.sample(NUMBER_POOL, PICK));
    for (const g of grade(randomLines, target).results) {
      result.randomRanks[g.rank]++;
      result.randomPrize += g.prize;
    }
    onProgress?.(i + 1, targets.length);
  });
  return result;
}

export const tickets = r => r.rounds * r.linesPerRound;
export const spent = r => tickets(r) * TICKET_PRICE;

/** 같은 장수를 무작위로 샀을 때 이론적으로 기대되는 등수별 횟수. */
export const expectedRanks = r =>
  Object.fromEntries(Object.entries(RANK_ODDS).map(([rank, p]) => [rank, tickets(r) * p]));

export function summaryRows(r) {
  const exp = expectedRanks(r);
  return [1, 2, 3, 4, 5].map(rank => ({
    rank: RANK_LABEL[rank],
    model: r.modelRanks[rank],
    random: r.randomRanks[rank],
    expected: Number(exp[rank].toFixed(2)),
  }));
}

/** 화면에 넘길 요약. 회수율은 투입 대비 당첨금. */
export function payload(r) {
  const total = spent(r);
  return {
    rounds: r.rounds,
    linesPerRound: r.linesPerRound,
    tickets: tickets(r),
    spent: total,
    rows: summaryRows(r),
    modelPrize: r.modelPrize,
    randomPrize: r.randomPrize,
    modelRoi: total ? Number((r.modelPrize / total).toFixed(4)) : 0,
    randomRoi: total ? Number((r.randomPrize / total).toFixed(4)) : 0,
    best: [...r.bestModel].sort((a, b) => a.rank - b.rank).slice(0, 10)
      .map(b => ({ no: b.no, rank: RANK_LABEL[b.rank], numbers: b.numbers })),
  };
}
