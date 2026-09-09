/* Service worker: cachea el "app shell" para uso offline en la bodega. */
var CACHE='stock-costanera-v2';
var SHELL=[
  './',
  './index.html',
  './manifest.webmanifest',
  './vendor/JsBarcode.all.min.js',
  './icons/icon-32.png',
  './icons/icon-180.png',
  './icons/icon-192.png',
  './icons/icon-512.png'
];
self.addEventListener('install', function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){ return c.addAll(SHELL); }).then(function(){ return self.skipWaiting(); }));
});
self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.map(function(k){ if(k!==CACHE) return caches.delete(k); }));
  }).then(function(){ return self.clients.claim(); }));
});
self.addEventListener('fetch', function(e){
  var req=e.request;
  if(req.method!=='GET') return;
  var url=new URL(req.url);
  // Imágenes de Falabella: red primero, sin cachear (cambian según stock/catálogo)
  if(url.hostname.indexOf('falabella.com')>=0) return;
  // App shell (mismo origen): cache-first con actualización en segundo plano
  if(url.origin===self.location.origin){
    e.respondWith(
      caches.match(req).then(function(hit){
        var net=fetch(req).then(function(res){
          if(res && res.status===200){ var copy=res.clone(); caches.open(CACHE).then(function(c){ c.put(req,copy); }); }
          return res;
        }).catch(function(){ return hit; });
        return hit || net;
      })
    );
  }
});
