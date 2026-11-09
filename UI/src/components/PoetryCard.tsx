import type { PoetryReport } from '../types'
import { mapMood } from '../utils/moodMapping'

export function PoetryCard({ report, username, poster = false }: {
  report: PoetryReport
  username?: string | null
  poster?: boolean
}) {
  const distribution = report.emotion_distribution.split(/[·•，,]/).map(part => part.trim()).filter(Boolean)
  return <article className="poem-sheet">
    <header className="poem-heading">
      <p>诗篇 <span aria-hidden="true">/</span> {report.created_at.slice(0, 10).replaceAll('-', '.')}</p>
      <h3>{report.title}</h3>
      {username && <small>给 {username}</small>}
    </header>
    <div className="poem-lines">
      {report.poetry_content.split('\n').filter(Boolean).map((line, i) =>
        <p key={i}>{line.split(/(\*\*.+?\*\*)/g).map((part, j) => part.startsWith('**') && part.endsWith('**')
          ? <strong key={j}>{part.slice(2, -2)}</strong> : part)}</p>)}
    </div>
    {report.quote && <blockquote className="poem-quote">
      <p>{report.quote}</p><cite>{report.quote_author}</cite>
    </blockquote>}
    <div className="poem-moods">{distribution.map((label, i) =>
      <span key={i}><i style={{backgroundColor: mapMood(label.replace(/\d+%/g, '').trim()).color}} />{label}</span>)}</div>
    {report.activity && (poster ?
      <div className="poem-activity"><b>想试一件小事？</b><p>{report.activity}</p></div> :
      <details className="poem-activity"><summary>想试一件小事？</summary><p>{report.activity}</p></details>)}
  </article>
}
