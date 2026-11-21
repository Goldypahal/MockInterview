"""The AI interviewer.

To save free-tier quota, each answer needs only ONE Gemini call, which:
  1. transcribes the spoken answer word for word (keeping "um", "uh" ...),
  2. scores the answer for content and clarity, and
  3. decides the next step: a follow-up question, a new question, or ending the interview.
A final call at the end writes the overall feedback.
"""

import json
from dataclasses import dataclass, field

from google.genai import types

from gemini_client import generate
from roles import INTERVIEW_TYPES, ROLES

MAX_FOLLOW_UPS_PER_QUESTION = 1


@dataclass
class InterviewSetup:
    role: str
    level: str
    interview_type: str
    num_questions: int = 5
    candidate_name: str = ""
    resume_text: str = ""
    job_description: str = ""

    def focus(self) -> str:
        return ROLES.get(self.role, f"Skills commonly needed for a {self.role} role.")


@dataclass
class Turn:
    question: str
    kind: str                      # "opening", "new_question" or "follow_up"
    topic: str = ""
    answer: str = ""               # transcript (spoken) or typed text
    answered_by: str = ""          # "voice", "typed" or "skipped"
    content: int | None = None     # 1–10
    clarity: int | None = None     # 1–10
    strengths: str = ""
    improvement: str = ""
    metrics: dict | None = None    # speaking metrics (voice answers only)
    model: str = ""


@dataclass
class Interview:
    setup: InterviewSetup
    turns: list[Turn] = field(default_factory=list)
    finished: bool = False

    @property
    def main_questions_asked(self) -> int:
        return sum(1 for t in self.turns if t.kind != "follow_up")

    @property
    def current(self) -> Turn:
        return self.turns[-1]


# ---------- prompts ----------

INTERVIEWER_RULES = """You are "Saathi", a friendly but professional campus-placement interviewer in India.
You are interviewing a candidate for the role of {role} ({level}).
Interview type: {itype} {itype_rule}
Topics to cover for this role: {focus}
{resume_block}{jd_block}
RULES FOR YOUR QUESTIONS
- Ask ONE clear question at a time, in simple spoken English (it will be read aloud), under 40 words.
- Start easy and increase difficulty if the candidate answers well; make it easier if they struggle.
- Do not repeat a topic that has already been covered.
- Use a follow-up only when the last answer was vague, incomplete or interesting enough to probe
  (for example "Can you give an example?" or "Why did you choose that approach?").
- No coding on paper: for technical topics ask the candidate to explain concepts, approaches or trade-offs.
- Never reveal the scores to the candidate during the interview, and never be rude.

HOW TO SCORE EACH ANSWER (be fair and specific, like a real interviewer)
- content (1–10): correctness, depth and relevance to the question. 1–3 wrong or off-topic,
  4–6 partly correct or shallow, 7–8 correct with some depth, 9–10 excellent with examples.
- clarity (1–10): structure and how easy it is to follow (logical order, to the point, complete sentences).
  Ignore accent and minor grammar mistakes; judge communication, not English level.
- strengths: one short sentence. improvement: one short, actionable sentence.
- If the candidate skipped the question or said they don't know, give content 1 and clarity 1, and
  suggest what they could have said.
"""

TURN_INSTRUCTIONS = """INTERVIEW SO FAR:
{history}

CURRENT QUESTION ({kind}): {question}

{answer_block}

YOUR TASK
1. transcript: {transcript_rule}
2. Score the answer to the CURRENT QUESTION (content, clarity, strengths, improvement).
3. Decide the next step (next_kind):
   - "follow_up" (allowed now: {follow_up_allowed}) to probe the same answer,
   - "new_question" (main questions asked: {asked} of {total}),
   - "end" ONLY if {asked} >= {total} and no follow-up is needed.
   Then write next_question (empty if ending) and next_topic (2–4 words)."""

TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "content": {"type": "integer"},
        "clarity": {"type": "integer"},
        "strengths": {"type": "string"},
        "improvement": {"type": "string"},
        "next_kind": {"type": "string", "enum": ["follow_up", "new_question", "end"]},
        "next_question": {"type": "string"},
        "next_topic": {"type": "string"},
    },
    "required": ["transcript", "content", "clarity", "strengths", "improvement", "next_kind", "next_question"],
}

FINAL_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "weakest_question": {"type": "string"},
        "better_answer": {"type": "string"},
        "topics_to_revise": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "strengths", "improvements", "weakest_question", "better_answer", "topics_to_revise"],
}


def _rules(setup: InterviewSetup) -> str:
    resume = setup.resume_text.strip()[:3500]
    jd = setup.job_description.strip()[:2000]
    return INTERVIEWER_RULES.format(
        role=setup.role, level=setup.level, itype=setup.interview_type,
        itype_rule=INTERVIEW_TYPES.get(setup.interview_type, ""), focus=setup.focus(),
        resume_block=(f"\nCANDIDATE'S RESUME (ask about their projects and skills from it):\n{resume}\n" if resume else ""),
        jd_block=(f"\nJOB DESCRIPTION (tailor questions to it):\n{jd}\n" if jd else ""),
    )


def _history(interview: Interview) -> str:
    done = [t for t in interview.turns[:-1] if t.answered_by]
    if not done:
        return "(this is the first question)"
    return "\n".join(f"Q{i + 1} [{t.kind}, topic: {t.topic or '-'}]: {t.question}\nA: {t.answer or '(skipped)'}"
                     for i, t in enumerate(done))


