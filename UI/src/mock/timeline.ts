import type { Entry, Mood } from '../types'
import { valenceForMood } from '../utils/moodMapping'

export const MOCK_USER = 'preview'

function daysAgo(days: number, hour: number, minute = 0): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  d.setHours(hour, minute, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:00`
}

const RAW: Array<{
  id: number
  content: string
  emotion: Mood
  tags: string[]
  days: number
  hour: number
  minute?: number
  intensity: number
}> = [
  {
    id: -1,
    content: '周末把书桌收拾干净了，窗外有风，忽然觉得可以慢慢来。',
    emotion: 'Calm',
    tags: ['#生活片刻'],
    days: 6,
    hour: 10,
    intensity: 0.45,
  },
  {
    id: -2,
    content: '项目突然加塞，开会时脑子里一直在倒计时。',
    emotion: 'Anxious',
    tags: ['#工作日常'],
    days: 5,
    hour: 16,
    minute: 20,
    intensity: 0.82,
  },
  {
    id: -3,
    content: '晚上和朋友通了很久的电话，说完反而更空了一点。',
    emotion: 'Low',
    tags: ['#关系心事'],
    days: 4,
    hour: 22,
    minute: 40,
    intensity: 0.6,
  },
  {
    id: -4,
    content: '把拖了两周的那封邮件发出去了。不是轻松，是终于做完。',
    emotion: 'Joy',
    tags: ['#微小确幸'],
    days: 4,
    hour: 11,
    intensity: 0.7,
  },
  {
    id: -5,
    content: '午后图书馆，键盘声很齐。我只是坐着，没有特别的心情。',
    emotion: 'Neutral',
    tags: ['#今日心绪'],
    days: 3,
    hour: 14,
    intensity: 0.35,
  },
  {
    id: -6,
    content: '散步走到河堤，晚霞把水岸烫成一条细线。',
    emotion: 'Calm',
    tags: ['#身体感受'],
    days: 2,
    hour: 18,
    minute: 30,
    intensity: 0.5,
  },
  {
    id: -7,
    content: '失眠到三点，脑子里循环白天没说出口的那句话。',
    emotion: 'Anxious',
    tags: ['#睡眠状态'],
    days: 2,
    hour: 3,
    minute: 10,
    intensity: 0.88,
  },
  {
    id: -8,
    content: '早上醒来发现自己还在，太阳很好。决定先吃一顿热的。',
    emotion: 'Joy',
    tags: ['#微小确幸'],
    days: 1,
    hour: 8,
    minute: 40,
    intensity: 0.64,
  },
  {
    id: -9,
    content: '下午有点提不起劲，把待办又往明天推了一格。',
    emotion: 'Low',
    tags: ['#情绪低谷'],
    days: 1,
    hour: 16,
    intensity: 0.52,
  },
  {
    id: -10,
    content: '此刻坐在灯下，想把这一周轻轻记下。',
    emotion: 'Calm',
    tags: ['#生活片刻'],
    days: 0,
    hour: 21,
    minute: 12,
    intensity: 0.48,
  },
]

export const MOCK_ENTRIES: Entry[] = RAW.map((row) => ({
  id: row.id,
  user_id: MOCK_USER,
  content: row.content,
  emotion: row.emotion,
  tags: row.tags,
  created_at: daysAgo(row.days, row.hour, row.minute ?? 0),
  valence: valenceForMood(row.emotion),
  intensity: row.intensity,
  analysis: {
    emotion: row.emotion,
    valence: valenceForMood(row.emotion),
    intensity: row.intensity,
    tags: row.tags,
    themes: [],
  },
}))
