self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open('medassist-v1').then(function (cache) {
      return cache.addAll([
        '/',
        '/index.html',
        '/manifest.json',
        '/public/icon-192.png',
        '/public/icon-512.png'
      ]);
    })
  );
});

self.addEventListener('fetch', function (e) {
  e.respondWith(
    caches.match(e.request).then(function (response) {
      return response || fetch(e.request);
    })
  );
});