def opening_question(setup: InterviewSetup) -> Turn:
    """The first question is always an introduction, so it needs no AI call."""
    name = f", {setup.candidate_name.split()[0]}" if setup.candidate_name.strip() else ""
    role = setup.role.replace(" (any role)", "")
    return Turn(question=f"Hello{name}, welcome to your mock interview. To begin, please introduce yourself "
                         f"and tell me why you are interested in this {role} role.",
                kind="opening", topic="Introduction")


def _clamp(v, lo=1, hi=10):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return None


def submit_answer(interview: Interview, *, audio_wav: bytes | None = None, typed: str | None = None,
                  skipped: bool = False) -> Turn:
    """Process the answer to the current question and add the next question (if any).

    Returns the answered turn. Sets interview.finished when the interview is over.
    """
    turn = interview.current
    follow_ups_in_a_row = 0
    for t in reversed(interview.turns[:-1] + [turn]):
        if t.kind == "follow_up":
            follow_ups_in_a_row += 1
        else:
            break
    follow_up_allowed = follow_ups_in_a_row < MAX_FOLLOW_UPS_PER_QUESTION and not skipped
    asked, total = interview.main_questions_asked, interview.setup.num_questions

    if skipped:
        answer_block, transcript_rule = "The candidate SKIPPED this question.", 'return "(skipped)".'
    elif audio_wav is not None:
        answer_block = "The candidate's spoken answer is the attached audio."
        transcript_rule = ("transcribe the audio EXACTLY as spoken, word for word. KEEP every filler word and "
                           "hesitation (um, uh, er, hmm, like, you know, basically, actually), repeated words "
                           "and false starts. Do not correct grammar. If there is no speech, return an empty string.")
    else:
        answer_block = f"The candidate's typed answer:\n{typed}"
        transcript_rule = "copy the typed answer exactly."

    prompt = TURN_INSTRUCTIONS.format(
        history=_history(interview), kind=turn.kind, question=turn.question, answer_block=answer_block,
        transcript_rule=transcript_rule, follow_up_allowed="yes" if follow_up_allowed else "NO",
        asked=asked, total=total,
    )
    contents = [types.Part.from_bytes(data=audio_wav, mime_type="audio/wav"), prompt] if audio_wav is not None else [prompt]

    response, model = generate(
        contents=contents,
        gen_config=types.GenerateContentConfig(
            system_instruction=_rules(interview.setup),
            temperature=0.4,               # some variety in questions, consistent scoring
            response_mime_type="application/json",
            response_schema=TURN_SCHEMA,
        ),
    )
    data = json.loads((response.text or "{}").strip().strip("`").removeprefix("json"))

    turn.answer = (typed if typed is not None else data.get("transcript", "")).strip()
    if skipped:
        turn.answer = ""
    turn.answered_by = "skipped" if skipped else ("voice" if audio_wav is not None else "typed")
    turn.content, turn.clarity = _clamp(data.get("content")), _clamp(data.get("clarity"))
    turn.strengths, turn.improvement = data.get("strengths", ""), data.get("improvement", "")
    turn.model = model

    # Decide what comes next, enforcing the limits even if the model ignores them.
    kind = data.get("next_kind", "new_question")
    question = (data.get("next_question") or "").strip()
    if kind == "follow_up" and not follow_up_allowed:
        kind = "new_question" if asked < total else "end"
    if kind == "new_question" and asked >= total:
        kind = "end"
    if kind == "end" and asked < total:
        kind = "new_question"      # the model ended too early: keep going
    if kind != "end" and not question:
        kind = "end" if asked >= total else kind
        question = question or "Can you tell me about a project you are proud of and your role in it?"

    if kind == "end":
        interview.finished = True
    else:
        interview.turns.append(Turn(question=question, kind=kind, topic=data.get("next_topic", "")))
    return turn


def final_feedback(interview: Interview) -> dict:
    """Overall written feedback for the scorecard (one AI call)."""
    answered = [t for t in interview.turns if t.answered_by]
    lines = [f"Q{i + 1} ({t.kind}): {t.question}\nA ({t.answered_by}): {t.answer or '(skipped)'}\n"
             f"Scores: content {t.content}/10, clarity {t.clarity}/10"
             + (f", fillers {t.metrics['filler_count']}, pace {t.metrics['wpm']} wpm" if t.metrics else "")
             for i, t in enumerate(answered)]
    prompt = ("Write the final feedback for this mock interview, as a supportive placement coach.\n"
              "summary: 3–4 sentences on overall performance and readiness.\n"
              "strengths: 3 specific strengths. improvements: 3 specific, actionable improvements.\n"
              "weakest_question: copy the question with the weakest answer.\n"
              "better_answer: a strong model answer to that question (80–150 words, in first person, as the "
              "candidate could say it).\n"
              "topics_to_revise: 3–5 topics to study before the real interview.\n\n" + "\n\n".join(lines))
    response, _ = generate(
        contents=[prompt],
        gen_config=types.GenerateContentConfig(
            system_instruction=_rules(interview.setup), temperature=0.4,
            response_mime_type="application/json", response_schema=FINAL_SCHEMA,
        ),
        prefer_light=False,
    )
    return json.loads((response.text or "{}").strip().strip("`").removeprefix("json"))
