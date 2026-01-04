const CACHE_NAME = "daily-goals-v1";

const STATIC_ASSETS = [
    "/",
    "/login",
    "/static/css/style.css",
    "/static/js/app.js",
    "/static/manifest.json"
];

// INSTALL
self.addEventListener("install", event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// ACTIVATE
self.addEventListener("activate", event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        )
    );
    self.clients.claim();
});

// FETCH
self.addEventListener("fetch", event => {
    const req = event.request;

    // ❗ Never cache API / POST requests
    if (req.method !== "GET" || req.url.includes("/task") || req.url.includes("/friend")) {
        return;
    }

    event.respondWith(
        caches.match(req).then(cached =>
            cached ||
            fetch(req).then(res => {
                // Cache only successful GETs
                if (res.status === 200) {
                    const copy = res.clone();
                    caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
                }
                return res;
            }).catch(() => cached)
        )
    );
});
