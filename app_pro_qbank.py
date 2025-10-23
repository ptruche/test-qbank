import os
import time
import json
import random
from typing import List, Dict, Any
import pandas as pd
import streamlit as st

# -------------------- App/Theming --------------------
st.set_page_config(page_title="QBank Pro", page_icon="🧠", layout="wide")

# Minimal, tasteful CSS for pro look
st.markdown(
    """
    <style>
    :root {
      --card-bg: #ffffff;
      --card-border: #e6e8ec;
      --muted: #6b7280;
      --accent: #2563eb;
      --success: #059669;
      --danger: #dc2626;
      --warning: #d97706;
    }
    .q-card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 16px;
      padding: 1.25rem 1.25rem;
      box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }
    .q-chip {
      display: inline-block;
      padding: .2rem .55rem;
      border-radius: 999px;
      background: #f3f4f6;
      color: #111827;
      font-size: 0.8rem;
      margin-right: .4rem;
    }
    .q-subtle { color: var(--muted); }
    .q-progress {
      height: 10px;
      background: #e5e7eb;
      border-radius: 999px;
      overflow: hidden;
      margin: 4px 0 12px 0;
    }
    .q-progress > div {
      height: 100%;
      background: var(--accent);
      width: 0%;
      transition: width .3s ease;
    }
    .q-choice {
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: .9rem 1rem;
      margin-bottom: .6rem;
      cursor: pointer;
      transition: border-color .2s ease, background .2s ease;
    }
    .q-choice:hover { border-color: #cbd5e1; background: #fafafa; }
    .q-choice.correct { border-color: var(--success); background: #ecfdf5; }
    .q-choice.incorrect { border-color: var(--danger); background: #fef2f2; }
    .q-actions .stButton>button {
      border-radius: 12px;
      padding: .5rem .9rem;
    }
    .q-stat {
      border: 1px solid var(--card-border);
      border-radius: 12px;
      padding: .9rem 1rem;
      text-align: center;
    }
    .q-stat h3 { margin: 0; }
    .sticky-top {
      position: sticky;
      top: 0;
      z-index: 50;
      background: white;
      padding: .6rem .5rem .6rem .5rem;
      border-bottom: 1px solid #eef0f3;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------- Constants --------------------
REQUIRED_COLS = ["id", "subject", "stem", "A", "B", "C", "D", "E", "correct", "explanation"]

# -------------------- Helpers --------------------
def load_fixed_csv() -> pd.DataFrame:
    path = os.environ.get("QBANK_CSV_PATH", "questions.csv")
    try:
        return pd.read_csv(path)
    except Exception as e_local:
        RAW_URL = st.secrets.get("CSV_URL", os.environ.get("CSV_URL", ""))
        if RAW_URL:
            try:
                return pd.read_csv(RAW_URL)
            except Exception as e_url:
                st.error(f"Failed to load CSV from local path '{path}' and CSV_URL. Local error: {e_local}. URL error: {e_url}")
                return pd.DataFrame()
        st.error(f"Could not read local CSV '{path}'. Error: {e_local}")
        return pd.DataFrame()

def validate_df(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def build_quiz_pool(df: pd.DataFrame, subjects: List[str], difficulty: List[str], tags: List[str]) -> pd.DataFrame:
    out = df.copy()
    if subjects:
        out = out[out["subject"].astype(str).isin(subjects)]
    if difficulty and "difficulty" in out.columns:
        out = out[out["difficulty"].astype(str).isin(difficulty)]
    if tags and "tags" in out.columns:
        tag_set = set([t.strip().lower() for t in tags])
        def has_any(cell):
            if pd.isna(cell):
                return False
            cell_tags = [t.strip().lower() for t in str(cell).split(",")]
            return any(t in tag_set for t in cell_tags)
        out = out[out["tags"].apply(has_any)]
    return out.reset_index(drop=True)

def init_session_state(n: int):
    st.session_state.answers = [None] * n
    st.session_state.revealed = [False] * n
    st.session_state.correct_flags = [False] * n
    st.session_state.current = 0
    st.session_state.started_at = time.time()
    st.session_state.finished = False

def answer_letter_to_text(row: pd.Series, letter: str) -> str:
    return str(row[letter])

def choice_block(row: pd.Series, i: int, letter: str):
    # Determine CSS class for state
    css = "q-choice"
    if st.session_state.revealed[i]:
        correct_letter = str(row["correct"]).strip().upper()
        if letter == correct_letter:
            css += " correct"
        elif st.session_state.answers[i] == letter and letter != correct_letter:
            css += " incorrect"

    label = f"{letter}. {row[letter]}"
    clicked = st.button(label, key=f"choice_{i}_{letter}")
    if clicked and not st.session_state.revealed[i]:
        st.session_state.answers[i] = letter

    st.markdown(f"<div class='{css}'></div>", unsafe_allow_html=True)

def render_header(n: int):
    # Progress
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    cols = st.columns([3,2,3,2])
    with cols[0]:
        st.markdown(f"### 🧠 QBank Pro")
        st.caption("SBA (A–E) • Explanations • Bookmarks • Review")
    with cols[1]:
        st.caption("Progress")
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"{pos+1} / {n}")
    with cols[2]:
        elapsed = int(time.time() - st.session_state.started_at)
        mins, secs = divmod(elapsed, 60)
        st.caption("Elapsed")
        st.markdown(f"### {mins:02d}:{secs:02d}")
    with cols[3]:
        st.caption("Controls")
        c1, c2 = st.columns(2)
        if c1.button("⏭ Skip"):
            st.session_state.current = min(st.session_state.current + 1, n - 1)
        if c2.button("🏁 Finish"):
            st.session_state.finished = True
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    n = len(pool)
    row = pool.iloc[i]

    st.markdown("<div class='q-card'>", unsafe_allow_html=True)
    top = st.columns([5,1,1])
    with top[0]:
        st.markdown(f"#### Q{i+1} • {row['subject']}")
    with top[1]:
        st.markdown(f"<span class='q-chip'>ID {row['id']}</span>", unsafe_allow_html=True)
    with top[2]:
        tags = row.get("tags", "")
        if isinstance(tags, str) and tags.strip():
            st.markdown(" ".join([f"<span class='q-chip'>{t.strip()}</span>" for t in tags.split(',')]), unsafe_allow_html=True)

    st.markdown(str(row["stem"]))

    # Choices as columns (two rows: A-C then D-E)
    letters = ["A","B","C","D","E"]
    for chunk in (letters[:3], letters[3:]):
        cols = st.columns(len(chunk))
        for col, L in zip(cols, chunk):
            with col:
                # Show as buttons; select updates state
                btn = st.button(f"{L}. {row[L]}", key=f"btn_{i}_{L}")
                if btn and not st.session_state.revealed[i]:
                    st.session_state.answers[i] = L

    # Actions
    st.markdown("---")
    ac = st.columns([1,1,2,2,2])
    with ac[0]:
        if st.button("Reveal", key=f"reveal_{i}"):
            st.session_state.revealed[i] = True
            correct_letter = str(row["correct"]).strip().upper()
            st.session_state.correct_flags[i] = (st.session_state.answers[i] == correct_letter)
    with ac[1]:
        if st.button("Next ▶", key=f"next_{i}"):
            st.session_state.current = min(st.session_state.current + 1, n - 1)
    with ac[2]:
        if st.button("◀ Prev", key=f"prev_{i}"):
            st.session_state.current = max(st.session_state.current - 1, 0)
    with ac[3]:
        if st.button("Reset Question", key=f"reset_q_{i}"):
            st.session_state.answers[i] = None
            st.session_state.revealed[i] = False
            st.session_state.correct_flags[i] = False
    with ac[4]:
        pass

    # Feedback
    if st.session_state.revealed[i]:
        correct_letter = str(row["correct"]).strip().upper()
        is_correct = (st.session_state.answers[i] == correct_letter)
        st.markdown("---")
        st.markdown(f"**Correct:** {correct_letter}")
        if st.session_state.answers[i] is None:
            st.warning("No answer selected.")
        else:
            if is_correct:
                st.success("Correct ✅")
            else:
                st.error(f"Incorrect ❌ (you chose {st.session_state.answers[i]})")
        st.info(row["explanation"])

    st.markdown("</div>", unsafe_allow_html=True)

def render_results(pool: pd.DataFrame):
    n = len(pool)
    answers = st.session_state.answers
    revealed = st.session_state.revealed

    # Score counts only revealed items with an answer
    correct_letters = [str(x).strip().upper() for x in pool["correct"].tolist()]
    is_correct = [a == c and a is not None and r for a,c,r in zip(answers, correct_letters, revealed)]
    total_correct = sum(is_correct)
    total_answered = sum(1 for a,r in zip(answers, revealed) if a is not None and r)

    st.markdown("## Results")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("<div class='q-stat'><h3>Answered</h3><p style='font-size:1.4rem;'>"
                    f"{total_answered}/{n}</p></div>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown("<div class='q-stat'><h3>Correct</h3><p style='font-size:1.4rem;'>"
                    f"{total_correct}/{n}</p></div>", unsafe_allow_html=True)
    with cols[2]:
        pct = int(100 * total_correct / n) if n else 0
        st.markdown("<div class='q-stat'><h3>Score</h3><p style='font-size:1.4rem;'>"
                    f"{pct}%</p></div>", unsafe_allow_html=True)

    # Subject breakdown
    df = pool.copy()
    df["user_answer"] = answers
    df["revealed"] = revealed
    df["is_correct"] = is_correct

    st.markdown("### Breakdown by Subject")
    summary = (df[df["revealed"]]
               .groupby("subject")
               .agg(total=("id","count"),
                    correct=("is_correct","sum"))
               .reset_index())
    if not summary.empty:
        summary["percent"] = (summary["correct"] / summary["total"] * 100).round(1)
        st.dataframe(summary, use_container_width=True)
    else:
        st.caption("No revealed questions yet.")

    # Review table
    st.markdown("### Review")
    review_cols = ["#","subject","stem","user_answer","correct","explanation"]
    review = []
    for i,row in df.iterrows():
        review.append([i+1, row["subject"], str(row["stem"])[:140]+"…", row["user_answer"], row["correct"], str(row["explanation"])[:200]+"…"])
    st.dataframe(pd.DataFrame(review, columns=review_cols), use_container_width=True)

    st.download_button("⬇️ Export Progress (.json)",
                       data=json.dumps({
                           "answers": answers,
                           "revealed": revealed,
                           "current": st.session_state.current
                       }, indent=2).encode("utf-8"),
                       file_name="qbank_progress.json",
                       mime="application/json")

    if st.button("🔁 Restart Session"):
        init_session_state(len(pool))

# -------------------- Load Data --------------------
df = load_fixed_csv()
if df.empty:
    st.stop()
missing = validate_df(df)
if missing:
    st.error(f"CSV missing required columns: {missing}")
    st.stop()

if "difficulty" not in df.columns:
    df["difficulty"] = "Unlabeled"
if "tags" not in df.columns:
    df["tags"] = ""

# -------------------- Sidebar: Build Quiz --------------------
with st.sidebar:
    st.header("Build Your Quiz")
    subj_opts = sorted(df["subject"].dropna().astype(str).unique().tolist())
    diff_opts = sorted(df["difficulty"].dropna().astype(str).unique().tolist())
    tag_opts = sorted({t.strip() for cell in df["tags"].dropna().astype(str).tolist() for t in cell.split(",") if t.strip()})

    pick_subjects = st.multiselect("Subject", subj_opts)
    pick_diffs = st.multiselect("Difficulty", diff_opts)
    pick_tags = st.multiselect("Tags", tag_opts)
    n_questions = st.number_input("Number of Questions", min_value=5, max_value=200, step=5, value=min(20, len(df)))

    if st.button("Start Quiz ▶"):
        pool = build_quiz_pool(df, pick_subjects, pick_diffs, pick_tags)
        if pool.empty:
            st.warning("No questions match your filters.")
        else:
            if len(pool) > n_questions:
                pool = pool.sample(n=n_questions, random_state=42).reset_index(drop=True)
            else:
                pool = pool.sample(frac=1.0, random_state=42).reset_index(drop=True)
            st.session_state.pool = pool
            init_session_state(len(pool))

# -------------------- Main Stage --------------------
pool: pd.DataFrame = st.session_state.get("pool", None)
if pool is None:
    st.markdown("### Welcome to QBank Pro")
    st.write("Use the **Build Your Quiz** panel to select subjects/tags and press **Start Quiz**.")
    st.info("This app reads from a fixed `questions.csv` in the repo. Configure `QBANK_CSV_PATH` or `CSV_URL` to point elsewhere.")
    st.stop()

# Render header & question/results
render_header(len(pool))
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
