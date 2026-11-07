import os
import re

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

GOALS = ["Build muscle", "Lose fat", "General fitness", "Improve endurance"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
EQUIPMENT = ["No equipment", "Home dumbbells", "Full gym"]

SYSTEM_PROMPT = """You are an experienced, certified personal trainer writing a weekly workout plan.

HARD RULES (never break these):
1. Use ONLY exercises possible with the stated equipment. "No equipment" means bodyweight only; \
"Home dumbbells" means dumbbells and bodyweight only (no barbells, machines, cables, benches unless improvised).
2. Create EXACTLY the number of training days requested, no more, no fewer. Do not list rest days as workout days; \
mention rest days in one short line at the end.
3. If limitations or injuries are listed, do not include any exercise that loads or stresses that area. \
Pick safe substitutes and state in one line per affected day what you avoided.
4. Scale volume and exercise complexity to the experience level (beginners: simple compound/machine-free \
movements, 2-3 sets, lower volume; advanced: higher volume, harder variations).
5. Match the plan to the goal (muscle: 6-12 reps hypertrophy ranges; fat loss: strength plus conditioning; \
endurance: higher reps, intervals, steady-state work; general fitness: balanced mix).
6. Split muscle groups sensibly across days; avoid training the same muscle group hard on consecutive days.
7. Stay in scope: no medical claims, no diagnosis, no supplement or diet prescriptions.

OUTPUT FORMAT (Markdown, nothing before or after it):
## Plan Overview
One or two sentences on the approach.

### Day 1 - <focus>
**Warm-up:** <one line>
| Exercise | Sets | Reps | Rest |
|---|---|---|---|
| ... | ... | ... | ... |
**Notes:** <one short tip, include any injury modification here>

(repeat for each day)

### Rest & Recovery
One or two lines.

If any injury or limitation was provided, end with this exact line:
> *Disclaimer: This plan is general fitness information, not medical advice. Consult a doctor or physiotherapist before \
starting, especially with an existing injury.*
"""


def get_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["GROQ_API_KEY"]
        except Exception:
            api_key = None
    if not api_key:
        raise ValueError("Missing GROQ_API_KEY")
    return Groq(api_key=api_key)


def call_llm(system: str, user: str, temperature: float) -> str:
    completion = get_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=6000,
    )
    return completion.choices[0].message.content.strip()


def friendly_error(exc: Exception) -> str:
    text = str(exc).lower()
    if isinstance(exc, ValueError) or "api key" in text or "401" in text or "invalid_api_key" in text:
        return "Your Groq API key is missing or invalid. Add `GROQ_API_KEY` to a `.env` file and restart the app."
    if "429" in text or "rate limit" in text:
        return "Groq's rate limit was hit. Please wait a moment and try again."
    if "connection" in text or "timeout" in text or "network" in text:
        return "Couldn't reach Groq. Check your internet connection and try again."
    return f"Something went wrong while generating your plan. Please try again. (Details: {type(exc).__name__}: {str(exc)[:300]})"


def build_user_prompt(
    goal: str,
    level: str,
    days: int,
    equipment: str,
    limitations: str,
    variation: bool = False,
) -> str:
    limits = limitations.strip() or "None"
    prompt = (
        f"Create a {days}-day weekly workout plan.\n"
        f"- Goal: {goal}\n"
        f"- Experience level: {level}\n"
        f"- Training days per week: {days} (output exactly {days} day sections)\n"
        f"- Equipment: {equipment}\n"
        f"- Injuries/limitations: {limits}"
    )
    if variation:
        prompt += "\n\nProvide a noticeably different variation from a typical plan: different exercise selection and split."
    return prompt


DISCLAIMER = (
    "> *Disclaimer: This plan is general fitness information, not medical advice. "
    "Consult a doctor or physiotherapist before starting, especially with an existing injury.*"
)

BANNED_EQUIPMENT = {
    "No equipment": ["dumbbell", "barbell", "kettlebell", "cable", "machine", "bench press", "lat pulldown", "leg press"],
    "Home dumbbells": ["barbell", "cable", "machine", "lat pulldown", "leg press", "smith"],
}

# Limitation keyword -> exercises that commonly stress that area
INJURY_BANS = {
    "knee": ["lunge", "jump squat", "box jump", "burpee", "pistol", "deep squat", "jumping"],
    "shoulder": ["overhead press", "shoulder press", "military press", "handstand", "upright row", "arnold press"],
    "overhead": ["overhead press", "shoulder press", "military press", "handstand", "arnold press", "pike push"],
    "back": ["deadlift", "good morning", "bent-over row", "bent over row", "sit-up", "russian twist"],
    "wrist": ["push-up", "pushup", "plank", "handstand", "burpee"],
    "ankle": ["jump", "skipping", "burpee", "box jump", "sprint"],
}


