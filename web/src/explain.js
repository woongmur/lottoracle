/** 추천 한 줄에 '분석 핵심' 코멘트를 붙인다. */
import { colorSignature, neighborNumbers, sameEndingGroups, wishNumbers } from './folklore.js';
import { TWIN_NUMBERS, ZONE_BOUNDS } from './metrics.js';

export const ZONE_LABELS = ['한 자리', '10번대', '20번대', '30번대', '40번대'];

export function zonePhrase(numbers) {
  const parts = [];
  ZONE_BOUNDS.forEach(([lo, hi], i) => {
    const hit = numbers.filter(n => n >= lo && n <= hi);
    if (hit.length) parts.push(`${ZONE_LABELS[i]} ${hit.join('·')}`);
  });
  return parts.join(', ');
}

/** [분석 핵심] 문장을 조립한다. 사실 관계(어떤 규칙이 걸렸는지)만 담는다. */
export function analysisNote(line, previous = null, folklore = null) {
  const nums = line.numbers;
  const numSet = new Set(nums);
  const bits = [];

  if (previous) {
    const carry = previous.numbers.filter(n => numSet.has(n)).sort((a, b) => a - b);
    if (carry.length) {
      bits.push(`직전 ${previous.no}회차 당첨수 ${carry.join('·')}번을 이월수로 채포`);
    }
    if (numSet.has(previous.bonus)) {
      bits.push(`직전 보너스볼 ${previous.bonus}번을 징검다리로 연결`);
    }
    const neighbors = neighborNumbers(previous);
    const hitNeighbors = [...numSet].filter(n => neighbors.has(n)).sort((a, b) => a - b);
    if (hitNeighbors.length) bits.push(`이웃수 ${hitNeighbors.join('·')}번으로 파동 확장`);
    if (!carry.length) bits.push('이월수를 끊고 새 흐름으로 전환');
  }

  const twins = TWIN_NUMBERS.filter(n => numSet.has(n));
  if (twins.length) bits.push(`쌍둥이수 ${twins.join('·')}번을 축으로 배치`);

  const endings = sameEndingGroups(nums);
  if (endings.size) {
    bits.push(`동형수 ${[...endings.values()].map(g => g.join('·')).join(', ')} 라인을 융합`);
  }

  if (folklore && folklore.enabled) {
    const wish = new Set(wishNumbers(folklore));
    const hit = [...numSet].filter(n => wish.has(n)).sort((a, b) => a - b);
    if (hit.length) bits.push(`행운·꿈수 ${hit.join('·')}번을 고정`);
  }

  const p = line.profile;
  const fit = line.relaxedStep === 0 ? '평균치 안에 안착' : '완화된 기준으로 통과';
  bits.push(`합계 ${p.total}(평균 138)·홀짝 ${p.odd}:${p.even}·AC ${p.ac}로 ${fit}`);
  bits.push(`볼 색상 배분 ${colorSignature(nums)}`);
  return bits.join(', ') + '.';
}
