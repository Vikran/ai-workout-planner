# AI Workout Planner

A single-page Streamlit app that turns structured inputs (goal, experience, days/week, equipment, injuries) into a weekly workout plan using the Groq API.

## Run

```
pip install -r requirements.txt
copy .env.example .env   # add your GROQ_API_KEY
streamlit run app.py
```

## How constraints are enforced

1. The system prompt sets hard rules: equipment, exact day count, injury avoidance, level scaling, no medical claims, fixed Markdown format.
2. `validate_plan()` checks the model's output in code (day count, banned equipment, injury-risk exercises) and asks the model to rewrite up to twice if any rule was broken.
3. A disclaimer is appended automatically whenever an injury or limitation is entered.

Extras: regenerate variation, plan kept in `st.session_state`, `.md` download, swap-one-exercise.