def validate_plan(plan: str, days: int, equipment: str, limitations: str) -> list[str]:
    """Return a list of constraint violations found in the plan (empty if it complies)."""
    problems: list[str] = []
    lowered = plan.lower()

    day_count = len(re.findall(r"^#{2,4}\s*day\s*\d+", plan, flags=re.IGNORECASE | re.MULTILINE))
    if day_count != days:
        problems.append(f"The plan has {day_count} training days but exactly {days} are required.")

    for word in BANNED_EQUIPMENT.get(equipment, []):
        if word in lowered:
            problems.append(f"It uses '{word}', which is not available with equipment '{equipment}'.")

    for key, bans in INJURY_BANS.items():
        if key in limitations.lower():
            for word in bans:
                if word in lowered:
                    problems.append(f"It includes '{word}', which conflicts with the limitation '{key}'.")
    return problems


def generate_plan(
    goal: str,
    level: str,
    days: int,
    equipment: str,
    limitations: str = "",
    variation: bool = False,
) -> str:
    """Generate a weekly workout plan via Groq. Returns Markdown, or a friendly error string prefixed with 'ERROR:'."""
    if days < 1:
        return "ERROR: Please select at least 1 training day per week."
    try:
        user_prompt = build_user_prompt(goal, level, days, equipment, limitations, variation)
        temperature = 0.9 if variation else 0.6
        plan = call_llm(SYSTEM_PROMPT, user_prompt, temperature)

        # Verify the constraints in code; if the model broke any, ask it to fix them (up to 2 retries).
        for _ in range(2):
            problems = validate_plan(plan, days, equipment, limitations)
            if not problems:
                break
            fix = (
                f"{user_prompt}\n\nYour previous draft violated the constraints:\n- "
                + "\n- ".join(problems)
                + "\n\nRewrite the full plan fixing every issue, keeping the same format."
            )
            plan = call_llm(SYSTEM_PROMPT, fix, temperature=0.4)

        if limitations.strip() and DISCLAIMER not in plan:
            plan = f"{plan.rstrip()}\n\n{DISCLAIMER}"
        return plan
    except Exception as exc:
        return f"ERROR: {friendly_error(exc)}"


def swap_exercise(plan: str, exercise: str, equipment: str, limitations: str = "") -> str:
    """Replace one exercise in an existing plan. Returns the full updated plan, or 'ERROR: ...'."""
    if not exercise.strip():
        return "ERROR: Please enter the exercise you want to swap."
    system = (
        "You edit workout plans. Replace ONLY the requested exercise with a similar one targeting the same muscles, "
        f"using only this equipment: {equipment}. Injuries/limitations to respect: {limitations.strip() or 'None'}. "
        "Keep everything else identical and keep the exact Markdown format. Return the full updated plan only."
    )
    user = f"Swap out '{exercise}' in this plan:\n\n{plan}"
    try:
        return call_llm(system, user, temperature=0.7)
    except Exception as exc:
        return f"ERROR: {friendly_error(exc)}"


def run_generation(inputs: dict, variation: bool) -> bool:
    with st.spinner("Building your plan..."):
        result = generate_plan(**inputs, variation=variation)
    if result.startswith("ERROR:"):
        st.error(result.removeprefix("ERROR:").strip())
        return False
    st.session_state.plan = result
    st.session_state.inputs = inputs
    return True


def main() -> None:
    st.set_page_config(page_title="AI Workout Planner", page_icon="🏋️", layout="centered")
    st.title("🏋️ AI Workout Planner")
    st.caption("Tell us about yourself and get a weekly plan built around your constraints.")

    with st.sidebar:
        st.header("About you")
        goal = st.selectbox("Fitness goal", GOALS)
        level = st.selectbox("Experience level", LEVELS)
        days = st.slider("Days available per week", 0, 7, 3)
        equipment = st.selectbox("Equipment access", EQUIPMENT)
        limitations = st.text_area(
            "Injuries or limitations (optional)",
            placeholder='e.g. "bad knees", "no overhead pressing"',
        )
        generate = st.button("Generate Plan", type="primary", use_container_width=True)

    inputs = {
        "goal": goal,
        "level": level,
        "days": days,
        "equipment": equipment,
        "limitations": limitations,
    }

    if generate:
        if days == 0:
            st.warning("Select at least 1 day per week to generate a plan.")
        else:
            run_generation(inputs, variation=False)

    plan = st.session_state.get("plan")
    if not plan:
        st.info("Fill in your details in the sidebar and click **Generate Plan**.")
        return

    st.markdown(plan)
    st.divider()
    saved = st.session_state.get("inputs", inputs)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Regenerate (new variation)", use_container_width=True):
            if run_generation(saved, variation=True):
                st.rerun()
    with col2:
        st.download_button(
            "⬇️ Download as .md",
            data=plan,
            file_name="workout_plan.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with st.expander("Swap an exercise"):
        exercise = st.text_input("Exercise to replace", placeholder="e.g. Goblet squat")
        if st.button("Swap it"):
            with st.spinner("Finding a replacement..."):
                updated = swap_exercise(plan, exercise, saved["equipment"], saved["limitations"])
            if updated.startswith("ERROR:"):
                st.error(updated.removeprefix("ERROR:").strip())
            else:
                st.session_state.plan = updated
                st.rerun()


if __name__ == "__main__":
    main()
