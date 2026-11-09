import { getUsernameFromToken } from '../../api/auth'
import type { AppView } from '../../types'

interface LeftNavProps {
  view: AppView
  panelOpen: boolean
  onView: (view: AppView) => void
  onTogglePanel: () => void
  onLogout: () => void
}

const ITEMS: Array<{ id: AppView; label: string; icon: string }> = [
  { id: 'canvas', label: '画布', icon: '∿' },
  { id: 'chat', label: '对话', icon: '◎' },
  { id: 'poetry', label: '诗篇', icon: '¶' },
]

export default function LeftNav({
  view,
  panelOpen,
  onView,
  onTogglePanel,
  onLogout,
}: LeftNavProps) {
  const username = getUsernameFromToken() ?? '访客'

  return (
    <aside className="flex h-full w-16 sm:w-[88px] shrink-0 flex-col items-center border-r border-white/6 bg-[#101218] py-6">
      <div className="serif text-2xl leading-none text-white">M</div>
      <p className="mt-2 text-[9px] tracking-[0.22em] text-[#8b909a]">MOOR</p>

      <nav className="mt-4 flex min-h-0 flex-1 overflow-y-auto flex-col gap-2">
        {ITEMS.map((item) => {
          const active = view === item.id
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => onView(item.id)}
              className={`flex h-16 w-16 flex-col items-center justify-center rounded-2xl text-[10px] tracking-[0.16em] transition ${
                active ? 'bg-white/8 text-white' : 'text-[#8b909a] hover:bg-white/4 hover:text-white'
              }`}
            >
              <span className="mb-1 text-lg leading-none">{item.icon}</span>
              {item.label}
            </button>
          )
        })}
        <button
          type="button"
          onClick={onTogglePanel}
          className={`mt-4 flex h-16 w-16 flex-col items-center justify-center rounded-2xl text-[10px] tracking-[0.16em] transition ${
            panelOpen ? 'bg-white/8 text-white' : 'text-[#8b909a] hover:bg-white/4 hover:text-white'
          }`}
        >
          <span className="mb-1 text-lg leading-none">{panelOpen ? '⟩' : '⟨'}</span>
          面板
        </button>
      </nav>

      <button type="button" onClick={onLogout} aria-label="退出登录"
        className="flex w-16 shrink-0 cursor-pointer flex-col items-center gap-1 rounded-xl py-2 text-xs text-[#b8bdc8] hover:bg-white/10 hover:text-white">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white/8">
          {username.slice(0, 1).toUpperCase()}
        </span>
        退出登录
      </button>
    </aside>
  )
}
