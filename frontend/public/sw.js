// Only public app-shell files enter Cache Storage. Private data lives in user-keyed IndexedDB.
const CACHE = 'anti-rot-shell-v6';
const SHELL = ['/', '/index.html', '/manifest.webmanifest', '/anti-rot-logo.jpg', '/icon-192.png', '/icon-512.png'];
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data?.json() || {}; } catch {}
  event.waitUntil(self.registration.showNotification(data.title || 'Anti-Rot', {
    body: data.body || 'Exercise reminder', icon: '/icon-192.png', badge: '/icon-192.png',
    tag: 'anti-rot-exercise', data: { url: '/?view=exercise' },
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    if (windows.length) { await windows[0].navigate('/?view=exercise'); await windows[0].focus(); }
    else await self.clients.openWindow('/?view=exercise');
  })());
});
self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const html = await (await fetch('/index.html', { cache: 'reload' })).text();
    const assets = [...html.matchAll(/(?:src|href)="(\/assets\/[^\"]+)"/g)].map(match => match[1]);
    await cache.addAll([...SHELL, ...assets]);
  })());
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE).then(cache => cache.put('/index.html', copy)));
      }
      return response;
    }).catch(() => caches.match('/index.html')));
  } else if (url.pathname.startsWith('/assets/') || SHELL.includes(url.pathname)) {
    event.respondWith(caches.match(event.request).then(hit => hit || fetch(event.request).then(response => {
      if (response.ok) {
        const copy = response.clone();
        event.waitUntil(caches.open(CACHE).then(cache => cache.put(event.request, copy)));
      }
      return response;
    })));
  }
});
