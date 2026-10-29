import type { User } from '../../types';

let token = sessionStorage.getItem('access') || '';
let refreshPending: Promise<User | null> | null = null;

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function setToken(value: string) {
  token = value;
  if (value) sessionStorage.setItem('access', value);
  else sessionStorage.removeItem('access');
}

export async function restoreSession(): Promise<User | null> {
  async function fromCookie(): Promise<User | null> {
    try {
      const response = await fetch('/api/core/auth/refresh', { method: 'POST', credentials: 'same-origin' });
      if (!response.ok) return null;
      const data = await response.json();
      setToken(data.access_token);
      return data.user;
    } catch { return null; }
  }
  // Serialize cookie rotation across tabs as well as concurrent requests in this tab.
  if (!refreshPending) refreshPending = (
    typeof navigator !== 'undefined' && navigator.locks
      ? navigator.locks.request('daymark-refresh', fromCookie)
      : fromCookie()
  ).finally(() => { refreshPending = null; });
  return refreshPending;
}

export async function refresh(): Promise<boolean> {
  return !!(await restoreSession());
}

export async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (typeof init.body === 'string') headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...init, headers, credentials: 'same-origin' });
  if (response.status === 401 && retry && !path.startsWith('/core/auth/')) {
    if (await refresh()) return raw(path, init, false);
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/core/auth/')) window.dispatchEvent(new Event('auth-required'));
    const data = await response.json().catch(() => ({}));
    throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`);
  }
  return response;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  return (await raw(path, init)).json();
}

export async function authenticate(email: string, password: string): Promise<User> {
  const data = await api<{ access_token: string; user: User }>('/core/auth/login',
    { method: 'POST', body: JSON.stringify({ email, password }) });
  setToken(data.access_token);
  return data.user;
}
