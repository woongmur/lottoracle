/** 일본 로또 세 종류의 규칙표. 파이썬 lottoracle/jp/games.py 와 같다 (골든 데이터로 대조).
 *
 * 번호 범위·개수·보너스 개수·등수가 게임마다 다르다. 이 표 하나만 보고 움직이게 해서
 * '45' 나 '6' 같은 한국 로또 숫자가 일본 쪽 코드에 박히지 않게 한다.
 */

/** weekdays: 추첨 요일 (월=0 … 일=6, 파이썬 date.weekday() 와 같은 번호). */
export const GAMES = {
  loto6: { key: 'loto6', name: '로또6', nameJa: 'ロト6', pool: 43, pick: 6, bonus: 1, ranks: 5, weekdays: [0, 3], carryover: true },
  loto7: { key: 'loto7', name: '로또7', nameJa: 'ロト7', pool: 37, pick: 7, bonus: 2, ranks: 6, weekdays: [4], carryover: true },
  miniloto: { key: 'miniloto', name: '미니로또', nameJa: 'ミニロト', pool: 31, pick: 5, bonus: 1, ranks: 4, weekdays: [1], carryover: false },
};

export const GAME_KEYS = Object.keys(GAMES);

export function getGame(key) {
  const g = typeof key === 'string' ? GAMES[key] : key;
  if (!g || !GAMES[g.key]) throw new Error(`모르는 게임입니다: ${key} (가능: ${GAME_KEYS.join(', ')})`);
  return g;
}
