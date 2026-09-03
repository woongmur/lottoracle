/** 5줄을 서로 다른 성격으로 뽑기 위한 전략 정의.
 *
 * 커뮤니티에 도는 '로또 공식'(이월수 채포, 직전 보너스볼 징검다리, 쌍둥이수, 궁합수)을
 * 가중치로 옮겨 놓은 것이다. 통계적 근거는 없고, 줄마다 다른 모양이 나오게 하는 장치다.
 */
import { defaultRules } from './filters.js';

const balancedRules = () => defaultRules();
// 이월수를 강제로 넣는 전략은 이월수 상한을 풀어줘야 한다.
const carryoverRules = () => ({ ...defaultRules(), carryoverRange: [1, 3] });
// 공격형은 평균에서 벗어난 조합도 허용한다.
const aggressiveRules = () => ({
  ...defaultRules(), sumRange: [90, 190], acMin: 8, endSumRange: [12, 40], carryoverRange: [0, 0],
});

/** 전략 하나. 지정하지 않은 가중치는 0. */
const strategy = opts => ({
  wFrequency: 0.0,      // 장기 출현 빈도 가중 (+면 다출현수 선호)
  wRecent: 0.0,         // 최근 N회 출현 가중 (+면 '핫넘버')
  wGap: 0.0,            // 미출현 기간 가중 (+면 '콜드/장기미출현')
  wCompanion: 0.0,      // 이미 뽑힌 번호와의 궁합수 가중
  wTwin: 0.0,           // 쌍둥이수(11·22·33·44) 가중
  carryoverTarget: 0,   // 직전 회차 당첨번호에서 강제로 넣을 개수
  usePrevBonus: false,  // 직전 보너스볼을 '징검다리'로 고정
  ...opts,
});

export const DEFAULT_STRATEGIES = [
  strategy({
    key: 'balance',
    name: '안정형 밸런스',
    concept: '평균치 정중앙 조준 — 합계·홀짝·고저·구간을 모두 최빈값에 맞춘 기본형',
    wFrequency: 0.5, wRecent: 0.2, wCompanion: 0.5,
    rules: balancedRules(),
  }),
  strategy({
    key: 'carryover',
    name: '이월수 채포형',
    concept: '직전 회차 당첨수 2개를 이월수로 채포하고 중심 구간으로 묶는 조합',
    wFrequency: 0.4, wRecent: 0.4, wCompanion: 0.7, carryoverTarget: 2,
    rules: carryoverRules(),
  }),
  strategy({
    key: 'bridge',
    name: '징검다리 저격형',
    concept: '직전 보너스볼을 징검다리로 끌어오고 쌍둥이수(11·22·33·44)를 얹은 그물망',
    wFrequency: 0.3, wRecent: 0.3, wCompanion: 0.6, wTwin: 1.2,
    carryoverTarget: 1, usePrevBonus: true,
    rules: carryoverRules(),
  }),
  strategy({
    key: 'variant',
    name: '변칙 조준형',
    concept: '이월 파동 1개를 고정하고 장기 미출현수로 허리를 채운 변칙 조합',
    wFrequency: -0.2, wRecent: -0.3, wGap: 0.9, wCompanion: 0.3, carryoverTarget: 1,
    rules: carryoverRules(),
  }),
  strategy({
    key: 'aggressive',
    name: '공격형 라인업',
    concept: '이월수를 완전히 끊고 장기 미출현·저빈도 번호로 구성한 롱샷',
    wFrequency: -0.5, wRecent: -0.6, wGap: 1.2, wCompanion: 0.2, carryoverTarget: 0,
    rules: aggressiveRules(),
  }),
];

export function byKey(key) {
  const found = DEFAULT_STRATEGIES.find(s => s.key === key);
  if (!found) {
    throw new Error(`알 수 없는 전략: ${key} (사용 가능: ${DEFAULT_STRATEGIES.map(s => s.key).join(', ')})`);
  }
  return found;
}
