/** 일본 로또 5줄을 서로 다른 성격으로 뽑기 위한 전략. 파이썬 lottoracle/jp/strategies.py 와 같다.
 *
 * 통계적 근거는 없다. 줄마다 다른 모양이 나오게 하는 장치다.
 */
import { RELAX_STEP, defaultRules } from './filters.js';
import { twinNumbers } from './metrics.js';

export const carryoverRules = game => ({ ...defaultRules(game), carryoverRange: [1, 3] });

export function aggressiveRules(game) {
  const r = defaultRules(game);
  const w = RELAX_STEP[game.key].sum;
  return {
    ...r,
    sumRange: [r.sumRange[0] - w, r.sumRange[1] + w],
    acMin: r.acMin + 1,
    endSumRange: [r.endSumRange[0] - 3, r.endSumRange[1] + 5],
    carryoverRange: [0, 0],
  };
}

const strategy = opts => ({
  wFrequency: 0.0, wRecent: 0.0, wGap: 0.0, wCompanion: 0.0, wTwin: 0.0,
  carryoverTarget: 0, usePrevBonus: false,
  ...opts,
});

export function strategies(game) {
  const twins = twinNumbers(game).join('·');
  return [
    strategy({
      key: 'balance', name: '안정형 밸런스',
      concept: '평균치 정중앙 조준 — 합계·홀짝·고저·구간을 모두 최빈값에 맞춘 기본형',
      wFrequency: 0.5, wRecent: 0.2, wCompanion: 0.5,
      rules: defaultRules(game),
    }),
    strategy({
      key: 'carryover', name: '이월수 채포형',
      concept: '직전 회차 당첨수 2개를 이월수로 채포하고 중심 구간으로 묶는 조합',
      wFrequency: 0.4, wRecent: 0.4, wCompanion: 0.7, carryoverTarget: 2,
      rules: carryoverRules(game),
    }),
    strategy({
      key: 'bridge', name: '징검다리 저격형',
      concept: `직전 보너스 숫자를 징검다리로 끌어오고 쌍둥이수(${twins})를 얹은 그물망`,
      wFrequency: 0.3, wRecent: 0.3, wCompanion: 0.6, wTwin: 1.2,
      carryoverTarget: 1, usePrevBonus: true,
      rules: carryoverRules(game),
    }),
    strategy({
      key: 'variant', name: '변칙 조준형',
      concept: '이월 파동 1개를 고정하고 장기 미출현수로 허리를 채운 변칙 조합',
      wFrequency: -0.2, wRecent: -0.3, wGap: 0.9, wCompanion: 0.3, carryoverTarget: 1,
      rules: carryoverRules(game),
    }),
    strategy({
      key: 'aggressive', name: '공격형 라인업',
      concept: '이월수를 완전히 끊고 장기 미출현·저빈도 번호로 구성한 롱샷',
      wFrequency: -0.5, wRecent: -0.6, wGap: 1.2, wCompanion: 0.2, carryoverTarget: 0,
      rules: aggressiveRules(game),
    }),
  ];
}

export function byKey(game, key) {
  const all = strategies(game);
  const found = all.find(s => s.key === key);
  if (!found) throw new Error(`알 수 없는 전략: ${key} (사용 가능: ${all.map(s => s.key).join(', ')})`);
  return found;
}
