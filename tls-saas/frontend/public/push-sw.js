/* Push notification service worker for TLS Appointment Checker */

self.addEventListener('push', function(event) {
  let data = { title: 'TLS Appointment Checker', body: 'New notification' };
  
  try {
    data = event.data ? event.data.json() : data;
  } catch (e) {
    data.body = event.data ? event.data.text() : 'New notification';
  }

  const options = {
    body: data.body || data.message || 'New notification',
    icon: '/icons/icon-192-white.png',
    badge: '/icons/icon-192-white.png',
    vibrate: [200, 100, 200],
    tag: data.tag || 'tls-notification',
    renotify: true,
    data: {
      url: data.url || '/',
    },
    actions: data.actions || [
      { action: 'open', title: 'Open App' },
    ],
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'TLS Appointment Checker', options)
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  
  const url = event.notification.data?.url || '/dashboard';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});

self.addEventListener('install', function(event) {
  self.skipWaiting();
});

self.addEventListener('activate', function(event) {
  event.waitUntil(self.clients.claim());
});
