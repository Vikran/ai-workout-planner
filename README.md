# AI Workout Planner

A single-page Streamlit app that turns structured inputs (goal, experience level, days per week, equipment, injuries/limitations) into a personalized weekly workout plan using an LLM through the **Groq API**.

## Setup

1. Get a free API key at https://console.groq.com (keys start with `gsk_`).
2. Install and run:

```
python -m venv .venv
.venv\Scripts\activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
# edit .env and set GROQ_API_KEY=gsk_...
streamlit run app.py
```

The app reads `.env` at startup, so restart it after changing the file. On Streamlit Cloud you can set `GROQ_API_KEY` under Secrets instead.

## LLM and model

All LLM calls go through the Groq SDK (`groq` package) using your `GROQ_API_KEY`. The default model is `openai/gpt-oss-120b`, an open-weights model hosted on Groq. Override it with `GROQ_MODEL` in `.env`.

## How constraints are enforced

1. **Prompt design:** the system prompt sets hard rules: use only the stated equipment, produce exactly the requested number of days, avoid exercises that stress listed injuries, scale to experience level, match the goal, make no medical claims, and follow a fixed Markdown format (a table of exercises, sets, reps and rest for each day).
2. **Code validation:** `validate_plan()` checks the output for day count, unavailable equipment and injury-risk exercises. If any rule is broken, the model is asked to rewrite the plan, up to twice.
3. **Disclaimer:** appended automatically whenever an injury or limitation is entered.
4. **Error handling:** 0 days selected, a missing or invalid key, rate limits and network failures all show friendly messages instead of crashing.

Extras: regenerate a different variation, the plan persists in `st.session_state`, download as `.md`, and swap a single exercise.

## Caveats

- **Available models vary by account.** Groq retires and adds models. If you see a `model_not_found` error, list your models and set `GROQ_MODEL`:
  `python -c "from dotenv import load_dotenv; load_dotenv(); from groq import Groq; print(*[m.id for m in Groq().models.list().data], sep='\n')"`
- **The injury and equipment checks are keyword-based.** They cover knee, shoulder, overhead, back, wrist and ankle, and common equipment terms. They reduce violations but can't guarantee a plan is safe or fully compliant, so the output is not verified beyond that.
- **Not medical advice.** Plans are general fitness information. Consult a doctor or physiotherapist, especially with an existing injury.
- **Rate limits and cost.** Groq's free tier is rate-limited. Each plan can take up to three LLM calls if validation triggers rewrites, and the swap feature adds one more.
- **Swap exercise** returns the whole plan rewritten by the model, and the result isn't re-validated against the constraints.
- **Output varies.** LLM output is non-deterministic, so two runs with the same inputs can differ.
