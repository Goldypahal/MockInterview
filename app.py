"""Interview Saathi - a voice mock-interview coach for campus placements.

Run with:  streamlit run app.py
"""

import hashlib
import io
from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st
from pypdf import PdfReader

import config
from gemini_client import friendly_error
from interviewer import Interview, InterviewSetup, final_feedback, opening_question, submit_answer
from metrics import IDEAL_WPM, fluency_score, pace_label, speaking_metrics, wav_duration_seconds
from roles import INTERVIEW_TYPES, LEVELS, ROLES
from ui import apply_style, banner, question_card, score_ring
from voice import VoiceError, speak

st.set_page_config(page_title="Interview Saathi", page_icon="🎤", layout="wide")
apply_style()

if config.missing_settings():
    st.error("Missing GEMINI_API_KEY in your .env file.")
    st.info("Copy .env.example to .env and paste your free key from https://aistudio.google.com/apikey, "
            "then restart the app.")
    st.stop()

ss = st.session_state
ss.setdefault("stage", "setup")        # setup -> interview -> report
ss.setdefault("q_audio", {})           # turn index -> MP3 of the question
ss.setdefault("played", set())         # turn indexes whose question audio already auto-played


# ---------- helpers ----------

def question_audio(index: int, text: str) -> bytes | None:
    if index not in ss.q_audio:
        try:
            ss.q_audio[index] = speak(text)
        except VoiceError as exc:
            st.warning(str(exc))
            ss.q_audio[index] = None
    return ss.q_audio[index]


def scores(interview: Interview) -> dict:
    answered = [t for t in interview.turns if t.answered_by]
    content = [t.content or 1 for t in answered]
    clarity = [t.clarity or 1 for t in answered]
    c = round(10 * sum(content) / len(content)) if content else 0
    cl = round(10 * sum(clarity) / len(clarity)) if clarity else 0
    fl = fluency_score(answered)
    overall = round(0.5 * c + 0.3 * cl + 0.2 * fl) if fl is not None else round(0.6 * c + 0.4 * cl)
    readiness = "Ready 🚀" if overall >= 75 else "Almost ready 💪" if overall >= 55 else "Needs more practice 📚"
    return {"content": c, "clarity": cl, "fluency": fl, "overall": overall, "readiness": readiness}


def all_fillers(interview: Interview) -> Counter:
    total = Counter()
    for t in interview.turns:
        if t.metrics:
            total.update(t.metrics["fillers"])
    return total


def scorecard_markdown(interview: Interview, s: dict, fb: dict) -> str:
    st_ = interview.setup
    lines = [f"# Interview Saathi: Mock Interview Scorecard", "",
             f"- **Candidate:** {st_.candidate_name or '-'}", f"- **Role:** {st_.role} ({st_.level})",
             f"- **Interview type:** {st_.interview_type}", f"- **Date:** {datetime.now():%d %b %Y, %I:%M %p}", "",
             f"## Scores", f"- **Overall:** {s['overall']}/100 ({s['readiness']})",
             f"- Content: {s['content']}/100", f"- Clarity: {s['clarity']}/100",
             f"- Fluency: {s['fluency'] if s['fluency'] is not None else 'n/a'}/100", "",
             "## Summary", fb.get("summary", ""), "", "## Strengths", *[f"- {x}" for x in fb.get("strengths", [])], "",
             "## Improve", *[f"- {x}" for x in fb.get("improvements", [])], "",
             "## Topics to revise", *[f"- {x}" for x in fb.get("topics_to_revise", [])], "",
             "## A stronger answer", f"**Q:** {fb.get('weakest_question', '')}", "", fb.get("better_answer", ""), "",
             "## Question by question"]
    for i, t in enumerate([t for t in interview.turns if t.answered_by], start=1):
        lines += [f"### Q{i}. {t.question}", f"*Answer ({t.answered_by}):* {t.answer or '(skipped)'}", "",
                  f"Content {t.content}/10 · Clarity {t.clarity}/10"
                  + (f" · Fillers {t.metrics['filler_count']} · Pace {t.metrics['wpm'] or '-'} wpm" if t.metrics else ""),
                  f"- Good: {t.strengths}", f"- Improve: {t.improvement}", ""]
    return "\n".join(lines)


