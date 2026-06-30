const CACHE_NAME = "friend-chat-v1";

const urlsToCache = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/icon-192.png",
    "/static/icon-512.png",
    "/static/line-icon.jpg",
    "/static/background.jpg"
];


self.addEventListener("install", (event) => {

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                return cache.addAll(urlsToCache);
            })
    );

});


self.addEventListener("fetch", (event) => {

    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                return response || fetch(event.request);
            })
    );

});