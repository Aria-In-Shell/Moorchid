import { PoetryCard } from './PoetryCard'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties } from 'react'
import { toPng } from 'html-to-image'
import { QRCodeSVG } from 'qrcode.react'
import type { PoetryReport } from '../types'

// ─── Palette ─────────────────────────────────────────────────────────────────
const C = {
  bg:        '#E8E2D5',
  card:      '#171c22',
  cardDeep:  '#20272d',
  ink:       '#e4eceb',
  inkMid:    '#c5d2d0',
  inkLight:  '#8A9E90',
  terra:     '#486e69',
  cinnabar:  '#e4a5a4',
  border:    '#384546',
  moss:      '#466861',
  mossMid:   '#4E6B5C',
  mossLight: '#7A9B8A',
  shadow:    'rgba(58,82,71,0.10)',
}

const FONT_SERIF_EN = '"Libertinus Serif", "Playfair Display", "Lora", "Baskerville", "Georgia", serif'
const FONT_SANS     = '"DM Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'

// ─── Types ──────────────────────────────────────────────────────────────────
export interface ShareCardModalProps {
  open: boolean
  onClose: () => void
  poetry: PoetryReport | null
  username?: string | null
  /** 二维码扫码后会跳转的链接；默认 https://cloverspace.cn。 */
  shareUrl?: string
}

function describeClient(): 'wechat' | 'mobile' | 'desktop' {
  if (typeof navigator === 'undefined') return 'desktop'
  const ua = navigator.userAgent
  if (/MicroMessenger/i.test(ua)) return 'wechat'
  if (/Android|iPhone|iPad|iPod|Mobile/i.test(ua)) return 'mobile'
  const touch =
    typeof window !== 'undefined'
    && (('ontouchstart' in window) || (navigator.maxTouchPoints ?? 0) > 0)
  if (touch) return 'mobile'
  return 'desktop'
}

// ─── Poster Card DOM (the actual art that gets screenshotted) ───────────────

interface PosterCardProps {
  poetry: PoetryReport
  username: string
  shareUrl: string
}

function PosterCard({poetry, username, shareUrl}: PosterCardProps) {
  return <div data-share-card-root style={{ width: 350, maxWidth: '78vw', background: '#161a21', borderRadius: 20, overflow: 'hidden' }}>
    <PoetryCard report={poetry} username={username} poster />
    <footer style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 22px', color: '#b8c8c6'}}>
      <span>Moorchid</span><QRCodeSVG value={shareUrl} size={44} marginSize={2} />
    </footer>
  </div>
}

