// www/sw.js

self.addEventListener('install', event => {
  console.log('Service Worker installing.');
});

self.addEventListener('fetch', event => {
  // Basic fetch handler
  event.respondWith(fetch(event.request));
});
