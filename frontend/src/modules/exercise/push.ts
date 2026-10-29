import { api } from '../core/api';

export async function enableExercisePush() {
  if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
    throw new Error('Notifications need HTTPS or localhost and a browser with Web Push support. On iPhone, install the app to your Home Screen first.');
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') throw new Error('Allow notifications in browser settings to enable reminders.');
  if (!await navigator.serviceWorker.getRegistration()) throw new Error('Use the installed app or a production build to enable notifications.');
  const registration = await navigator.serviceWorker.ready;
  const { public_key } = await api<{ public_key: string }>('/exercise/push/key');
  const decoded = atob(public_key.replace(/-/g, '+').replace(/_/g, '/'));
  const key = Uint8Array.from(decoded, character => character.charCodeAt(0));
  let subscription = await registration.pushManager.getSubscription();
  if (subscription) {
    const existing = subscription.options.applicationServerKey;
    if (existing && Array.from(new Uint8Array(existing)).join() !== Array.from(key).join()) {
      await subscription.unsubscribe(); subscription = null;
    }
  }
  subscription ??= await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
  await api('/exercise/push/subscribe', { method: 'POST', body: JSON.stringify(subscription.toJSON()) });
}

export async function disableExercisePush() {
  if (!('serviceWorker' in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration();
  const subscription = await registration?.pushManager?.getSubscription();
  if (!subscription) return;
  try {
    await api('/exercise/push/unsubscribe', { method: 'POST', body: JSON.stringify(subscription.toJSON()) });
  } finally {
    await subscription.unsubscribe();
  }
}
