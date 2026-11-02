/** 일본 로또 당첨 확인 — 번호 한 줄이 몇 등인지, 그 회차 당첨금이 얼마인지.
 *
 * 등수 규칙은 다카라쿠지 공식 규칙 그대로다. 보너스는 사는 사람이 고르지 않고,
 * 본숫자 일치 개수가 같을 때 2등(로또7 은 6등도)을 가르는 데만 쓴다.
 * 로또7 의 '보너스' 는 보너스 두 개 중 하나 이상이면 된다.
 * 화면에 쓰는 일치 조건 글자는 games.js 의 RANK_MATCH (같은 순서).
 */
import { getGame } from './games.js';

/** 등수 순서대로 [본숫자 일치 개수, 보너스 최소 일치 개수]. 위에서부터 처음 맞는 것이 그 등수. */
export const RANK_RULES = {
  loto6: [[6, 0], [5, 1], [5, 0], [4, 0], [3, 0]],
  loto7: [[7, 0], [6, 1], [6, 0], [5, 0], [4, 0], [3, 1]],
  miniloto: [[5, 0], [4, 1], [4, 0], [3, 0]],
};

/** 한 줄의 번호가 이 게임에 맞는지. 틀리면 이유를, 맞으면 null. */
export function lineError(gameKey, line) {
  const g = getGame(gameKey);
  const nums = line.map(Number);
  if (nums.length !== g.pick) return `${g.pick}개를 넣어 주세요`;
  if (nums.some(n => !Number.isInteger(n) || n < 1 || n > g.pool)) return `1~${g.pool} 사이 숫자만 됩니다`;
  if (new Set(nums).size !== nums.length) return '같은 숫자가 두 번 있습니다';
  return null;
}

/** 등수 (0 은 낙첨). */
export function rankOf(gameKey, line, draw) {
  const win = new Set(draw.numbers);
  const bonus = new Set(draw.bonus);
  const hit = line.filter(n => win.has(n)).length;
  const bonusHit = line.filter(n => bonus.has(n)).length;
  const i = RANK_RULES[getGame(gameKey).key].findIndex(([h, b]) => hit === h && bonusHit >= b);
  return i + 1;
}

/** 여러 줄을 채점한다. draw.prizes 가 있으면 등수별 1게임당 금액을 붙인다.
 *  prize 는 낙첨 0, 당첨인데 금액을 모르면 null(집계 전), 아니면 엔. */
export function gradeLines(gameKey, draw, lines) {
  const win = new Set(draw.numbers);
  const bonus = new Set(draw.bonus);
  const results = lines.map(raw => {
    const numbers = raw.map(Number).sort((a, b) => a - b);
    const rank = rankOf(gameKey, numbers, draw);
    const row = rank && draw.prizes?.length ? draw.prizes[rank - 1] : null;
    return {
      numbers,
      hit: numbers.filter(n => win.has(n)),
      bonusHit: numbers.filter(n => bonus.has(n)),
      rank,
      // 집계상 그 등수 당첨자가 0 이면(입력한 번호가 실제로 산 표가 아닌 경우 등) 금액을 모른다.
      prize: rank === 0 ? 0 : row && row[0] > 0 ? row[1] : null,
    };
  });
  const best = results.reduce((m, r) => (r.rank && (!m || r.rank < m) ? r.rank : m), 0);
  const known = results.every(r => r.prize !== null);
  return { results, bestRank: best, totalPrize: results.reduce((s, r) => s + (r.prize || 0), 0), prizesKnown: known };
}