# ---------- screen 1: setup ----------

def setup_screen():
    banner("🎤 Interview Saathi",
           "Voice mock interviews for campus placements. Saathi asks questions out loud, listens to your answers, "
           "asks follow-ups, and gives you a scorecard.",
           [f"🎯 {len(ROLES)} roles + custom", "🗣️ Voice answers", "🔁 Smart follow-ups", "📊 Filler words & pace"])
    with st.form("setup"):
        c1, c2 = st.columns(2)
        c1.markdown("##### 👤 About you")
        c2.markdown("##### 🎯 The interview")
        name = c1.text_input("Your name (optional)")
        role = c2.selectbox("Role", list(ROLES) + ["Other (type below)"])
        custom_role = c2.text_input("If Other, which role?", placeholder="e.g. Business Analyst")
        level = c1.radio("Experience", LEVELS, horizontal=True)
        itype = c1.radio("Interview type", list(INTERVIEW_TYPES), index=2, horizontal=True)
        n = c2.slider("Number of main questions", 3, 8, 5,
                      help="Plus up to one follow-up per question. Each answer uses one free Gemini request.")
        feedback_live = c2.toggle("Show quick feedback after each answer", value=False,
                                  help="Off = like a real interview, feedback only at the end.")
        with st.expander("Personalise with your resume or a job description (optional)"):
            resume_pdf = st.file_uploader("Resume (PDF)", type=["pdf"])
            resume_txt = st.text_area("…or paste your resume text", height=120)
            jd = st.text_area("Job description", height=120)
        start = st.form_submit_button("Start interview", type="primary")

    st.caption("Tip: use headphones and a quiet room. Speak naturally; filler words like 'um' are counted.")
    if start:
        resume = resume_txt
        if resume_pdf is not None:
            try:
                resume = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(resume_pdf.getvalue())).pages)
            except Exception:
                st.warning("Couldn't read the resume PDF; continuing without it.")
        chosen = custom_role.strip() if role.startswith("Other") else role
        if not chosen:
            st.error("Please type the role.")
            return
        setup = InterviewSetup(role=chosen, level=level, interview_type=itype, num_questions=n,
                               candidate_name=name, resume_text=resume or "", job_description=jd or "")
        ss.interview = Interview(setup=setup, turns=[opening_question(setup)])
        ss.feedback_live, ss.q_audio, ss.played = feedback_live, {}, set()
        ss.pop("final", None)
        ss.pop("last_feedback", None)
        ss.stage = "interview"
        st.rerun()


# ---------- screen 2: interview ----------

def process(audio=None, typed=None, skipped=False):
    iv: Interview = ss.interview
    turn_index = len(iv.turns) - 1
    try:
        with st.spinner("Saathi is listening to your answer..."):
            turn = submit_answer(iv, audio_wav=audio, typed=typed, skipped=skipped)
    except Exception as exc:
        ss.error = friendly_error(exc)
        return
    if audio is not None:
        turn.metrics = speaking_metrics(turn.answer, wav_duration_seconds(audio))
        if turn.metrics["words"] == 0:
            ss.error = "I couldn't hear any words in that recording. Please try again."
            # undo: drop the next question that was added and reset this turn
            if not iv.finished and len(iv.turns) > turn_index + 1:
                iv.turns.pop()
            iv.finished = False
            turn.answered_by, turn.answer, turn.metrics = "", "", None
            return
    ss.last_feedback = turn
    if iv.finished:
        ss.stage = "report"


