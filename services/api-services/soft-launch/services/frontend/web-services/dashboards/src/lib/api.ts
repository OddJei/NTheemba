import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { getAccessToken, getRefreshToken, setTokens, clearTokens } from './auth';

interface ImportMetaEnv { VITE_API_URL?: string }
const meta = import.meta as unknown as { env?: ImportMetaEnv };
const BASE = (meta.env?.VITE_API_URL as string) || '';

const instance = axios.create({ baseURL: BASE, headers: { 'Content-Type': 'application/json' } });

let isRefreshing = false;
let refreshQueue: Array<{
  resolve: (token?: string) => void;
  reject: (err: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  refreshQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error);
    else resolve(token || undefined);
  });
  refreshQueue = [];
}

instance.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token && config.headers) config.headers['Authorization'] = `Bearer ${token}`;
  return config;
});

instance.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
  const original = error.config as AxiosRequestConfig & { _retry?: boolean };
  if (error.response?.status === 401 && !original._retry) {
      // attempt to refresh token with queue
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (original.headers && token) (original.headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
            return instance(original);
          })
          .catch((err) => Promise.reject(err));
      }

  original._retry = true;
      isRefreshing = true;
      const refreshToken = getRefreshToken();

      try {
        const resp = await axios.post(`${BASE}/auth/refresh`, { refreshToken }, { headers: { 'Content-Type': 'application/json' } });
        const data = resp.data;
        if (data?.accessToken) {
          setTokens({ accessToken: data.accessToken, refreshToken: data.refreshToken });
          processQueue(null, data.accessToken);
          if (original.headers) original.headers['Authorization'] = `Bearer ${data.accessToken}`;
          return instance(original);
        }
      } catch (err) {
        processQueue(err, null);
        clearTokens();
        if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('ntheemba:auth-expired'));
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export async function API(path: string, opts: RequestInit = {}) {
  const method = (opts.method || 'GET').toLowerCase() as AxiosRequestConfig['method'];
  // map fetch-like body to axios 'data'
  let data: unknown = undefined;
  const body = (opts as any).body as unknown | undefined;
  if (typeof body !== 'undefined') {
    if (typeof body === 'string') {
      try {
        data = JSON.parse(body);
      } catch {
        data = body;
      }
    } else {
      data = body;
    }
  }

  const headers = (opts.headers || {}) as Record<string, string>;

  const resp = await instance.request({ url: path, method, data, headers });
  return resp.data;
}

export default API;
