self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open('medassist-cache-v1').then((cache) => {
            return cache.addAll([
                '/',
                '/index.html',
                '/script.js',
                '/public/icon-192.png',
                '/public/icon-512.png'
            ]);
        })
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Bypass caching for API calls
    if (url.pathname.startsWith('/ask')) {
        return; // Let it go directly to network
    }

    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});
