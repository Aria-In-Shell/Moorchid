/**
 * moodMapping.ts
 *
 * Maps stored emotion labels (English canonical + Chinese keywords)
 * onto canvas color, valence (ECG Y-axis), and display names.
 */

import type { Mood } from '../types'

export type MoodLabel = Mood | string
export type MoodType = 'happy' | 'calm' | 'neutral' | 'low' | 'anxious'

export interface MoodMapping {
  type: MoodType
  canonical: Mood
  score: number
  valence: number
  label: string
  displayLabel: string
  color: string
  colorSoft: string
  glow: string
}

type MoodConfig = Omit<MoodMapping, 'label'>

export const MOOD_CONFIGS: Record<MoodType, MoodConfig> = {
  happy: {
    type: 'happy',
    canonical: 'Joy',
    score: 2,
    valence: 0.86,
    displayLabel: '欣喜',
    color: '#F5C15A',
    colorSoft: 'rgba(245,193,90,0.22)',
    glow: 'rgba(245,193,90,0.55)',
  },
  calm: {
    type: 'calm',
    canonical: 'Calm',
    score: 1,
    valence: 0.42,
    displayLabel: '平静',
    color: '#5EEAD4',
    colorSoft: 'rgba(94,234,212,0.2)',
    glow: 'rgba(94,234,212,0.5)',
  },
  neutral: {
    type: 'neutral',
    canonical: 'Neutral',
    score: 0,
    valence: 0,
    displayLabel: '日常',
    color: '#94A3B8',
    colorSoft: 'rgba(148,163,184,0.18)',
    glow: 'rgba(148,163,184,0.4)',
  },
  low: {
    type: 'low',
    canonical: 'Low',
    score: -1,
    valence: -0.52,
    displayLabel: '低落',
    color: '#818CF8',
    colorSoft: 'rgba(129,140,248,0.22)',
    glow: 'rgba(129,140,248,0.5)',
  },
  anxious: {
    type: 'anxious',
    canonical: 'Anxious',
    score: -2,
    valence: -0.86,
    displayLabel: '焦虑',
    color: '#FB7185',
    colorSoft: 'rgba(251,113,133,0.22)',
    glow: 'rgba(251,113,133,0.55)',
  },
}

const KEYWORD_MAP: Array<{ keywords: string[]; type: MoodType }> = [
  {
    keywords: ['焦虑', '痛苦', '崩溃', '抓狂', '压力', '烦恼', '烦躁', '难受', '紧张', '不安', '惶恐', '难熬'],
    type: 'anxious',
  },
  {
    keywords: ['开心', '快乐', '喜悦', '高兴', '棒', '爽', '哈哈', '充实', '满足', '幸福', '欢乐', '欢快', '愉悦', '雀跃', '美滋滋'],
    type: 'happy',
  },
  {
    keywords: ['低落', '疲惫', '累', '无力', '难过', '伤心', '郁闷', '消沉', '沮丧', '困', '疲倦', '困倦', '疲乏', '没劲'],
    type: 'low',
  },
  {
    keywords: ['平静', '舒缓', '舒适', '温暖', '放松', '安宁', '安心', '踏实', '宁静', '惬意', '闲适', '轻松', '自在'],
    type: 'calm',
  },
  {
    keywords: ['中性', '观察', '一般', '日常', '思考', '平常', '普通', '还好'],
    type: 'neutral',
  },
]

const ENUM_MAP: Record<string, MoodType> = {
  Joy: 'happy',
  Happy: 'happy',
  joy: 'happy',
  happy: 'happy',
  Calm: 'calm',
  Cozy: 'calm',
  calm: 'calm',
  cozy: 'calm',
  Neutral: 'neutral',
  neutral: 'neutral',
  Low: 'low',
  low: 'low',
  Anxious: 'anxious',
  anxious: 'anxious',
}

function resolveEnum(input: string): MoodType | null {
  if (ENUM_MAP[input]) return ENUM_MAP[input]
  const lower = input.toLowerCase()
  if (ENUM_MAP[lower]) return ENUM_MAP[lower]
  return null
}

export function mapMood(raw: Mood | string | null | undefined): MoodMapping {
  if (!raw || !String(raw).trim()) {
    return { ...MOOD_CONFIGS.neutral, label: '', displayLabel: '未记录' }
  }
  const input = String(raw).trim()
  const enumType = resolveEnum(input)
  if (enumType) return { ...MOOD_CONFIGS[enumType], label: input }

  for (const { keywords, type } of KEYWORD_MAP) {
    for (const kw of keywords) {
      if (input.includes(kw)) return { ...MOOD_CONFIGS[type], label: input }
    }
  }
  return { ...MOOD_CONFIGS.neutral, label: input }
}

export function valenceForMood(raw: Mood | string | null | undefined, explicit?: number | null): number {
  if (typeof explicit === 'number' && Number.isFinite(explicit)) {
    return Math.max(-1, Math.min(1, explicit))
  }
  return mapMood(raw).valence
}

export function nodeRadius(intensity?: number | null): number {
  const value = typeof intensity === 'number' ? intensity : 0.55
  return 5.5 + Math.max(0, Math.min(1, value)) * 5.5
}

export const Y_TICKS = [
  { value: -1, label: '低谷' },
  { value: 0, label: '水平' },
  { value: 1, label: '高处' },
]

export const getMoodConfig = mapMood
export const SCORE_DOMAIN = [-2, 2] as const
