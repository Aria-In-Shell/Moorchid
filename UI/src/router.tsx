/**
 * router.tsx — hash-mode router with auth guards.
 *
 * Routes
 * ------
 *  /login     — only when NOT logged in
 *  /          — main app shell (Journal / Chat / Poetry tabs)
 *
 * Guards
 * ------
 *  RequireAuth        — redirects to /login if no token
 *  RedirectIfLoggedIn — redirects to / if already logged in
 *
 * Why a window-level "loggedIn" mirrored into React context?
 *   The 401 interceptor in api/client.ts dispatches a native CustomEvent
 *   to kick the user out without coupling to a particular state library.
 *   We mirror that state into a small React context (AuthContext) so
 *   route components and the App shell can read it synchronously.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  HashRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom'
import { AUTH_LOGOUT_EVENT } from './api/client'
import { isLoggedIn } from './api/auth'
import { AuthScreen } from './components/AuthScreen'
import App from './App'

// ─── Auth context ──────────────────────────────────────────────────────────────
//
// Keep the field name `setLoggedIn` (matches every prior code path and
// every prior `useAuth()` alias). We deliberately DO NOT rename it to
// `setIsLoggedIn` / `login()` because that would only shift the
// "is not defined" error from one identifier to the next.

export interface AuthContextValue {
  /** Whether the user is currently logged in (JWT in localStorage). */
  loggedIn: boolean
  /** Flip the auth state. Calling `setLoggedIn(true)` is the single
   *  way to leave the login screen without a hard refresh. */
  setLoggedIn: (v: boolean) => void
  /** Clears the JWT and flips the state back to false. */
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Hook used by route components to read & mutate the auth state.
 * Throws if used outside `<AuthProvider>` so we fail fast in dev rather
 * than silently shipping a broken bundle.
 */
export function useAuthState(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuthState must be used within <AuthProvider>')
  }
  return ctx
}

/** Backwards-compatible alias used by older imports. */
export const useAuth = useAuthState

// ─── Provider ──────────────────────────────────────────────────────────────────

function AuthProvider({ children }: { children: ReactNode }) {
  // Seed from localStorage so a hard-refresh doesn't kick the user out.
  const [loggedIn, setLoggedInState] = useState<boolean>(() => isLoggedIn())

  // ── Auth-event listeners (registered once via useEffect) ──
  useEffect(() => {
    function handleLogout() {
      setLoggedInState(false)
    }
    function handleStorage(e: StorageEvent) {
      if (e.key === 'soulcontext.jwt') setLoggedInState(isLoggedIn())
    }
    window.addEventListener(AUTH_LOGOUT_EVENT, handleLogout)
    window.addEventListener('storage', handleStorage)
    return () => {
      window.removeEventListener(AUTH_LOGOUT_EVENT, handleLogout)
      window.removeEventListener('storage', handleStorage)
    }
  }, [])

  // Expose a single setter. Stable across renders so `useCallback`s
  // upstream don't need to re-bind.
  const setLoggedIn = useCallback((v: boolean) => {
    setLoggedInState(Boolean(v))
  }, [])

  const logout = useCallback(() => {
    setLoggedIn(false)
  }, [setLoggedIn])

  const value = useMemo<AuthContextValue>(
    () => ({ loggedIn, setLoggedIn, logout }),
    [loggedIn, setLoggedIn, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// ─── Guards ───────────────────────────────────────────────────────────────────

function RequireAuth() {
  const { loggedIn } = useAuthState()
  const location = useLocation()
  if (!loggedIn) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

function RedirectIfLoggedIn() {
  const { loggedIn } = useAuthState()
  if (loggedIn) return <Navigate to="/" replace />
  return <Outlet />
}

// ─── Login wrapper ─────────────────────────────────────────────────────────────
//
// Wraps AuthScreen so that on success we synchronously:
//   1) Flip the auth context (so guards let us through)
//   2) Call navigate() to leave /login
//
// The flip AND the navigate happen in the same event-loop turn, so we
// never depend on a downstream `useEffect` to fire. Defence in depth:
//   - AuthScreen ALREADY saved the JWT before calling onLoggedIn (see
//     api/authApi.ts login())
//   - We also flip the context immediately
//   - We also navigate immediately
//
// All three can fail in isolation; together they cover the lot.

function LoginRoute() {
  const { setLoggedIn } = useAuthState()
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  // Guard against StrictMode double-invoke: only the first call navigates.
  const navigatedRef = useRef(false)

  const handleLoggedIn = useCallback(() => {
    if (navigatedRef.current) return
    navigatedRef.current = true
    try {
      setLoggedIn(true)
    } catch (e) {
      // Should never happen — `setLoggedIn` is a useState setter — but
      // we surface it rather than swallow silently.
      console.error('[Auth] setLoggedIn threw:', e)
      return
    }
    // Always navigate, even if the state update is batched/deferred.
    navigate(from, { replace: true })
  }, [setLoggedIn, navigate, from])

  return <AuthScreen onLoggedIn={handleLoggedIn} />
}

// ─── App shell wrapper ─────────────────────────────────────────────────────────

function AppShell() {
  return <App />
}

// ─── Router ───────────────────────────────────────────────────────────────────

export function AppRouter() {
  return (
    <AuthProvider>
      <HashRouter>
        <Routes>
          <Route element={<RedirectIfLoggedIn />}>
            <Route path="/login" element={<LoginRoute />} />
          </Route>
          <Route element={<RequireAuth />}>
            <Route path="/" element={<AppShell />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </HashRouter>
    </AuthProvider>
  )
}