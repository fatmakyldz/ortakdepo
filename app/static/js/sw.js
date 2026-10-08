// Sezkar Muhasebe servis çalışanı.
// Bilerek az şey yapar: sayfalar ve veriler her zaman sunucudan gelir (muhasebe verisi
// önbellekten gösterilmez). Yalnızca yazı tipi, stil ve simgeler önbelleğe alınır;
// bağlantı yokken de "çevrimdışı" sayfası gösterilir.
const CACHE = "muhasebe-v1";
const OFFLINE = "/cevrimdisi";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.add(OFFLINE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE)));
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then((hit) => {
        if (hit) return hit;
        return fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(req, copy));
          }
          return res;
        });
      })
    );
  }
});
