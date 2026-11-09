/**
 * auth.ts — JWT token storage in localStorage.
 *
 * Centralised so every API call can read the same source of truth, and the
 * 401 interceptor in client.ts has a single place to clear the token.
 */

const TOKEN_KEY = 'soulcontext.jwt'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    // SSR / private mode — localStorage may throw; treat as no token.
    return null
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token)
  } catch {
    /* storage full / disabled — best-effort */
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* ignore */
  }
}

export function isLoggedIn(): boolean {
  return getToken() !== null
}

/**
 * Best-effort decode of the JWT payload to extract the username (sub).
 * Does NOT verify the signature — this is purely for UI display; the backend
 * is the source of truth and will reject forged tokens with a 401.
 */
export function getUsernameFromToken(): string | null {
  const token = getToken()
  if (!token) return null
  const parts = token.split('.')
  if (parts.length !== 3) return null
  try {
    // base64url → base64
    const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = b64 + '==='.slice((b64.length + 3) % 4)
    const json = atob(padded)
    const payload = JSON.parse(json) as { sub?: string; exp?: number }
    if (typeof payload.exp === 'number' && payload.exp * 1000 < Date.now()) {
      return null
    }
    return payload.sub ?? null
  } catch {
    return null
  }
}

