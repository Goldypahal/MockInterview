# 🎤 Interview Saathi: Voice Mock-Interview Coach for Placements

Practise placement interviews by voice. Pick a role, and the AI interviewer **asks questions out loud**,
**listens to your spoken answers**, asks **follow-up questions** when an answer needs more depth, and at the
end gives you a **scorecard**: content, clarity and fluency, including filler words like "um" and "basically"
and your speaking pace.

Runs on the **free Google Gemini API** (the same key as Notice Board Saathi). No credit card needed.

## Features

- **Roles:** Python Developer, Data Analyst, ML Engineer, AI/GenAI Engineer, SDE, Full Stack, Java,
  Cloud/DevOps, HR round, or any role you type
- **Interview types:** Technical, HR/Behavioural or Mixed. Levels: Fresher to 5 years
- **Personalised:** upload your resume (PDF) and/or paste a job description, and it asks about *your* projects
- **Real conversation:** the question is spoken aloud. You answer with the mic (or type), and it decides
  whether to ask a follow-up (max one per question) or move on, getting harder if you answer well
- **Scorecard:**
  - Overall score out of 100 and readiness (Ready / Almost ready / Needs more practice)
  - Content and clarity score for each answer, with a chart
  - Filler words counted (um, uh, basically, you know, actually, …) and your most-used ones
  - Speaking pace in words per minute (comfortable range: 110–160)
  - Strengths, improvements, topics to revise, and a **model answer** to your weakest question
  - Download the scorecard as a file
- Optional **quick feedback after each answer**, or keep it off for a realistic interview

## How it works

```
Question (text) ──gTTS──► spoken aloud ──► you answer on the mic
                                               │
              one Gemini call per answer ◄──────┘
              • transcribes word for word (keeps "um", "uh")
              • scores content and clarity (1–10)
              • decides: follow-up / new question / end
                                               │
   metrics.py (local, no AI): filler words, words per minute, fluency score
                                               │
   end of interview: one more Gemini call for written feedback and the model answer
```

A 5-question interview uses only about **6–11 free requests**: one per answer plus one for the final feedback.
The first question ("introduce yourself") needs no AI call.

### Scoring

| Score | How it's calculated |
|---|---|
| Content | AI rates correctness, depth and relevance, 1–10 per answer → average × 10 |
| Clarity | AI rates structure and how easy it is to follow, 1–10 → average × 10 (accent and minor grammar are ignored) |
| Fluency | Calculated locally: starts at 100, minus 10 per filler word per 100 words (max −60), minus points if your pace is outside 110–160 wpm (max −30). Voice answers only |
| Overall | 50% content + 30% clarity + 20% fluency (60/40 content and clarity if you only typed) |

## Setup (Windows)

```
cd "%USERPROFILE%\Desktop\interview-saathi"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Your Gemini key has already been copied into `.env` from Notice Board Saathi. If it's missing, copy
`.env.example` to `.env` and paste your key from https://aistudio.google.com/apikey.

## Tips for a good practice session

- Use **headphones** so the interviewer's voice isn't picked up by your mic.
- Click the mic, answer, then click it again to stop. The answer is sent automatically.
- Aim for answers of 30–90 seconds. For HR questions, use **STAR** (Situation, Task, Action, Result).
- Practise the same role several times with **Practice again** and watch your scores and filler count improve.

## Project files

| File | What it does |
|---|---|
| `app.py` | Streamlit app: setup screen, interview screen, scorecard |
| `interviewer.py` | The AI interviewer: prompts, scoring rules, follow-up logic, final feedback |
| `metrics.py` | Filler words, speaking pace and fluency score (no AI) |
| `roles.py` | Roles, levels and interview types, with the topics for each role |
| `voice.py` | The interviewer's voice (gTTS) |
| `gemini_client.py` | Gemini connection with automatic model fallback when a free quota runs out |
| `config.py` | Settings from `.env` |

## Troubleshooting

| Problem | Fix |
|---|---|
| No sound | Check volume. Some browsers block autoplay, so press play on the audio bar |
| Mic does nothing | Allow microphone access in the browser and in Windows Settings > Privacy > Microphone |
| "Couldn't hear any words" | Speak right after clicking the mic and stay close to it |
| Free limit used up | Each model allows about 20 requests a day. The app switches models automatically, and limits reset around 1:30 PM India time |
| Filler words not counted | The AI is told to transcribe word for word, but it can occasionally tidy up speech, so the count is an estimate |

## AI-901 concepts used

Generative AI and prompt engineering (`interviewer.py`), speech recognition through multimodal audio input,
speech synthesis (`voice.py`), structured JSON output, model configuration (temperature 0.4), an agent-like
decision loop (follow-up, new question or end), and responsible AI (fair scoring rules that ignore accent,
and a clear note that scores are practice feedback).

> Scores are AI-generated practice feedback, not a prediction of real interview results.
