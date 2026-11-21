"""Look and feel: styling, header banner, question card and score ring. Works in light and dark mode."""

import html

import streamlit as st

CSS = """
<style>
.block-container {padding-top: 3.6rem; max-width: 1150px;}
.is-banner {background: linear-gradient(120deg, #312E81 0%, #4F46E5 55%, #7C3AED 100%); color: #fff;
  border-radius: 18px; padding: 22px 28px 18px; margin-bottom: 16px; box-shadow: 0 6px 22px rgba(79,70,229,.28);}
.is-banner h1 {color: #fff; font-size: 2.05rem; margin: 0 0 4px; padding: 0; line-height: 1.2;}
.is-banner p {color: rgba(255,255,255,.9); margin: 0 0 12px; font-size: 1.02rem;}
.is-chip {display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
  border-radius: 999px; padding: 3px 12px; margin: 0 8px 4px 0; font-size: .85rem; color: #fff;}
.is-q {border: 1px solid rgba(79,70,229,.35); border-left: 6px solid #4F46E5; background: rgba(79,70,229,.08);
  border-radius: 14px; padding: 16px 20px; margin: 6px 0 10px;}
.is-q .who {font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; opacity: .75; margin-bottom: 4px;}
.is-q .text {font-size: 1.28rem; font-weight: 600; line-height: 1.45;}
.is-ring-wrap {display: flex; align-items: center; gap: 22px; margin: 6px 0 14px;}
.is-ring {width: 132px; height: 132px; position: relative; flex: none;}
.is-ring .arc {position: absolute; inset: 0; border-radius: 50%;
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 14px), #000 calc(100% - 13px));
          mask: radial-gradient(farthest-side, transparent calc(100% - 14px), #000 calc(100% - 13px));}
.is-ring .label {position: absolute; inset: 0; display: grid; place-items: center; text-align: center;}
.is-ring .num {font-size: 2.1rem; font-weight: 800; line-height: 1;}
.is-ring .of {font-size: .75rem; opacity: .7;}
.is-ready {font-size: 1.35rem; font-weight: 700;}
.is-sub {opacity: .8;}
[data-testid="stChatMessage"] {border-radius: 14px;}
[data-baseweb="tab"] {font-weight: 600;}
</style>
"""

def apply_style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def banner(title: str, subtitle: str, chips: list[str]) -> None:
    chip_html = "".join(f'<span class="is-chip">{html.escape(c)}</span>' for c in chips)
    st.markdown(f'<div class="is-banner"><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p>{chip_html}</div>',
                unsafe_allow_html=True)


def question_card(who: str, text: str) -> None:
    st.markdown(f'<div class="is-q"><div class="who">🧑‍💼 {html.escape(who)}</div>'
                f'<div class="text">{html.escape(text)}</div></div>', unsafe_allow_html=True)


def score_color(score: int) -> str:
    return "#16A34A" if score >= 75 else "#F59E0B" if score >= 55 else "#DC2626"


def score_ring(score: int, readiness: str, sub: str) -> None:
    c = score_color(score)
    st.markdown(
        f'<div class="is-ring-wrap"><div class="is-ring">'
        f'<div class="arc" style="background: conic-gradient({c} {score * 3.6}deg, rgba(128,128,128,.25) 0deg);"></div>'
        f'<div class="label"><div><div class="num" style="color:{c}">{score}</div><div class="of">out of 100</div></div></div>'
        f'</div><div><div class="is-ready">{html.escape(readiness)}</div><div class="is-sub">{html.escape(sub)}</div></div></div>',
        unsafe_allow_html=True)
