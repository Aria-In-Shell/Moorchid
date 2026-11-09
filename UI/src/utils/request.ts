/**
 * request.ts — Axios-based API client.
 *
 * Reads `VITE_API_BASE_URL` from the build-time environment as the axios
 * baseURL. In dev mode this is typically `/api`, which is then proxied to
 * the FastAPI backend by `server.proxy` in vite.config.ts.
 *
 * Responses are intercepted so 401s trigger a global logout event (same
 * behavior as the fetch-based client in src/api/client.ts).
 *
 * Note: this project historically uses a fetch wrapper and `client.ts`
 * remains the active HTTP layer. This file is here as a thin axios
 * alternative for new code that prefers axios semantics.
 */
import axios from 'axios'

const rawBase = import.meta.env.VITE_API_BASE_URL as string | undefined

function resolveBaseUrl(): string {
  if (typeof rawBase === 'string' && rawBase.trim().length > 0) {
    // Strip trailing slashes; callers pass full paths like "/api/auth/register".
    return rawBase.trim().replace(/\/+$/, '')
  }
  if (import.meta.env.DEV) {
    // Dev default: same-origin so the Vite proxy can forward to FastAPI.
    return '/'
  }
  console.warn(
    '[Moorchid] VITE_API_BASE_URL is not set. ' +
    'Production API calls will not work — set VITE_API_BASE_URL in .env.production.',
  )
  return '/'
}

export const request = axios.create({
  baseURL: resolveBaseUrl(),
  timeout: 30_000,
})

// ─── Request interceptor: attach Bearer token from localStorage. ───────────────
request.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem('soulcontext_token')
    if (token) {
      config.headers = config.headers ?? {}
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    /* localStorage may be unavailable in some test environments */
  }
  return config
})

// ─── Response interceptor: handle 401 and surface user-friendly errors. ───────
request.interceptors.response.use(
  (response) => response,
  (error) => {
    // 401 — token expired / invalid. Clear and broadcast a logout event.
    if (error?.response?.status === 401) {
      try {
        localStorage.removeItem('soulcontext_token')
      } catch {
        /* ignore */
      }
      window.dispatchEvent(new CustomEvent('soulcontext:auth:logout'))
    }

    // Normalize the error message so callers can show useful UI.
    const detail = error?.response?.data?.detail
    const message = typeof detail === 'string' ? detail : error?.message ?? 'Network error'
    // eslint-disable-next-line no-console
    console.error('[Moorchid request]', message)

    return Promise.reject(new Error(message))
  },
)

export default request