export function ShareCardModal({
  open,
  onClose,
  poetry,
  username,
  shareUrl = 'https://cloverspace.cn',
}: ShareCardModalProps) {
  // 卡片 DOM ref —— 截图源。
  const cardWrapperRef = useRef<HTMLDivElement | null>(null)
  const [generating, setGenerating] = useState(false)
  const [pngUrl, setPngUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const client = useMemo(() => describeClient(), [])

  // 关闭 modal 时清理中间状态
  useEffect(() => {
    if (!open) {
      setPngUrl(null)
      setError(null)
      setGenerating(false)
    }
  }, [open])

  /**
   * 关键修复：被截图的 [data-share-card-root] 现在始终真实挂载在 Modal 中
   * （不再是 `visibility: hidden` 屏外节点），配合字体 ready + 120ms 延迟，
   * 可以避免「拿到一张白图」的 canvas 捕获失败。
   */
  const handleGenerate = useCallback(async () => {
    const node = cardWrapperRef.current?.querySelector<HTMLElement>(
      '[data-share-card-root]',
    )
    if (!node || !poetry) return
    setGenerating(true)
    setError(null)
    try {
      // 双保险：字体真正就绪 + 短暂延迟让一帧 layout 落定
      if (typeof document !== 'undefined' && document.fonts?.ready) {
        await document.fonts.ready.catch(() => undefined)
      }
      await new Promise(r => setTimeout(r, 120))
      const dataUrl = await toPng(node, {
        pixelRatio: 2,
        cacheBust: true,
        backgroundColor: '#161a21',
        skipFonts: true,
      })
      setPngUrl(dataUrl)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(`生成长图失败：${msg}`)
    } finally {
      setGenerating(false)
    }
  }, [poetry])

  const handleDownload = useCallback(() => {
    if (!pngUrl || !poetry) return
    const a = document.createElement('a')
    a.href = pngUrl
    const safeDate = poetry.created_at.split(' ')[0] || 'card'
    a.download = `moorchid-${safeDate}.png`
    document.body.appendChild(a)
    a.click()
    a.remove()
  }, [pngUrl, poetry])

  if (!open || !poetry) return null
  const usernameDisplay = username?.trim() || '朋友'

  return (
    <div
      role="dialog"
      aria-modal
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 80,
        background: 'rgba(42,51,40,0.55)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '16px',
        fontFamily: FONT_SANS,
        WebkitBackdropFilter: 'blur(2px)', backdropFilter: 'blur(2px)',
        animation: 'scm-fade 220ms ease both',
      }}
    >
      <style>{`
        @keyframes scm-fade {
          from { opacity: 0; }
          to   { opacity: 1; }
        }
        @keyframes scm-pop {
          from { opacity: 0; transform: translateY(12px) scale(0.96); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }
      `}</style>

      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: C.card, borderRadius: 26,
          width: '100%', maxWidth: 420,
          maxHeight: '90vh', overflow: 'auto',
          boxShadow: '0 30px 70px rgba(0,0,0,0.32)',
          animation: 'scm-pop 280ms cubic-bezier(0.22,1,0.36,1) both',
          padding: '20px 16px 18px',
          boxSizing: 'border-box',
        }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div>
            <p style={{
              fontFamily: FONT_SANS, fontSize: 10, fontWeight: 700,
              letterSpacing: '0.34em', color: C.mossLight, margin: 0,
            }}>
              SHARE · 分享卡片
            </p>
            <p style={{
              fontFamily: FONT_SERIF_EN, fontSize: 18, fontStyle: 'italic',
              color: C.ink, fontWeight: 700, margin: '4px 0 0',
            }}>
              Moorchid · 周报长图
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="关闭"
            style={{
              width: 32, height: 32, borderRadius: 16, border: 'none',
              background: 'rgba(58,82,71,0.08)', color: C.inkMid,
              fontSize: 18, lineHeight: 1, cursor: 'pointer',
            }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ marginTop: 4 }}>
          {!pngUrl ? (
            <>
              {/* 实时卡片预览（也是 toPng 截图源）：fixed 360×640 真实挂载，
                  不再 visibility:hidden / 离屏。 */}
              <div style={{ display: 'flex', justifyContent: 'center', padding: '2px 0 14px' }}>
                <div ref={cardWrapperRef}>
                  <PosterCard
                    poetry={poetry}
                    username={usernameDisplay}
                    shareUrl={shareUrl}
                  />
                </div>
              </div>

              <div style={{
                background: C.cardDeep, borderRadius: 16,
                padding: '14px 16px', border: `1px dashed ${C.border}`,
                textAlign: 'center',
              }}>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  style={{
                    marginTop: 12, padding: '12px 0', width: '100%',
                    background: C.terra, color: '#FAF7F0', border: 'none',
                    borderRadius: 13, fontSize: 13.5, fontWeight: 600,
                    fontFamily: FONT_SANS, letterSpacing: '0.18em',
                    cursor: generating ? 'default' : 'pointer',
                    boxShadow: '0 4px 14px rgba(184,115,85,0.32)',
                    opacity: generating ? 0.6 : 1,
                  }}
                >
                  {generating ? '正在生成…' : '生成长图'}
                </button>
                {error && (
                  <p style={{ marginTop: 10, fontSize: 12, color: C.cinnabar }}>{error}</p>
                )}
              </div>
            </>
          ) : (
            <>
              {/* 已生成的 PNG：直接渲染到 <img>，让微信 / 移动端长按保存。 */}
              <img
                src={pngUrl}
                alt="情绪诗篇分享长图"
                style={{
                  display: 'block',
                  width: '100%',
                  maxWidth: 360,
                  height: 'auto',
                  margin: '0 auto',
                  borderRadius: 18,
                  boxShadow: `0 14px 40px ${C.shadow}`,
                }}
              />

              <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {client === 'desktop' ? (
                  <button onClick={handleDownload} style={primaryButton(C.moss)}>
                    保存 PNG 到本地
                  </button>
                ) : (
                  <div style={mobileTipStyle()}>
                    <span aria-hidden style={{ fontSize: 18, lineHeight: 1, flexShrink: 0 }}>✨</span>
                    <span style={{ flex: 1 }}>
                      <strong>长按上方图片</strong>即可保存到相册或发送给好友。
                    </span>
                  </div>
                )}
                <button onClick={() => setPngUrl(null)} style={secondaryButton()}>
                  重新生成
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Style helpers ──────────────────────────────────────────────────────────
function primaryButton(bg: string): CSSProperties {
  return {
    padding: '12px 0', width: '100%',
    background: bg, color: '#FAF7F0', border: 'none',
    borderRadius: 13, fontSize: 13.5, fontWeight: 600,
    fontFamily: FONT_SANS, letterSpacing: '0.18em',
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(58,82,71,0.25)',
  }
}

function secondaryButton(): CSSProperties {
  return {
    padding: '11px 0', width: '100%',
    background: 'transparent',
    color: C.mossMid,
    border: `1px solid ${C.border}`,
    borderRadius: 13,
    fontSize: 13, fontWeight: 500,
    fontFamily: FONT_SANS,
    cursor: 'pointer',
  }
}

function mobileTipStyle(): CSSProperties {
  return {
    padding: '12px 14px',
    background: 'linear-gradient(135deg, rgba(58,82,71,0.06), rgba(184,115,85,0.06))',
    border: `1px solid ${C.border}`,
    borderRadius: 13,
    fontSize: 13,
    color: C.inkMid,
    lineHeight: 1.65,
    fontFamily: FONT_SANS,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    textAlign: 'left',
  }
}

export default ShareCardModal
