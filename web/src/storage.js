/** 프로필·내 번호·설정 저장소. 브라우저 localStorage 에만 남고 서버로 가지 않는다.
 *
 * localStorage 를 못 쓰는 환경(사파리 프라이빗, 테스트)에서도 죽지 않게 메모리로 물러선다.
 */
const PREFIX = 'lottoracle.';
const MAX_PICKS = 200;

/** localStorage 흉내를 내는 메모리 백엔드. */
function memoryBackend() {
  const map = new Map();
  return {
    getItem: k => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: k => map.delete(k),
  };
}

function detectBackend() {
  try {
    const ls = globalThis.localStorage;
    if (!ls) return memoryBackend();
    const probe = `${PREFIX}__probe`;
    ls.setItem(probe, '1');
    ls.removeItem(probe);
    return ls;
  } catch {
    return memoryBackend();      // 저장이 막힌 브라우저
  }
}

export function createStorage(backend = null) {
  const store = backend || detectBackend();

  const read = (key, fallback) => {
    try {
      const raw = store.getItem(PREFIX + key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;           // 손상된 값은 없는 것으로 본다
    }
  };
  const write = (key, value) => {
    try {
      store.setItem(PREFIX + key, JSON.stringify(value));
      return true;
    } catch {
      return false;              // 용량 초과 등
    }
  };
  const drop = key => {
    try { store.removeItem(PREFIX + key); } catch { /* 무시 */ }
  };

  return {
    // ---- 프로필
    loadProfile: () => read('profile', null),
    saveProfile: p => write('profile', p),
    clearProfile: () => drop('profile'),

    // ---- 내 번호
    listPicks() {
      const raw = read('picks', []);
      return Array.isArray(raw) ? raw : [];
    },
    addPick(lines, targetDraw, note = '') {
      const clean = lines.map(row => {
        const nums = [...row].map(Number).sort((a, b) => a - b);
        if (nums.length !== 6 || new Set(nums).size !== 6
          || nums.some(n => !Number.isInteger(n) || n < 1 || n > 45)) {
          throw new Error(`조합은 1~45 사이 서로 다른 번호 6개여야 합니다: ${[...row].join(', ')}`);
        }
        return nums;
      });
      if (!clean.length) throw new Error('저장할 조합이 없습니다.');
      if (clean.length > 20) throw new Error('한 번에 최대 20줄까지 저장할 수 있습니다.');
      const record = {
        id: Math.random().toString(36).slice(2, 12),
        savedAt: new Date().toISOString().slice(0, 19),
        targetDraw: Number(targetDraw),
        lines: clean,
        note: String(note || '').slice(0, 60),
      };
      const picks = [...this.listPicks(), record].slice(-MAX_PICKS);
      write('picks', picks);
      return record;
    },
    deletePick(id) {
      const picks = this.listPicks();
      const kept = picks.filter(p => p.id !== id);
      if (kept.length === picks.length) return false;
      write('picks', kept);
      return true;
    },

    // ---- 설정
    loadSettings() {
      const raw = read('settings', {});
      return raw && typeof raw === 'object' ? raw : {};
    },
    saveSettings(patch) {
      const allowed = ['autoRefresh', 'lastCheckedAt'];
      const current = this.loadSettings();
      for (const [k, v] of Object.entries(patch)) {
        if (!allowed.includes(k)) continue;
        if (v === null || v === undefined || v === '') delete current[k];
        else current[k] = v;
      }
      write('settings', current);
      return current;
    },

    // ---- 회차 캐시 (동행복권에서 새로 받은 회차를 다음 방문까지 들고 있는다)
    loadDrawCache: () => read('draws', null),
    saveDrawCache: draws => write('draws', draws),
    clearAll() {
      for (const k of ['profile', 'picks', 'settings', 'draws']) drop(k);
    },
  };
}
