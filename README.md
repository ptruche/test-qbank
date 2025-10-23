# Mini QBank (TrueLearn-style) — Streamlit + CSV

A tiny, reliable question bank you can deploy for free on Streamlit Community Cloud.
- Single-best-answer (A–E) format
- Loads questions from a CSV (upload or raw GitHub URL)
- Filters by subject, difficulty, tags
- Shuffle, bookmarks, reveal answers, explanations
- Export/import session progress (.json)

## Files
- `app.py` — the Streamlit app
- `requirements.txt` — Python deps for Streamlit Cloud
- `questions_sample.csv` — example question set

## CSV Schema (required headers)
```text
id,subject,stem,A,B,C,D,E,correct,explanation
```
Optional: `difficulty`, `tags`

## Quick Start (Local)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy to Streamlit Community Cloud
1. Create a new GitHub repo and add all three files.
2. Go to https://share.streamlit.io/ (sign in) → "New app".
3. Choose your repo/branch and set **Main file path** to `app.py`.
4. Deploy. When it opens, upload your CSV or paste the **raw** GitHub CSV URL.

### Raw CSV URL example
If your CSV lives at `https://github.com/you/qbank/blob/main/questions.csv`, click the **Raw** button and copy that URL (it will look like `https://raw.githubusercontent.com/you/qbank/main/questions.csv`). Paste that into the app.
