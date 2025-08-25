/* eslint-disable no-restricted-globals */

// Cache version - update this when you want to invalidate all caches
const CACHE_VERSION = 'v1';
const CACHE_PREFIX = 'auraconnect-customer';

// Cache names
const CACHES = {
  static: `${CACHE_PREFIX}-static-${CACHE_VERSION}`,
  dynamic: `${CACHE_PREFIX}-dynamic-${CACHE_VERSION}`,
  api: `${CACHE_PREFIX}-api-${CACHE_VERSION}`,
};

// Files to cache on install (app shell)
const STATIC_CACHE_URLS = [
  '/',
  '/index.html',
  '/static/css/main.css',
  '/static/js/bundle.js',
  '/manifest.json',
  '/favicon.ico',
];

// API endpoints that should NEVER be cached
const NO_CACHE_PATTERNS = [
  /\/api\/auth\//,
  /\/api\/customers\/profile/,
  /\/api\/orders\/\d+\/track/,
  /\/api\/payments\//,
  /\/api\/cart\//,
  /\/api\/checkout/,
];

// API endpoints suitable for caching with network-first strategy
const CACHE_API_PATTERNS = [
  /\/api\/menu\//,
  /\/api\/categories/,
  /\/api\/restaurants/,
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install');
  
  event.waitUntil(
    caches.open(CACHES.static)
      .then((cache) => {
        console.log('[ServiceWorker] Pre-caching app shell');
        return cache.addAll(STATIC_CACHE_URLS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate');
  
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName.startsWith(CACHE_PREFIX) && !Object.values(CACHES).includes(cacheName)) {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - implement caching strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip WebSocket connections
  if (url.protocol === 'ws:' || url.protocol === 'wss:') {
    return;
  }

  // Check if this URL should never be cached
  const shouldNotCache = NO_CACHE_PATTERNS.some(pattern => pattern.test(url.pathname));
  if (shouldNotCache) {
    event.respondWith(fetch(request));
    return;
  }

  // API requests - network first, fallback to cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // Static assets - cache first, fallback to network
  if (request.destination === 'image' || 
      request.destination === 'style' || 
      request.destination === 'script' ||
      request.destination === 'font') {
    event.respondWith(cacheFirstStrategy(request));
    return;
  }

  // HTML pages - network first for freshness
  if (request.mode === 'navigate' || request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstStrategy(request));
    return;
  }

  // Default - network first
  event.respondWith(networkFirstStrategy(request));
});

// Cache-first strategy
async function cacheFirstStrategy(request) {
  const cache = await caches.open(CACHES.static);
  const cachedResponse = await cache.match(request);
  
  if (cachedResponse) {
    // Return cached version and update cache in background
    fetchAndCache(request, cache);
    return cachedResponse;
  }
  
  // Not in cache, fetch from network
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('[ServiceWorker] Fetch failed:', error);
    // Return offline page if available
    return caches.match('/offline.html') || new Response('Offline', {
      status: 503,
      statusText: 'Service Unavailable',
    });
  }
}

// Network-first strategy
async function networkFirstStrategy(request) {
  const cache = await caches.open(CACHES.dynamic);
  
  try {
    const networkResponse = await fetch(request);
    
    // Cache successful responses
    if (networkResponse.ok) {
      // Check if this API endpoint should be cached
      const url = new URL(request.url);
      const shouldCacheAPI = CACHE_API_PATTERNS.some(pattern => pattern.test(url.pathname));
      
      if (shouldCacheAPI) {
        cache.put(request, networkResponse.clone());
      }
    }
    
    return networkResponse;
  } catch (error) {
    // Network failed, try cache
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      console.log('[ServiceWorker] Serving from cache due to network failure');
      return cachedResponse;
    }
    
    // Both network and cache failed
    console.error('[ServiceWorker] Network and cache failed:', error);
    return new Response(JSON.stringify({ 
      error: 'Offline', 
      message: 'No internet connection and no cached data available' 
    }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}

// Background fetch and cache update
async function fetchAndCache(request, cache) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      cache.put(request, networkResponse);
    }
  } catch (error) {
    // Silent fail - we already returned cached version
  }
}

// Listen for messages from the app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'CLEAR_CACHE') {
    event.waitUntil(
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName.startsWith(CACHE_PREFIX)) {
              return caches.delete(cacheName);
            }
          })
        );
      })
    );
  }
});

// Handle background sync for offline orders
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-orders') {
    event.waitUntil(syncOfflineOrders());
  }
});

async function syncOfflineOrders() {
  // This would sync any orders placed while offline
  console.log('[ServiceWorker] Syncing offline orders...');
  // Implementation would go here
}