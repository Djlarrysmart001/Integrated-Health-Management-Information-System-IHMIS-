// IHMIS service worker
//
// Deliberately minimal. IHMIS is a live clinical system backed by a real
// database -- it should NOT work offline or serve cached/stale patient
// data, so this does not cache anything or intercept requests for
// offline use. Its only job is to exist and register a fetch listener,
// which is one of the browser's required criteria for "this site can be
// installed as an app" (the trigger PWABuilder and Android's install
// prompt both check for).
//
// If you ever want real offline support for something like the login
// page shell, that would be added deliberately here later -- not by
// default, since caching clinical data is a patient-safety risk.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Pass every request straight through to the network, unmodified.
  event.respondWith(fetch(event.request));
});