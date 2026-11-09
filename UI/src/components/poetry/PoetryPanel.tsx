import { useState } from 'react'
import type { PoetryReport } from '../../types'
import { PoetryCard } from '../PoetryCard'
import { ShareCardModal } from '../ShareCardModal'
import { getUsernameFromToken } from '../../api/auth'

interface Props {
  reports: PoetryReport[]
  generating: boolean
  error: string | null
  onGenerate: () => void
}

export default function PoetryPanel({reports, generating, error, onGenerate}: Props) {
  const [share, setShare] = useState<PoetryReport | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const selected = reports.find(report => report.id === selectedId) ?? reports[0]
  const username = getUsernameFromToken()
  function card(report: PoetryReport) {
    return <>
      <PoetryCard report={report} username={username} />
      <button className="mt-3 w-full rounded-xl border border-white/15 py-2 text-sm" onClick={() => setShare(report)}>分享卡片</button>
    </>
  }
  return <section className="panel-enter pb-6">
    <header className="mb-5 flex items-center justify-between">
      <h2 className="serif text-3xl">诗篇</h2>
      <button disabled={generating} onClick={() => { setSelectedId(null); onGenerate() }} className="rounded-full bg-white px-4 py-2 text-sm text-[#101419] disabled:opacity-50">{generating ? '生成中…' : '生成诗篇'}</button>
    </header>
    {error && <p role="alert" className="mb-3 text-sm text-rose-300">{error}</p>}
    {selected ? card(selected) : <p className="text-sm leading-7 text-[#acb5be]">写下至少三则随记，就能把最近的心情写成一首诗。</p>}
    {reports.length > 1 && <label className="mt-5 flex items-center gap-2 text-xs text-[#acb5be]">
      查看诗篇
      <select aria-label="选择诗篇" value={selected.id} onChange={event => setSelectedId(Number(event.target.value))}
        className="min-w-0 flex-1 rounded-md border border-white/10 bg-[#171c22] px-2 py-1.5">
        {reports.map((report, index) => <option key={report.id} value={report.id}>
          {index === 0 ? '最新' : '历史'} · {report.created_at.slice(0, 16)}
        </option>)}
      </select>
    </label>}
    {share && <ShareCardModal open onClose={() => setShare(null)} poetry={share} username={username} />}
  </section>
}
