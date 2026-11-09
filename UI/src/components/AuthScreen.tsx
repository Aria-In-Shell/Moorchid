import { useState } from 'react'
import { login, register } from '../api/authApi'

interface AuthScreenProps {
  onLoggedIn: () => void
}

type Mode = 'login' | 'register'

export function AuthScreen({ onLoggedIn }: AuthScreenProps) {
  const [mode, setMode] = useState<Mode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (mode === 'register') {
        await register({ username, password })
      }
      await login({ username, password })
      onLoggedIn()
    } catch (err) {
      setError(err instanceof Error ? err.message : '登录失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0b0c0f] px-6">
      <svg className="pointer-events-none absolute inset-x-0 top-1/3 h-64 w-full opacity-80" viewBox="0 0 1200 240" fill="none">
        <defs>
          <linearGradient id="auth-ecg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#FB7185" />
            <stop offset="35%" stopColor="#818CF8" />
            <stop offset="65%" stopColor="#5EEAD4" />
            <stop offset="100%" stopColor="#F5C15A" />
          </linearGradient>
        </defs>
        <path
          d="M0 140 C 80 140, 120 80, 180 90 S 280 210, 340 150 S 460 40, 540 70 S 680 200, 760 130 S 900 20, 980 80 S 1100 180, 1200 120"
          stroke="url(#auth-ecg)"
          strokeWidth="2.4"
          strokeLinecap="round"
          opacity="0.35"
        />
        <path
          d="M0 140 C 80 140, 120 80, 180 90 S 280 210, 340 150 S 460 40, 540 70 S 680 200, 760 130 S 900 20, 980 80 S 1100 180, 1200 120"
          stroke="url(#auth-ecg)"
          strokeWidth="2.2"
          strokeLinecap="round"
          className="ecg-flow"
          opacity="0.95"
        />
      </svg>

      <div className="relative w-full max-w-md rounded-[32px] border border-white/8 bg-[#14161c]/90 p-10 backdrop-blur-xl">
        <p className="text-[11px] tracking-[0.28em] text-[#8b909a] uppercase">Moorchid</p>
        <h1 className="serif mt-3 text-4xl text-white">把日子轻轻写下</h1>
        <p className="mt-3 text-sm leading-7 text-[#8b909a]">
          每一次记录都会在画布上落下一个彩色节点，连成你的情绪兰花。
        </p>

        <div className="mt-8 flex gap-2 rounded-full bg-white/5 p-1">
          {(['login', 'register'] as Mode[]).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setMode(item)}
              className={`flex-1 rounded-full py-2 text-sm ${
                mode === item ? 'bg-white text-[#0b0c0f]' : 'text-[#8b909a]'
              }`}
            >
              {item === 'login' ? '登录' : '注册'}
            </button>
          ))}
        </div>

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="用户名"
            autoComplete="username"
            className="h-12 w-full rounded-2xl border border-white/8 bg-white/4 px-4 text-sm outline-none"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="密码"
            type="password"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            className="h-12 w-full rounded-2xl border border-white/8 bg-white/4 px-4 text-sm outline-none"
          />
          {error && <p className="text-xs text-[#fb7185]">{error}</p>}
          <button
            type="submit"
            disabled={busy || username.trim().length < 3 || password.length < 6}
            className="h-12 w-full rounded-2xl bg-white text-sm font-medium text-[#0b0c0f] disabled:opacity-40"
          >
            {busy ? '请稍候…' : mode === 'login' ? '进入画布' : '创建档案'}
          </button>
        </form>
      </div>
    </div>
  )
}
