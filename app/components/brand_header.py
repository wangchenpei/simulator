from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
AVATAR_PATH = ASSETS_DIR / "alpha_wang.jpg"
AUTHOR_NAME = "Alpha Wang"

_BRAND_CSS = """
.bx-app-head {
  margin: -2.5rem calc(-1 * var(--bx-page-pad, 5rem)) 1.25rem;
  padding: 12px var(--bx-page-pad, 5rem);
  background: linear-gradient(90deg, #1a3a52, #2a5a7e);
  color: #f0f6fc;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}
.bx-brand-lockup {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 1400px;
  margin: 0 auto;
}
.bx-brand-avatar-wrap {
  position: relative;
  flex: 0 0 auto;
  width: 52px;
  height: 52px;
}
.bx-brand-avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  object-fit: cover;
  display: block;
  border: 2px solid rgba(255, 255, 255, 0.45);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  background: #fff;
}
.bx-brand-avatar-fb {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #1a3a52;
  background: linear-gradient(160deg, #ffd88a, #ffb347);
  border: 2px solid rgba(255, 255, 255, 0.45);
}
.bx-brand-text {
  min-width: 0;
  flex: 1 1 auto;
}
.bx-app-head h1 {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: #f0f6fc;
}
.bx-app-head .bx-brand-byline {
  margin: 3px 0 0;
  font-size: 0.92rem;
  font-weight: 500;
  letter-spacing: 0.04em;
  opacity: 0.95;
  color: #e8f4ff;
}
@media (max-width: 768px) {
  .bx-app-head {
    margin-left: -1rem;
    margin-right: -1rem;
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
"""


@lru_cache(maxsize=1)
def _avatar_data_uri() -> str | None:
    if not AVATAR_PATH.exists():
        return None
    encoded = base64.b64encode(AVATAR_PATH.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def inject_brand_header_styles() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
          --bx-page-pad: 5rem;
        }}
        {_BRAND_CSS}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand_header(title: str, *, author: str = AUTHOR_NAME) -> None:
    """Top banner with avatar + author, matching BX/Jira check styling."""
    inject_brand_header_styles()
    avatar_uri = _avatar_data_uri()
    if avatar_uri:
        avatar_html = (
            f'<img class="bx-brand-avatar" src="{avatar_uri}" width="52" height="52" '
            f'alt="{author}" decoding="async" '
            'onerror="this.style.display=\'none\'; '
            "this.nextElementSibling.style.display='flex';\" />"
            f'<span class="bx-brand-avatar-fb" style="display:none" aria-hidden="true">AW</span>'
        )
    else:
        avatar_html = '<span class="bx-brand-avatar-fb" aria-hidden="true">AW</span>'

    st.markdown(
        f"""
        <header class="app-head bx-app-head">
          <div class="bx-brand-lockup">
            <div class="bx-brand-avatar-wrap">
              {avatar_html}
            </div>
            <div class="bx-brand-text">
              <h1>{title}</h1>
              <p class="bx-brand-byline">作者 <strong>{author}</strong></p>
            </div>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )
