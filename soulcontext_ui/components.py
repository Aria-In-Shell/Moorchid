"""UI helper functions for Moorchid — card rendering & markdown helpers."""

from __future__ import annotations

from typing import Sequence

import streamlit as st


def render_flomo_card(
    content: str,
    emotion: str,
    tags: Sequence[str],
    created_at: str,
    entry_id: int | None = None,
    on_delete_url: str | None = None,
) -> None:
    """Render a journal entry as a flomo-style minimalist card."""
    tags_html = "".join(
        f'<span class="fc-tag">{tag}</span>' for tag in (tags or [])
    )

    html = f"""
    <div class="flomo-card" id="fc-{entry_id if entry_id else ''}">
      <div class="fc-header">
        <span class="fc-emotion-badge">{emotion or '平静'}</span>
        <span class="fc-time">{created_at or ''}</span>
      </div>
      <div class="fc-content">{_escape_html(content)}</div>
      <div class="fc-tags">{tags_html}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_xhs_card(
    title: str,
    poetry: str,
    emotion_distribution: str,
    blessing: str,
    created_at: str | None = None,
) -> None:
    """Render a poetry report as a Xiaohongshu-style high-aesthetic card."""
    # Parse emotion distribution into a simple progress bar
    # e.g. "70% 专注探索 · 30% 惬意"  →  70%
    first_part = emotion_distribution.split("%")[0] if "%" in emotion_distribution else "70"
    try:
        fill_percent = min(100, max(0, int(first_part)))
    except ValueError:
        fill_percent = 70

    time_str = f'<span class="xhs-timestamp">{created_at}</span>' if created_at else ""

    html = f"""
    <div class="xhs-card">
      <div class="xhs-title">{_escape_html(title)}</div>
      <div class="xhs-divider"></div>
      <div class="xhs-poetry">{_escape_html(poetry)}</div>
      <div class="xhs-emotion-bar">
        <span class="xhs-emotion-label">情绪气象</span>
        <div class="xhs-emotion-track">
          <div class="xhs-emotion-fill" style="width:{fill_percent}%"></div>
        </div>
        <span class="xhs-emotion-label">{emotion_distribution}</span>
      </div>
      <div class="xhs-blessing">{_escape_html(blessing)}</div>
      <div class="xhs-footer">
        <span></span>
        {time_str}
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_locked_hint(current_count: int, required: int = 3) -> None:
    """Show the locked state when poetry is not yet available."""
    remaining = required - current_count
    html = f"""
    <div class="locked-hint">
      <div class="lock-icon">🔒</div>
      <p>情绪诗篇需要 <strong>{required}</strong> 条随记才能生成。<br>
      再记录 <strong>{remaining}</strong> 条，就能解锁本周诗篇 ✨</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def inject_styles() -> None:
    """Inject the ui/styles.css file into the page."""
    import os
    from pathlib import Path

    css_path = Path(__file__).parent / "styles.css"
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )
    else:
        st.warning("UI styles not found. Please ensure ui/styles.css exists.")


def _escape_html(text: str) -> str:
    """Basic HTML escaping for user-provided text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("\n", "<br>")
    )