def interview_screen():
    iv: Interview = ss.interview
    s = iv.setup
    idx = len(iv.turns) - 1
    turn = iv.current

    top1, top2 = st.columns([4, 1])
    top1.markdown(f"### 🎤 {s.role}")
    top1.caption(f"{s.interview_type} interview · {s.level}")
    if top2.button("End interview", help="Finish now and see your scorecard"):
        if any(t.answered_by for t in iv.turns):
            iv.turns = [t for t in iv.turns if t.answered_by]
            iv.finished = True
            ss.stage = "report"
        else:
            ss.stage = "setup"
        st.rerun()
    st.progress(min(1.0, iv.main_questions_asked / s.num_questions),
                text=f"Question {iv.main_questions_asked} of {s.num_questions}"
                     + (" · follow-up" if turn.kind == "follow_up" else ""))

    if ss.get("error"):
        st.error(ss.pop("error"))
    if ss.feedback_live and ss.get("last_feedback") is not None:
        f = ss.pop("last_feedback")
        msg = f"**Last answer:** content {f.content}/10, clarity {f.clarity}/10"
        if f.metrics:
            msg += f", {f.metrics['filler_count']} filler word(s), pace {f.metrics['wpm'] or '-'} wpm ({pace_label(f.metrics['wpm'])})"
        st.info(f"{msg}\n\n✅ {f.strengths}\n\n💡 {f.improvement}")
    else:
        ss.pop("last_feedback", None)

    question_card("Saathi · follow-up question" if turn.kind == "follow_up" else "Saathi asks", turn.question)
    audio = question_audio(idx, turn.question)
    if audio:
        st.audio(audio, format="audio/mpeg", autoplay=idx not in ss.played)
        ss.played.add(idx)

    tab_voice, tab_type = st.tabs(["🎙️ Answer by voice", "⌨️ Type instead"])
    with tab_voice:
        rec = st.audio_input("Click the mic, answer, then click again to stop. Your answer is sent automatically.",
                             sample_rate=16000, key=f"answer_{idx}")
        if rec is not None:
            data = rec.getvalue()
            h = hashlib.sha256(data).hexdigest()
            if ss.get("last_rec") != h:
                ss.last_rec = h
                process(audio=data)
                st.rerun()
    with tab_type:
        with st.form(f"typed_{idx}", clear_on_submit=True):
            txt = st.text_area("Your answer", height=140)
            if st.form_submit_button("Submit answer") and txt.strip():
                process(typed=txt.strip())
                st.rerun()

    if st.button("Skip this question"):
        process(skipped=True)
        st.rerun()

    done = [t for t in iv.turns if t.answered_by]
    if done:
        with st.expander(f"Conversation so far ({len(done)} answered)"):
            for t in done:
                st.markdown(f"**Q:** {t.question}")
                st.markdown(f"**You ({t.answered_by}):** {t.answer or '_(skipped)_'}")


# ---------- screen 3: scorecard ----------

