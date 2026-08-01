// Served by main.service_worker() so the cache name carries the build number.
// With a fixed name the old cache outlived every release: `activate` only
// deletes caches whose name differs from the current one, and the fetch
// handler answered from cache without ever revalidating, so an installed PWA
// kept serving the stylesheet it first downloaded.
const VERSION = "{{ app_version }}";
const CACHE = "ams-static-" + VERSION;
const ASSETS = [
  "/static/style.css?v=" + VERSION,
  "/static/app.js?v=" + VERSION,
  "/static/icon.svg",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || !url.pathname.startsWith("/static/")) return;
  // Serve the cached copy for speed, but always refresh it in the background so
  // a build that changes an asset without changing its URL still lands.
  e.respondWith(
    caches.match(e.request).then((hit) => {
      const live = fetch(e.request).then((resp) => {
        if (resp && resp.ok) {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return resp;
      }).catch(() => hit);
      return hit || live;
    }));
});
