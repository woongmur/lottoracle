/** 일본 로또 추천 한 줄의 '분석 핵심' 문장. 파이썬 lottoracle/jp/explain.py 와 같다.
 *
 * 한국판과 다른 점: 볼 색상 배분은 없다(일본 로또 공은 번호대별 색이 정해져 있지 않다).
 * 합계 비교 기준은 게임마다 다른 이론 기대값(로또6 132 · 로또7 133 · 미니로또 80)이다.
 */
import { sameEndingGroups } from '../folklore.js';
import { inPool, neighborNumbers } from './folklore.js';
import { ZONE_LABELS, expectedSum, profile, twinNumbers, zoneBounds } from './metrics.js';

const dots = nums => nums.join('·');
const asc = nums => [...nums].sort((a, b) => a - b);

export function zonePhrase(game, numbers) {
  const sorted = asc(numbers);
  const parts = [];
  zoneBounds(game).forEach(([lo, hi], i) => {
    const hit = sorted.filter(n => n >= lo && n <= hi);
    if (hit.length) parts.push(`${ZONE_LABELS[i]} ${dots(hit)}`);
  });
  return parts.join(', ');
}

export function analysisNote(game, numbers, relaxedStep, previous = null, wishes = null) {
  const nums = asc(numbers);
  const has = new Set(nums);
  const bits = [];

  if (previous) {
    const carry = asc(previous.numbers.filter(n => has.has(n)));
    if (carry.length) bits.push(`직전 ${previous.no}회 당첨수 ${dots(carry)}번을 이월수로 채포`);
    const bridge = asc(previous.bonus.filter(n => has.has(n)));
    if (bridge.length) bits.push(`직전 보너스 ${dots(bridge)}번을 징검다리로 연결`);
    const near = neighborNumbers(game, previous);
    const neighbors = nums.filter(n => near.has(n));
    if (neighbors.length) bits.push(`이웃수 ${dots(neighbors)}번으로 파동 확장`);
    if (!carry.length) bits.push('이월수를 끊고 새 흐름으로 전환');
  }

  const twins = twinNumbers(game).filter(n => has.has(n));
  if (twins.length) bits.push(`쌍둥이수 ${dots(twins)}번을 축으로 배치`);

  const endings = sameEndingGroups(nums);
  if (endings.size) bits.push(`동형수 ${[...endings.values()].map(dots).join(', ')} 라인을 융합`);

  if (wishes && wishes.enabled) {
    const lucky = new Set(inPool(game, wishes.lucky));
    const hit = nums.filter(n => lucky.has(n));
    if (hit.length) bits.push(`행운수 ${dots(hit)}번을 고정`);
  }

  const p = profile(game, nums, previous ? previous.numbers : []);
  const fit = relaxedStep === 0 ? '평균치 안에 안착' : '완화된 기준으로 통과';
  bits.push(`합계 ${p.total}(평균 ${expectedSum(game)})·홀짝 ${p.odd}:${p.even}·AC ${p.ac}로 ${fit}`);
  return bits.join(', ') + '.';
}