def report_screen():
    iv: Interview = ss.interview
    s = scores(iv)
    if "final" not in ss:
        try:
            with st.spinner("Preparing your scorecard..."):
                ss.final = final_feedback(iv)
        except Exception as exc:
            st.warning("Couldn't generate the written feedback: " + friendly_error(exc))
            ss.final = {}
    fb = ss.final
    answered = [t for t in iv.turns if t.answered_by]

    banner("📊 Your Interview Scorecard", f"{iv.setup.role} · {iv.setup.interview_type} · {iv.setup.level}",
           [f"✅ {len(answered)} answers", f"🗓️ {datetime.now():%d %b %Y}"])
    left, right = st.columns([2, 3])
    with left:
        score_ring(s["overall"], s["readiness"], "Overall score")
    with right:
        m = st.columns(3)
        m[0].metric("Content", f"{s['content']}/100")
        m[1].metric("Clarity", f"{s['clarity']}/100")
        m[2].metric("Fluency", f"{s['fluency']}/100" if s["fluency"] is not None else "n/a",
                    help="From filler words and speaking pace (voice answers only)")
        for label, val in (("Content", s["content"]), ("Clarity", s["clarity"]), ("Fluency", s["fluency"])):
            if val is not None:
                st.progress(val / 100, text=label)

    if fb.get("summary"):
        st.write(fb["summary"])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### ✅ Strengths")
        for x in fb.get("strengths", []):
            st.markdown(f"- {x}")
    with c2:
        st.markdown("#### 💡 Improve")
        for x in fb.get("improvements", []):
            st.markdown(f"- {x}")

    st.markdown("#### Scores by question")
    df = pd.DataFrame({"Question": [f"Q{i}" for i in range(1, len(answered) + 1)],
                       "Content": [t.content or 0 for t in answered],
                       "Clarity": [t.clarity or 0 for t in answered]}).set_index("Question")
    st.bar_chart(df, stack=False, height=260, color=["#4F46E5", "#A5B4FC"])

    voice = [t for t in answered if t.metrics]
    if voice:
        st.markdown("#### 🗣️ Speaking")
        fillers = all_fillers(iv)
        words = sum(t.metrics["words"] for t in voice)
        wpms = [t.metrics["wpm"] for t in voice if t.metrics["wpm"]]
        a, b, c = st.columns(3)
        a.metric("Filler words", sum(fillers.values()), help="um, uh, basically, you know, actually ...")
        b.metric("Fillers per 100 words", round(100 * sum(fillers.values()) / words, 1) if words else 0)
        avg = round(sum(wpms) / len(wpms)) if wpms else None
        c.metric("Average pace", f"{avg} wpm" if avg else "–", pace_label(avg) if avg else None,
                 delta_color="off", help=f"Comfortable range: {IDEAL_WPM[0]}–{IDEAL_WPM[1]} words per minute")
        if fillers:
            st.caption("Most used: " + ", ".join(f"“{w}” × {n}" for w, n in fillers.most_common(6)))

    st.markdown("#### Question by question")
    for i, t in enumerate(answered, start=1):
        label = f"Q{i}. {t.question[:90]}{'…' if len(t.question) > 90 else ''}  ·  {t.content}/10, {t.clarity}/10"
        with st.expander(label):
            st.markdown(f"**Question:** {t.question}")
            st.markdown(f"**Your answer ({t.answered_by}):** {t.answer or '_(skipped)_'}")
            if t.metrics:
                st.caption(f"{t.metrics['words']} words · {t.metrics['duration_s']} s · "
                           f"{t.metrics['wpm'] or '-'} wpm ({pace_label(t.metrics['wpm'])}) · "
                           f"{t.metrics['filler_count']} filler word(s)")
            st.markdown(f"✅ {t.strengths}\n\n💡 {t.improvement}")

    if fb.get("better_answer"):
        st.markdown("#### ✨ A stronger answer")
        st.markdown(f"**{fb.get('weakest_question', '')}**")
        st.success(fb["better_answer"])
    if fb.get("topics_to_revise"):
        st.markdown("#### 📚 Revise before your real interview")
        st.markdown("\n".join(f"- {x}" for x in fb["topics_to_revise"]))

    st.divider()
    b1, b2, b3 = st.columns(3)
    b1.download_button("⬇ Download scorecard", scorecard_markdown(iv, s, fb),
                       file_name=f"interview_scorecard_{datetime.now():%Y%m%d_%H%M}.md", mime="text/markdown")
    if b2.button("Practice again (same settings)", type="primary"):
        setup = iv.setup
        ss.interview = Interview(setup=setup, turns=[opening_question(setup)])
        ss.q_audio, ss.played = {}, set()
        ss.pop("final", None)
        ss.stage = "interview"
        st.rerun()
    if b3.button("New interview setup"):
        ss.stage = "setup"
        st.rerun()
    st.caption("Scores are AI-generated practice feedback, not a prediction of real interview results.")


# ---------- router ----------
{"setup": setup_screen, "interview": interview_screen, "report": report_screen}[ss.stage]()
