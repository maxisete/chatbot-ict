// Versión de la caché: subirla solo si cambian los recursos de ASSETS.
const CACHE_NAME = "chatbot-ict-v2";
const ASSETS = [
  "/",
  "/static/icon.svg",
  "/static/manifest.json",
  "/static/marked-18.0.14.umd.js",
  "/static/purify-3.4.16.min.js"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Las consultas y el webhook de Telegram nunca pasan por la caché.
  if (event.request.method !== "GET" || url.pathname.startsWith("/consulta") || url.pathname.startsWith("/webhook")) {
    return;
  }
  // Página principal: red primero, para tener siempre la versión actual.
  // La copia guardada solo se usa si no hay conexión.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((resp) => {
          if (resp.ok) {
            const copia = resp.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put("/", copia));
          }
          return resp;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }
  // Iconos, manifest y librerías versionadas: caché primero.
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
