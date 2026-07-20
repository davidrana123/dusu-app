/* DuSu service worker — makes the app installable + caches the shell.
   Network-first for navigations (always try fresh HTML so deploys show up),
   falling back to cache when offline. WebSocket + API calls are never cached. */

const CACHE = "dusu-v1";
const SHELL = ["/", "/logo.png", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;                       // never cache POST/auth
  const url = new URL(req.url);
  if (url.pathname.startsWith("/ws") || url.pathname.startsWith("/auth")) return;

  // Navigations: network-first so a new deploy is picked up immediately.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put("/", copy)).catch(() => {});
        return res;
      }).catch(() => caches.match("/"))
    );
    return;
  }

  // Static assets: cache-first, then network (and store).
  event.respondWith(
    caches.match(req).then((hit) =>
      hit || fetch(req).then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      }).catch(() => hit)
    )
  );
});
