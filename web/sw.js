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
const SHELL_FILES = [
  './', './index.html', './privacy.html', './manifest.webmanifest',
  './icon.svg', './icon-192.png', './icon-512.png',
  './src/engine.js', './src/storage.js', './src/dhlottery.js', './src/generator.js',
  './src/model.js', './src/stats.js', './src/metrics.js', './src/filters.js',
  './src/folklore.js', './src/fortune.js', './src/explain.js', './src/grade.js',
  './src/qr.js', './src/rng.js', './src/strategies.js', './src/backtest.js',
  './src/stores.js',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL)
      .then(c => c.addAll(SHELL_FILES))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())     // 일부 파일이 없어도 설치는 진행
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;    // 동행복권·카카오는 그대로 통과

  // 회차·배출점 데이터: 네트워크 우선 (주간 갱신이 재방문자에게 바로 닿아야 한다)
  if (url.pathname.endsWith('/data/draws.json') || url.pathname.endsWith('/data/stores.json')) {
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

  // 나머지: 캐시 우선
  event.respondWith(
    caches.match(request).then(hit => hit || fetch(request).then(res => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(SHELL).then(c => c.put(request, copy));
      }
      return res;
    }))
  );
});
