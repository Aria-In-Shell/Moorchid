/**
 * authApi.ts — login / register endpoints.
 * On success, the returned token is stored in localStorage via setToken().
 */

import { buildApiUrl } from './client'
import { setToken } from './auth'

export interface RegisterBody {
  username: string
  password: string
}

export interface LoginBody {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
}

export interface UserResponse {
  id: number
  username: string
  created_at: string
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const url = buildApiUrl(path)
  let res: Response
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (networkErr) {
    // Surface the actual URL we tried so the user can tell at a glance
    // whether the request went to localhost (dev) or to the public
    // domain. `Failed to fetch` on mobile almost always means a wrong
    // host:port combination.
    throw new Error(
      `Network error reaching ${url}: ${
        networkErr instanceof Error ? networkErr.message : String(networkErr)
      }`,
    )
  }
  if (!res.ok) {
    let msg = `HTTP ${res.status} on ${url}`
    try {
      const data = (await res.json()) as { detail?: string }
      msg = data.detail ?? msg
    } catch {
      /* ignore parse errors */
    }
    throw new Error(msg)
  }
  return (await res.json()) as T
}

export async function register(body: RegisterBody): Promise<UserResponse> {
  return postJson<UserResponse>('/api/auth/register', body).catch((err) => {
    if (err instanceof Error && err.message.includes('409')) {
      return null as unknown as UserResponse
    }
    throw err
  })
}

export async function login(body: LoginBody): Promise<TokenResponse> {
  const token = await postJson<TokenResponse>('/api/auth/login', body)
  setToken(token.access_token)
  return token
}