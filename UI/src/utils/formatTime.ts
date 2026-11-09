export function formatClock(iso: string): string {
  const time = iso.split(' ')[1] ?? '00:00:00'
  return time.slice(0, 5)
}

export function formatDateLabel(iso: string): { day: string; weekday: string; full: string } {
  const [datePart] = iso.split(' ')
  const [year, month, day] = datePart.split('-').map(Number)
  const d = new Date(year, month - 1, day)
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  const yest = new Date(now)
  yest.setDate(now.getDate() - 1)
  const yesterday = `${yest.getFullYear()}-${pad(yest.getMonth() + 1)}-${pad(yest.getDate())}`
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']

  let weekday = weekdays[d.getDay()]
  if (datePart === today) weekday = '今天'
  else if (datePart === yesterday) weekday = '昨天'

  return {
    day: `${month}月${pad(day)}日`,
    weekday,
    full: `${year}年${month}月${pad(day)}日 ${weekday}`,
  }
}

export function formatRelative(updatedAt: string): string {
  const [datePart, timePart] = updatedAt.split(' ')
  const [y, m, d] = datePart.split('-').map(Number)
  const [hh, mm] = (timePart ?? '00:00:00').split(':').map(Number)
  const dt = new Date(y, m - 1, d, hh, mm)
  const now = new Date()
  const diffMin = Math.floor((now.getTime() - dt.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} 小时前`
  return `${m}月${d}日`
}
