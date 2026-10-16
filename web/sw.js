/** 서비스 워커 — 앱 껍데기와 회차 데이터를 캐시해 오프라인에서도 열리게 한다.
 *
 * 정적 파일은 캐시 우선(빠름), 회차 데이터는 네트워크 우선(최신 우선, 실패 시 캐시).
 * 동행복권 API 는 캐시하지 않는다.
 */
// __BUILD__ 는 배포할 때 커밋 해시로 바뀐다 (deploy.yml).
// 이 값이 안 바뀌면 캐시가 그대로라 배포해도 예전 화면이 계속 나온다.
const VERSION = 'v0.4.0-__BUILD__';
const SHELL = `shell-${VERSION}`;
const DATA = `data-${VERSION}`;
// 글꼴(fonts/)은 배포마다 바뀌지 않는다. 배포 판 이름을 붙이지 않고 따로 오래 둔다.
const FONTS = 'fonts-pretendard-1.3.9';
const SHELL_FILES = [
  './', './index.html', './privacy.html', './manifest.webmanifest',
  './icon.svg', './icon-192.png', './icon-512.png',
  './src/engine.js', './src/storage.js', './src/dhlottery.js', './src/generator.js',
  './src/model.js', './src/stats.js', './src/metrics.js', './src/filters.js',
  './src/folklore.js', './src/fortune.js', './src/explain.js', './src/grade.js',
  './src/qr.js', './src/rng.js', './src/strategies.js', './src/backtest.js',
  './src/stores.js', './src/sheet.js',
  './src/tzhistory.js', './src/solartime.js', './src/saju.js', './src/sipsin.js', './src/daeun.js',
];

/** 이 배포의 파일을 '새로' 받는다.
 *
 * 그냥 fetch 하면 브라우저 HTTP 캐시와 Cloudflare 가장자리 캐시(GitHub Pages 는
 * max-age=600)를 거친다. 배포 직후 10분 안에 설치되면 새 index.html 옆에 예전
 * storage.js 가 담기고, 캐시 우선이라 그 짝이 다음 배포까지 굳는다 — 실제로 일본
 * 화면이 예전 저장소를 불러 'addJpPick is not a function' 이 났다.
 * 주소에 배포 버전을 붙이면 가장자리 캐시를 비켜 가고, cache:'reload' 는 브라우저
 * 캐시를 비켜 간다. 담을 때는 원래 주소로 담아 페이지 요청과 맞춘다.
 */
function fresh(url) {
  const u = new URL(url, self.location.href);
  u.searchParams.set('v', VERSION);
  return fetch(u, { cache: 'reload' });
}

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const c = await caches.open(SHELL);
    // 하나가 실패해도 나머지는 담는다. 못 담은 파일은 처음 쓸 때 아래 fetch 처리기가 받는다.
    await Promise.all(SHELL_FILES.map(async path => {
      try {
        const res = await fresh(path);
        if (res.ok) await c.put(new URL(path, self.location.href), res);
      } catch { /* 오프라인 등 */ }
    }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== DATA && k !== FONTS).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;    // 동행복권·카카오는 그대로 통과

  // 회차·배출점 데이터: 네트워크 우선 (주간 갱신이 재방문자에게 바로 닿아야 한다)
  // 일본 로또(data/jp/*.json)도 같다. 일본 화면 모듈(src/jp/)은 아래 캐시 우선 길로
  // 처음 쓸 때 담긴다 — 한국 로또만 쓰는 사람에게까지 미리 내려보내지 않는다.
  if (url.pathname.endsWith('/data/draws.json') || url.pathname.endsWith('/data/stores.json')
    || url.pathname.includes('/data/jp/')) {
    event.respondWith(
      fetch(request)
        .then(res => {
          const copy = res.clone();
          caches.open(DATA).then(c => c.put(request, copy));
          return res;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  if (url.pathname.includes('/fonts/')) {
    event.respondWith(caches.match(request).then(hit => hit || fetch(request).then(res => {
      if (res.ok) { const copy = res.clone(); caches.open(FONTS).then(c => c.put(request, copy)); }
      return res;
    })));
    return;
  }

  // 나머지: 캐시 우선. 캐시에 없으면 이 배포 판을 새로 받아 담는다
  // (일본 화면 src/jp/ 처럼 처음 쓸 때 내려가는 파일도 같은 배포 것끼리 맞물리게).
  event.respondWith(
    caches.match(request).then(hit => hit || fresh(request.url).then(res => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(request, copy));
      }
      return res;
    }))
  );
});
