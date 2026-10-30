/** 일본 로또 화면 — 번호 추천 · 내 번호 · 통계.
 *
 * index.html 은 상단 스위치가 '일본 로또' 로 처음 바뀔 때 이 모듈을 불러온다
 * (한국 로또만 쓰는 사람에게는 내려가지 않는다). 한국 화면의 함수·DOM 은 건드리지 않고,
 * 자기 몫의 섹션(#tab-jp-recommend · -picks · -stats · -draws · -shops) 안만 그린다.
 *
 * 구매 대행·온라인 구매 링크는 넣지 않는다. 회차 탭은 등수별 당첨금을 보여 주지만
 * (집계 사이트 두 곳이 일치한 값), 내 번호는 '맞은 개수' 만 세고 등수는 공식 발표로 안내한다.
 */
import { GAMES, GAME_KEYS, RANK_MATCH } from './games.js';
import { createJpEngine } from './engine.js';
import { strategies as allStrategies } from './strategies.js';
import { AREAS, JAPAN, MAPS_EMBED_KEY, OFFICIAL_MAP, appUrl, embedUrl, inJapan, placeOf } from './shops.js';

const WEEKDAY = ['월', '화', '수', '목', '금', '토', '일'];
const weekdayOf = iso => WEEKDAY[(new Date(`${iso}T00:00:00Z`).getUTCDay() + 6) % 7];
const dayLabel = iso => `${iso.slice(5).replace('-', '/')} ${weekdayOf(iso)}`;

// 1등 확률 = 1 / C(pool, pick)
const ODDS = { loto6: '6,096,454', loto7: '10,295,472', miniloto: '169,911' };
const DRAW_DAYS = { loto6: '월·목', loto7: '금', miniloto: '화' };

