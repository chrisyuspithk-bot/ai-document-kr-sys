'use client';

import { useSession } from 'next-auth/react';

/**
 * Access token for authenticated API calls. Auth lives in the NextAuth
 * session (JWT cookie), so client pages must read it from useSession()
 * rather than localStorage.
 */
export function useApiToken(): string | null {
  const { data: session } = useSession();
  return session?.accessToken ?? null;
}

/**
 * Authenticated fetch for client components. Uses a relative /api/v1 path
 * so Next.js rewrites proxy the request to the backend (works from any
 * public origin, unlike a hard-coded localhost base URL).
 */
export async function apiFetch(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(path, { ...init, headers });
}

export async function apiFetchJson<T = unknown>(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<T> {
  const res = await apiFetch(path, token, init);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
