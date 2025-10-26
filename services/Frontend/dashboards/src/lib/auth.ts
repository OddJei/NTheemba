interface ImportMetaEnv { VITE_API_URL?: string }
const meta = import.meta as unknown as { env?: ImportMetaEnv };
const BASE = (meta.env?.VITE_API_URL as string) || '';

export const ACCESS_KEY = 'ntheemba_access_token';
export const REFRESH_KEY = 'ntheemba_refresh_token';

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens({ accessToken, refreshToken }: { accessToken: string; refreshToken?: string }) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(ACCESS_KEY, accessToken);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
}

export function clearTokens() {
  if (typeof window === 'undefined') return;
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// Try to refresh access token using refresh token. Returns true when successful.
export async function refreshAccessToken(): Promise<boolean> {
  try {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;

    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken }),
    });

    if (!res.ok) return false;
    const data = await res.json();
    // Expecting { accessToken, refreshToken? }
    if (data?.accessToken) {
      setTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken });
      return true;
    }
    return false;
  } catch (err) {
    return false;
  }
}