export function createJpUi(ctx) {
  const { storage, $, el, esc, fmt, showErr, yieldToUI, setMeta } = ctx;
  const engines = new Map();       // 게임 → 엔진 (데이터는 처음 쓸 때 받는다)
  const loading = new Map();
  let game = GAMES[storage.loadSettings().jpGame] ? storage.loadSettings().jpGame : 'loto6';
  let built = false;
  let last = null;                 // 마지막 추천 결과 (저장용)
  let statsFor = null;
  let drawLimit = 30;

  // 서비스 워커 캐시에 예전 storage.js 가 남아 있으면 일본 번호 함수가 없다.
  // 그대로 부르면 'is not a function' 이 뜨므로, 새로고침하면 된다고 알려 준다.
  const STALE = '앱 파일이 아직 이전 버전입니다. 페이지를 새로고침한 뒤 다시 시도해 주세요.';
  const storageReady = () => typeof storage.addJpPick === 'function' && typeof storage.listJpPicks === 'function';

  async function engineOf(key) {
    if (engines.has(key)) return engines.get(key);
    if (!loading.has(key)) {
      loading.set(key, fetch(`./data/jp/${key}.json`)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
        .then(raw => { const e = createJpEngine(key, raw); engines.set(key, e); return e; })
        .catch(err => {
          loading.delete(key);
          throw new Error(`${GAMES[key].name} 당첨번호 데이터를 받지 못했습니다 (${err.message}). 연결을 확인하고 다시 눌러 주세요.`);
        }));
    }
    return loading.get(key);
  }

  const balls = (key, nums, hits = null, small = false) => {
    const H = new Set(hits || []);
    return nums.map(n => `<span class="ball jp g-${key}${small ? ' sm' : ''}${H.has(n) ? ' hit' : ''}">${n}</span>`).join('');
  };
  const bonusBalls = (key, nums, small = false) =>
    `<span class="plus">+</span>${nums.map(n => `<span class="ball jp g-${key} bonus${small ? ' sm' : ''}">${n}</span>`).join('')}`;

  const switcher = id => `<div class="gamesw" id="${id}" role="tablist">${GAME_KEYS.map(k => {
    const g = GAMES[k];
    return `<button type="button" data-game="${k}" class="g-${k}${k === game ? ' on' : ''}">
      <b>${g.name}</b><small>1~${g.pool} 중 ${g.pick}개</small><small>${DRAW_DAYS[k]} 추첨</small></button>`;
  }).join('')}</div>`;

  function markSwitchers() {
    document.querySelectorAll('.gamesw button').forEach(b => b.classList.toggle('on', b.dataset.game === game));
  }

  async function setGame(key) {
    if (!GAMES[key] || key === game) return;
    game = key;
    storage.saveSettings({ jpGame: key });
    markSwitchers();
    fillStrategies();
    $('#jp-max_overlap').value = Math.floor(GAMES[key].pick / 2);
    $('#jp-max_overlap').max = GAMES[key].pick;
    $('#jp-rec-results').innerHTML = '';
    $('#jp-rec-info').innerHTML = '';
    $('#jp-rec-actions').style.display = 'none';
    $('#jp-rec-foot').style.display = 'none';
    showErr('#jp-rec-error', null);
    last = null;
    await renderMeta();
    if ($('#tab-jp-stats').classList.contains('active')) loadStats();
    drawLimit = 30;
    if ($('#tab-jp-draws').classList.contains('active')) loadDraws();
  }

  function fillStrategies() {
    $('#jp-strategies').innerHTML = allStrategies(GAMES[game]).map(s =>
      `<div class="check"><input type="checkbox" value="${s.key}" title="${esc(s.concept)}"><span>${esc(s.name)} <small style="color:var(--muted)">${s.key}</small></span></div>`).join('');
  }

  // ------------------------------------------------------------ 화면 뼈대
  function build() {
    if (built) return;
    built = true;
    $('#tab-jp-recommend').innerHTML = `
      <div class="grid">
        <div class="panel">
          <h3>일본 로또 번호 추천</h3>
          ${switcher('jp-game-rec')}
          <div id="jp-profile-hint" class="softbox" style="display:none;margin:10px 0 0"></div>
          <div class="row">
            <div><label>줄 수</label><input type="number" id="jp-lines" value="5" min="1" max="10"></div>
            <div><label>시드 (비우면 매번 다름)</label><input type="number" id="jp-seed" placeholder="예: 20261016"></div>
          </div>
          <label>전략 (비우면 5종 순환)</label>
          <div id="jp-strategies"></div>
          <label>행운수 <small style="color:var(--muted)">— 뽑힐 확률만 올라갑니다 · 범위 밖 번호는 빠집니다</small></label>
          <input type="text" id="jp-lucky" placeholder="예: 7 13">
          <label>기피수 (완전 제외)</label><input type="text" id="jp-avoid" placeholder="예: 4">
          <div class="check"><input type="checkbox" id="jp-folklore" checked><span>속설 가중치 사용 (행운수·이웃수·쌍둥이수)</span></div>
          <div class="check"><input type="checkbox" id="jp-calibrate" checked><span>실데이터로 필터 자동 보정</span></div>
          <label>보정 범위 <b id="jp-coverage-v">80%</b> — 낮을수록 빡빡하게</label>
          <input type="range" id="jp-coverage" min="50" max="99" value="80">
          <label>선택 온도 <b id="jp-temperature-v">1.00</b> — 낮을수록 가장 흔한 모양만</label>
          <input type="range" id="jp-temperature" min="5" max="300" value="100">
          <div class="row">
            <div><label>줄당 후보 수</label><input type="number" id="jp-candidates" value="40" min="1" max="400"></div>
            <div><label>줄 간 최대 중복</label><input type="number" id="jp-max_overlap" value="${Math.floor(GAMES[game].pick / 2)}" min="0" max="${GAMES[game].pick}"></div>
          </div>
          <button class="primary" id="jp-run">추천 5줄 뽑기</button>
          <p class="kv" style="margin-top:10px;text-align:center">번호 추천은 무료입니다 · 회원가입 없음</p>
          <p class="kv" style="margin-top:12px">일본 로또는 보너스 숫자를 고르지 않습니다. 본숫자만 뽑습니다.
            표를 사는 것은 일본 현지 판매점에서 직접 해 주세요 — 이 사이트는 구매를 대신하거나 연결하지 않습니다.</p>
        </div>
        <div>
          <div id="jp-rec-info" class="kv" style="margin-bottom:10px"></div>
          <div id="jp-rec-actions" style="display:none;margin:0 0 12px"><button class="ghost" id="jp-save">이 조합을 내 번호로 저장</button> <span class="kv" id="jp-save-msg" style="display:inline"></span></div>
          <div id="jp-rec-error"></div>
          <div id="jp-rec-results"></div>
          <div id="jp-rec-foot" class="kv" style="display:none;margin-top:6px"></div>
        </div>
      </div>`;
    $('#tab-jp-picks').innerHTML = `
      <div class="panel">
        <h3>일본 로또 내 번호 <button class="ghost" id="jp-picks-reload" style="float:right">새로고침</button></h3>
        <p class="kv">일본 로또 추천에서 저장한 조합입니다. 한국 로또 번호와 따로 보관하고, 이 브라우저에만 저장합니다.
          목표 회차가 추첨되면 당첨번호와 맞은 개수를 보여 드립니다. 등수와 당첨금은 일본 공식 발표로 확인해 주세요.</p>
        <div id="jp-picks-error"></div>
        <div id="jp-picks-body"></div>
      </div>`;
    $('#tab-jp-stats').innerHTML = `
      <div class="panel" style="margin-bottom:16px">${switcher('jp-game-stats')}</div>
      <div id="jp-stats-body"></div>`;

    $('#tab-jp-draws').innerHTML = `
      <div class="panel" style="margin-bottom:16px">${switcher('jp-game-draws')}</div>
      <div class="panel">
        <h3>최근 회차 <span style="float:right"><button class="ghost" id="jp-draws-more">더 보기</button></span></h3>
        <div id="jp-draws-body"></div>
      </div>`;

    $('#tab-jp-shops').innerHTML = `
      <div class="grid">
        <div class="panel" id="jp-shop-controls">
          <h3>일본 복권 판매점 찾기</h3>
          <p class="kv" style="margin-top:-4px">일본에서는 '宝くじ売り場(다카라쿠지 우리바)' 간판이 붙은 곳에서 로또6·로또7·미니로또를 팝니다.</p>
          <button class="primary" id="jp-shop-locate" style="margin-top:6px">내 위치 주변 판매점</button>
          <div id="jp-shop-status" class="kv" style="margin-top:8px"></div>
          <label style="margin-top:14px">여행지에서 찾기</label>
          ${AREAS.map(a => `<div class="jp-areas"><span class="kv">${esc(a.city)}</span>${a.items.map(([name, lat, lng, ja]) =>
            `<button type="button" class="ghost" data-lat="${lat}" data-lng="${lng}" data-place="${esc(ja)}">${esc(name)}</button>`).join('')}</div>`).join('')}
          <p class="kv" style="margin-top:14px">위치는 지도를 띄우는 데만 쓰고 저장하지 않습니다. 브라우저가 구글 지도로 바로 보냅니다.
            <a href="${OFFICIAL_MAP}" target="_blank" rel="noopener" style="color:var(--accent)">공식 판매점 검색(일본어)</a></p>
        </div>
        <div id="jp-shop-mapwrap">
          <div id="jp-shop-map" class="jp-map"></div>
          <div id="jp-shop-foot" class="kv" style="margin-top:8px"></div>
        </div>
      </div>`;

    fillStrategies();
    $('#jp-shop-locate').addEventListener('click', locateShops);
    document.querySelectorAll('.jp-areas button').forEach(b => b.addEventListener('click', () => {
      showShops(+b.dataset.lat, +b.dataset.lng, b.textContent, b.dataset.place);
    }));
    document.querySelectorAll('.gamesw button').forEach(b =>
      b.addEventListener('click', () => setGame(b.dataset.game)));
    $('#jp-coverage').addEventListener('input', e => { $('#jp-coverage-v').textContent = e.target.value + '%'; });
    $('#jp-temperature').addEventListener('input', e => { $('#jp-temperature-v').textContent = (e.target.value / 100).toFixed(2); });
    $('#jp-run').addEventListener('click', runRecommend);
    $('#jp-save').addEventListener('click', savePicks);
    $('#jp-picks-reload').addEventListener('click', loadPicks);
    $('#jp-draws-more').addEventListener('click', () => { drawLimit += 30; loadDraws(); });
  }

  const options = () => ({
    lines: +$('#jp-lines').value, seed: $('#jp-seed').value,
    strategies: [...document.querySelectorAll('#jp-strategies input:checked')].map(i => i.value),
    lucky: $('#jp-lucky').value, avoid: $('#jp-avoid').value,
    folklore: $('#jp-folklore').checked, calibrate: $('#jp-calibrate').checked,
    coverage: +$('#jp-coverage').value / 100, temperature: +$('#jp-temperature').value / 100,
    candidates: +$('#jp-candidates').value, maxOverlap: +$('#jp-max_overlap').value,
  });

  // ------------------------------------------------------------ 추천
  async function runRecommend() {
    const btn = $('#jp-run');
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span>뽑는 중…';
    showErr('#jp-rec-error', null);
    $('#jp-rec-actions').style.display = 'none'; $('#jp-save-msg').textContent = '';
    $('#jp-save').disabled = false;
    const key = game;
    try {
      const engine = await engineOf(key);
      await yieldToUI();
      const r = engine.recommendPayload(options());
      if (key !== game) return;                 // 뽑는 사이에 게임을 바꿨다
      last = r;
      const info = [];
      if (r.previous) info.push(`${esc(r.game.name)} · 기준 ${r.previous.no}회 (${dayLabel(r.previous.date)}) → 목표 <b>${r.next.no}회</b> (${dayLabel(r.next.date)})`);
      info.push(`분석 ${fmt(r.drawsUsed)}회차`);
      if (r.seed != null) info.push(`시드 ${r.seed}`);
      if (r.lucky.length) info.push(`행운수 ${r.lucky.join('·')}`);
      if (r.rules) info.push(`보정 규칙: 합계 ${r.rules.sumRange.join('~')} · 홀수 ${r.rules.oddRange.join('~')} · 저구간 ${r.rules.lowRange.join('~')} · AC≥${r.rules.acMin} · 끝수합 ${r.rules.endSumRange.join('~')}`);
      $('#jp-rec-info').innerHTML = info.join('<br>');
      $('#jp-rec-results').innerHTML = r.lines.map(L => `
        <div class="card jp-card g-${key}">
          <div class="head"><div class="title"><span class="gchip">${esc(r.game.name)}</span>${L.index}조합 <small>${esc(L.strategyName)}</small></div>
            <div class="kv">전형성 상위 <b>${(100 - L.percentile).toFixed(0)}%</b>${L.relaxed ? ` · <span style="color:var(--warn)">규칙 ${L.relaxed}단계 완화</span>` : ''}</div></div>
          <div class="balls">${balls(key, L.numbers)}</div>
          <div class="note"><b>[분석 핵심]</b> ${esc(L.note)}</div>
          <div class="kv">전형성 백분위 ${L.percentile}% (후보 ${L.poolSize}개 중 선택)</div><div class="bar"><i style="width:${L.percentile}%"></i></div>
          <div class="kv" style="margin-top:8px">${esc(L.metrics)}</div>
          <div class="kv">${esc(L.zones)}</div>
        </div>`).join('');
      if (r.next) {
        $('#jp-rec-actions').style.display = '';
        $('#jp-save').textContent = `이 ${r.lines.length}줄을 내 번호로 저장 (${r.game.name} ${r.next.no}회)`;
      }
      $('#jp-rec-foot').textContent = `${r.game.name} 1등 확률은 어떤 조합이든 1/${ODDS[key]} · 잃어도 괜찮은 만큼만 · 상담 1336`;
      $('#jp-rec-foot').style.display = '';
    } catch (e) {
      showErr('#jp-rec-error', e);
    } finally {
      btn.disabled = false;
      btn.textContent = `추천 ${$('#jp-lines').value}줄 뽑기`;
    }
  }

  function savePicks() {
    if (!last || !last.next) return;
    if (!storageReady()) { $('#jp-save-msg').textContent = STALE; return; }
    const btn = $('#jp-save');
    btn.disabled = true;
    try {
      storage.addJpPick(last.game.key, last.lines.map(L => L.numbers), last.next.no, last.next.date, '추천');
      $('#jp-save-msg').innerHTML = '저장했습니다 → <a href="#" style="color:var(--accent)">내 번호</a>';
      $('#jp-save-msg a').addEventListener('click', e => { e.preventDefault(); ctx.goto('jp-picks'); });
    } catch (e) {
      $('#jp-save-msg').textContent = '저장 실패: ' + e.message;
      btn.disabled = false;
    }
  }

  // ------------------------------------------------------------ 내 번호
  async function loadPicks() {
    showErr('#jp-picks-error', null);
    const body = $('#jp-picks-body');
    if (!storageReady()) { showErr('#jp-picks-error', STALE); body.innerHTML = ''; return; }
    // 저장 순서의 역순(같은 초에 둘을 저장해도 나중 것이 위로), 그다음 저장 시각.
    const picks = storage.listJpPicks().reverse()
      .sort((a, b) => String(b.savedAt).localeCompare(a.savedAt));
    if (!picks.length) {
      body.innerHTML = '<p class="kv">아직 저장한 일본 로또 번호가 없습니다. 번호 추천에서 뽑은 뒤 "내 번호로 저장"을 누르세요.</p>';
      return;
    }
    // 저장된 게임의 데이터만 받는다. 못 받아도 번호는 보여 준다.
    const needed = [...new Set(picks.map(p => p.game))];
    const ready = new Map();
    await Promise.all(needed.map(k => engineOf(k).then(e => ready.set(k, e)).catch(() => null)));
    body.innerHTML = picks.map(p => {
      const g = GAMES[p.game];
      const engine = ready.get(p.game);
      const draw = engine ? engine.draws.find(d => d.no === p.targetDraw) : null;
      let badge, detail;
      if (draw) {
        const drawn = new Set(draw.numbers);
        const hits = p.lines.map(row => row.filter(n => drawn.has(n)));
        const best = Math.max(...hits.map(h => h.length));
        badge = `<span class="badge ${best >= 3 ? 'win' : 'lose'}">추첨 완료 · 최고 ${best}개</span>`;
        detail = `<div class="kv" style="margin:6px 0 2px">${draw.no}회 (${dayLabel(draw.date)}) 당첨번호</div>
          <div style="margin:0 0 8px">${balls(p.game, draw.numbers, null, true)}${bonusBalls(p.game, draw.bonus, true)}</div>` +
          p.lines.map((row, i) => `<div class="kv">${i + 1}줄 ${balls(p.game, row, hits[i], true)} ${hits[i].length}개</div>`).join('') +
          `<div class="caution">맞은 개수만 셉니다. 등수·당첨금은 일본 공식 발표(미즈호은행 · 다카라쿠지 공식 사이트)로 확인해 주세요.</div>`;
      } else {
        const when = p.targetDate ? dayLabel(p.targetDate) : '';
        badge = `<span class="badge wait">추첨 전${when ? ' · ' + when : ''}</span>`;
        detail = p.lines.map((row, i) => `<div class="kv">${i + 1}줄 ${balls(p.game, row, null, true)}</div>`).join('');
      }
      return `<div class="card jp-card g-${p.game}"><div class="head"><div class="title"><span class="gchip">${esc(g.name)}</span>${p.targetDraw}회 목표
          <small>${esc(p.savedAt.replace('T', ' '))} 저장${p.note ? ' · ' + esc(p.note) : ''}</small></div>
          <div>${badge} <button class="ghost" data-jpdel="${esc(p.id)}" title="삭제">✕</button></div></div>${detail}</div>`;
    }).join('');
    body.querySelectorAll('[data-jpdel]').forEach(b => b.addEventListener('click', () => {
      if (!confirm('이 기록을 삭제할까요?')) return;
      storage.deleteJpPick(b.dataset.jpdel);
      loadPicks();
    }));
  }

  // ------------------------------------------------------------ 회차
  const yen = n => `${fmt(n)}엔`;
  function prizeTable(key, d) {
    if (!d.prizes.length) return '<p class="kv">이 회차 당첨금은 아직 집계 중입니다. 보통 추첨 다음 날 아침까지 올라옵니다.</p>';
    return `<table><tr><th>등수</th><th>일치</th><th class="num">당첨 게임 수</th><th class="num">1게임당</th><th class="num">등수별 총액</th></tr>` +
      d.prizes.map(([w, a], i) => `<tr><td>${i + 1}등</td><td class="kv">${RANK_MATCH[key][i] || ''}</td>
        <td class="num">${fmt(w)}게임</td><td class="num">${w ? yen(a) : '<span class="kv">해당 없음</span>'}</td>
        <td class="num kv">${w ? yen(w * a) : '-'}</td></tr>`).join('') +
      (d.carryover > 0 ? `<tr><th colspan="4">다음 회차로 넘어가는 1등 이월금</th><td class="num">${yen(d.carryover)}</td></tr>` : '') +
      `</table>`;
  }

  async function loadDraws() {
    const key = game;
    const box = $('#jp-draws-body');
    if (!box.innerHTML) box.innerHTML = '<span class="spin"></span>불러오는 중…';
    try {
      const engine = await engineOf(key);
      if (key !== game) return;
      const rows = engine.drawsPayload(drawLimit);
      box.innerHTML = `<p class="kv">회차를 누르면 등수별 당첨금이 펼쳐집니다.</p><table><tr><th>회차</th><th>추첨일</th><th>당첨번호</th><th class="num">1등</th><th class="num">1게임당</th></tr>` +
        rows.map(d => {
          const [w, a] = d.prizes[0] || [-1, 0];
          return `<tr class="drawrow" data-no="${d.no}" style="cursor:pointer"><td>${d.no}회 ▾</td><td>${dayLabel(d.date)}</td>
            <td>${balls(key, d.numbers, null, true)}${bonusBalls(key, d.bonus, true)}</td>
            <td class="num">${w < 0 ? '-' : w ? fmt(w) + '게임' : '없음'}</td><td class="num">${w > 0 ? yen(a) : w === 0 ? '이월' : '-'}</td></tr>
            <tr class="drawdetail" data-detail="${d.no}" style="display:none"><td colspan="5">${prizeTable(key, d)}</td></tr>`;
        }).join('') + '</table>';
      box.querySelectorAll('.drawrow').forEach(tr => tr.addEventListener('click', () => {
        const row = box.querySelector(`[data-detail="${tr.dataset.no}"]`);
        const open = row.style.display !== 'none';
        box.querySelectorAll('.drawdetail').forEach(r => { r.style.display = 'none'; });
        row.style.display = open ? 'none' : '';
      }));
      $('#jp-draws-more').style.display = rows.length < engine.draws.length ? '' : 'none';
    } catch (e) {
      box.innerHTML = `<div class="err">${esc(e.message)}</div>`;
    }
  }

  // ------------------------------------------------------------ 통계
  async function loadStats() {
    const key = game;
    const box = $('#jp-stats-body');
    if (statsFor === key && box.innerHTML) return;
    box.innerHTML = '<span class="spin"></span>통계 계산 중…';
    try {
      const engine = await engineOf(key);
      await yieldToUI();
      if (key !== game) return;
      const s = engine.statsPayload(30, 0.8);
      statsFor = key;
      const g = s.game;
      const dist = (arr, label) => {
        const top = Math.max(...arr.map(x => x.ratio)) || 1;
        return `<div class="kv" style="margin-top:14px"><b>${label}</b></div><div class="dist">${arr.map(d =>
          `<div style="height:${Math.max(2, d.ratio / top * 70)}px"><em>${(d.ratio * 100).toFixed(0)}%</em><span>${d.key}</span></div>`).join('')}</div>`;
      };
      const maxF = Math.max(...s.frequency.map(f => f.count));
      const R = s.calibratedRules;
      const recent = engine.drawsPayload(10);
      box.innerHTML = `
        <div class="grid two">
          <div class="panel"><h3>${esc(g.name)} 평균치 (${s.firstNo}~${s.lastNo}회, ${fmt(s.drawsUsed)}회차)</h3>
            <table>
              <tr><th>당첨번호 합 평균</th><td class="num">${s.meanSum} <span class="kv">(이론 ${g.expectedSum})</span></td></tr>
              <tr><th>합계 80% 구간</th><td class="num">${s.sumRange80[0]} ~ ${s.sumRange80[1]}</td></tr>
              <tr><th>끝수합 평균</th><td class="num">${s.endSumMean}</td></tr>
              <tr><th>연속수 포함 비율</th><td class="num">${(s.consecutiveRatio * 100).toFixed(1)}%</td></tr>
              <tr><th>번호당 평균 출현</th><td class="num">${s.meanFrequency}회</td></tr>
              <tr><th>첫 추첨</th><td class="num">${s.firstDate}</td></tr>
            </table>
            ${dist(s.odd, '홀수 개수 분포')}${dist(s.low, `저구간(1~${Math.floor(g.pool / 2)}) 개수 분포`)}${dist(s.ac, 'AC값 분포')}${dist(s.carryover, '이월수(직전 회차 중복) 분포')}
          </div>
          <div class="panel"><h3>핫 / 콜드</h3>
            <div class="kv"><b>최근 ${s.recentWindow}회 다출현</b></div><div style="margin:6px 0 12px">${s.hot.map(([n, c]) => `<span class="ball sm jp g-${key}" title="${c}회">${n}</span>`).join('')}</div>
            <div class="kv"><b>장기 미출현</b></div><div style="margin:6px 0 12px">${s.cold.map(([n, gap]) => `<span class="ball sm jp g-${key}" title="${gap}회차째 미출현">${n}</span>`).join('')}</div>
            <div class="kv" style="margin-top:14px"><b>자동 보정 규칙 (coverage ${(s.coverage * 100).toFixed(0)}%)</b></div>
            <table>
              <tr><th>합계</th><td>${R.sumRange.join(' ~ ')}</td><th>홀수 개수</th><td>${R.oddRange.join(' ~ ')}</td></tr>
              <tr><th>저구간</th><td>${R.lowRange.join(' ~ ')}</td><th>AC 최소</th><td>${R.acMin}</td></tr>
              <tr><th>끝수합</th><td>${R.endSumRange.join(' ~ ')}</td><th>번호 폭 최소</th><td>${R.spreadMin}</td></tr>
              <tr><th>연속쌍 최대</th><td>${R.maxConsecutivePairs}</td><th>이월수</th><td>${R.carryoverRange.join(' ~ ')}</td></tr>
            </table>
          </div>
        </div>
        <div class="panel" style="margin-top:20px"><h3>최근 ${recent.length}회 당첨번호</h3>
          ${recent.map(d => `<div class="jp-draw"><div class="kv"><b>${d.no}회</b> ${dayLabel(d.date)}</div>
            <div>${balls(key, d.numbers, null, true)}${bonusBalls(key, d.bonus, true)}</div></div>`).join('')}
          <p class="kv" style="margin-top:8px">일본 당첨번호 집계 사이트 두 곳의 전체 이력을 라쿠텐 다카라쿠지 최근 결과와 맞춰 본 값입니다. 공식 발표는 미즈호은행입니다.</p>
        </div>
        <div class="panel" style="margin-top:20px"><h3>번호별 출현 횟수</h3>
          <p class="note">본숫자 기준 · 번호를 누르고 있으면 보너스·최근·미출현</p>
          <div class="freq">${s.frequency.map(f => `<div class="f" title="보너스 ${f.bonus}회 · 최근 ${s.recentWindow}회 중 ${f.recent}회 · ${f.gap}회차째 미출현"><span class="ball sm jp g-${key}">${f.n}</span><div class="bar"><i style="width:${f.count / maxF * 100}%"></i></div><span>${f.count}</span></div>`).join('')}</div>
        </div>`;
    } catch (e) {
      box.innerHTML = `<div class="err">${esc(e.message)}</div>`;
    }
  }

  // ------------------------------------------------------------ 복권방
  /** 지도를 띄운다. place 는 검색어에 붙일 일본어 지명 — 이게 있어야 주변 핀이 찍힌다. */
  function showShops(lat, lng, label, place = '', zoom = 15, scroll = true) {
    const where = esc(label);
    if (!MAPS_EMBED_KEY) {                       // 키가 없으면 구글 지도를 새 창으로
      window.open(appUrl(lat, lng, place, zoom), '_blank', 'noopener');
      return;
    }
    $('#jp-shop-map').innerHTML = `<iframe title="${where} 복권 판매점 지도" src="${embedUrl(lat, lng, place, zoom)}"
      referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe>`;
    $('#jp-shop-foot').innerHTML = (zoom <= JAPAN.zoom
      ? `일본 전체의 판매점 일부입니다. 위에서 <b>내 위치</b>나 동네를 고르면 그 주변을 찾습니다.`
      : `지도 가운데가 <b>${where}</b>입니다. 핀을 누르면 영업시간과 길찾기가 나옵니다. 핀이 안 보이면 지도를 조금 축소해 보세요.`)
      + ` · <a href="${appUrl(lat, lng, place, zoom)}" target="_blank" rel="noopener" style="color:var(--accent)">구글 지도 앱에서 열기</a>`;
    if (scroll && window.matchMedia('(max-width:900px)').matches) {
      $('#jp-shop-mapwrap').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  const showJapan = (scroll = false) => showShops(JAPAN.lat, JAPAN.lng, '일본 전체', '', JAPAN.zoom, scroll);

  function locateShops() {
    const st = $('#jp-shop-status');
    if (!navigator.geolocation) { st.textContent = '이 브라우저는 위치를 알려 주지 않습니다. 아래 동네 버튼을 써 주세요.'; return; }
    st.innerHTML = '<span class="spin"></span>위치를 확인하는 중…';
    navigator.geolocation.getCurrentPosition(async pos => {
      const { latitude: lat, longitude: lng } = pos.coords;
      if (!inJapan(lat, lng)) {
        st.textContent = '지금은 일본 밖에 계셔서 일본 전체 지도를 보여 드립니다. 여행 가실 동네를 아래에서 골라 보세요.';
        showJapan(true);
        return;
      }
      st.innerHTML = '<span class="spin"></span>주변 지명을 찾는 중…';
      const place = await placeOf(lat, lng);      // 東京都新宿区 같은 시·구 이름
      st.textContent = place ? `${place} 주변` : '';
      showShops(lat, lng, '지금 계신 곳', place);
    }, err => {
      st.textContent = err.code === 1
        ? '위치 권한이 꺼져 있습니다. 브라우저 설정에서 허용하거나 아래 동네 버튼을 써 주세요.'
        : '위치를 잡지 못했습니다. 잠시 뒤 다시 누르거나 아래 동네 버튼을 써 주세요.';
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 });
  }

  // ------------------------------------------------------------ 상단 최신 회차
  async function renderMeta() {
    const key = game;
    try {
      const engine = await engineOf(key);
      if (key !== game) return;
      const p = engine.previous;
      if (!p) { setMeta(`${GAMES[key].name} 데이터 없음`); return; }
      const narrow = window.matchMedia('(max-width:640px)').matches;
      const head = narrow
        ? `<b>${esc(GAMES[key].name)} ${p.no}회</b> <span class="kv" style="font-size:11.5px">${p.date.slice(5)}</span>`
        : `${esc(GAMES[key].name)} 최신 <b>${p.no}회</b> (${p.date})`;
      setMeta(`${head} ${balls(key, p.numbers, null, true)}${bonusBalls(key, p.bonus, true)}`);
    } catch (e) {
      setMeta(esc(e.message));
    }
  }

  return {
    /** 일본 모드로 들어올 때. */
    async activate() {
      build();
      await renderMeta();
    },
    renderMeta,
    /** 일본 탭이 열릴 때 index.html 의 goto 가 부른다. */
    onTab(name) {
      build();
      if (name === 'jp-picks') loadPicks();
      if (name === 'jp-stats') loadStats();
      if (name === 'jp-draws') loadDraws();
      // 복권방은 처음 열 때 일본 전체 지도부터. 탭을 안 여는 사람에게는 구글 지도를 부르지 않는다.
      if (name === 'jp-shops' && !$('#jp-shop-map iframe')) showJapan();
    },
    /** 운세의 '이 기운으로 번호 뽑기' — 오늘의 숫자를 행운수로 넣고 바로 뽑는다. */
    useFortune(lucky) {
      build();
      const g = GAMES[game];
      const inRange = lucky.filter(n => n >= 1 && n <= g.pool);
      $('#jp-lucky').value = inRange.join(' ');
      const hint = $('#jp-profile-hint');
      hint.style.display = '';
      hint.textContent = inRange.length
        ? `오늘의 숫자 중 ${g.name} 범위(1~${g.pool}) 안의 ${inRange.join('·')}을 행운수로 채웠습니다. 바꿔도 됩니다.`
        : `오늘의 숫자가 모두 ${g.name} 범위(1~${g.pool}) 밖이라 행운수 없이 뽑습니다.`;
      $('#jp-run').click();
    },
    get game() { return game; },
  };
}
