const CACHE_NAME = "taller-frenos-static-v3";
const STATIC_PATHS = ["/static/css/", "/static/js/", "/static/icons/"];

self.addEventListener("install", function (event) {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames
          .filter(function (cacheName) {
            return cacheName.startsWith("taller-frenos-static-") && cacheName !== CACHE_NAME;
          })
          .map(function (cacheName) {
            return caches.delete(cacheName);
          }),
      );
    }).then(function () {
      return self.clients.claim();
    }),
  );
});

self.addEventListener("fetch", function (event) {
  const requestUrl = new URL(event.request.url);
  const isStaticAsset = STATIC_PATHS.some(function (path) {
    return requestUrl.pathname.startsWith(path);
  });

  if (
    event.request.method !== "GET" ||
    requestUrl.origin !== self.location.origin ||
    !isStaticAsset
  ) {
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.match(event.request).then(function (cachedResponse) {
        if (cachedResponse) {
          return cachedResponse;
        }

        return fetch(event.request).then(function (response) {
          if (response.ok && response.type === "basic") {
            cache.put(event.request, response.clone());
          }
          return response;
        });
      });
    }),
  );
});
