import io
import json
import random
from typing import List, Dict

import pandas as pd
import streamlit as st

# ---------- Page Setup ----------
st.set_page_config(
    page_title="Mini QBank (TrueLearn-style)",
    page_icon="🧠",
    layout="wide"
)

# ---------- Helper Functions ----------
REQUIRED_COLS = ["id", "subject", "stem", "A", "B", "C", "D", "E", "correct", "explanation"]

def validate_df(df: pd.DataFrame) -> List[str]:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return missing

def load_questions_from_csv(file_or_url) -> pd.DataFrame:
    try:
        if isinstance(file_or_url, str):
            df = pd.read_csv(file_or_url)
        else:
            df = pd.read_csv(file_or_url)
        return df
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return pd.DataFrame()

def filter_df(df: pd.DataFrame, subjects: List[str], difficulties: List[str], tags: List[str]) -> pd.DataFrame:
    out = df.copy()
    if subjects:
        out = out[out["subject"].astype(str).isin(subjects)]
    if difficulties:
        out = out[out["difficulty"].astype(str).isin(difficulties)]
    if tags:
        # For tags, allow contains-any match (case-insensitive); split tags on comma in the CSV
        tag_set = set([t.strip().lower() for t in tags])
        def has_any(cell):
            if pd.isna(cell):
                return False
            cell_tags = [t.strip().lower() for t in str(cell).split(",")]
            return any(t in tag_set for t in cell_tags)
        out = out[out["tags"].apply(has_any)]
    return out

def ensure_session_lists(n: int):
    st.session_state.answers = st.session_state.get("answers", [None] * n)
    st.session_state.revealed = st.session_state.get("revealed", [False] * n)
    st.session_state.bookmarks = st.session_state.get("bookmarks", [False] * n)

def export_progress(df: pd.DataFrame) -> bytes:
    payload = {
        "answers": st.session_state.answers,
        "revealed": st.session_state.revealed,
        "bookmarks": st.session_state.bookmarks,
        "order_index": st.session_state.get("order_index", list(range(len(df)))),
        "current_idx": st.session_state.get("current_idx", 0),
        "meta": {"n_questions": len(df)},
    }
    return json.dumps(payload, indent=2).encode("utf-8")

def import_progress(payload: bytes, n_questions: int):
    try:
        obj = json.loads(payload.decode("utf-8"))
        # Basic sanity checks
        if obj.get("meta", {}).get("n_questions") != n_questions:
            st.warning("Progress file does not match the number of loaded questions. Ignoring.")
            return
        st.session_state.answers = obj.get("answers", [None] * n_questions)
        st.session_state.revealed = obj.get("revealed", [False] * n_questions)
        st.session_state.bookmarks = obj.get("bookmarks", [False] * n_questions)
        st.session_state.order_index = obj.get("order_index", list(range(n_questions)))
        st.session_state.current_idx = obj.get("current_idx", 0)
        st.success("Progress imported.")
    except Exception as e:
        st.error(f"Could not import progress: {e}")

def show_question(q_row: pd.Series, idx: int, total: int):
    st.markdown(f"### Q{idx+1} / {total} — {q_row['subject']}")
    st.markdown(q_row["stem"])

    options = ["A", "B", "C", "D", "E"]
    labels = [f"A. {q_row['A']}", f"B. {q_row['B']}", f"C. {q_row['C']}", f"D. {q_row['D']}", f"E. {q_row['E']}"]

    current_answer = st.session_state.answers[idx]
    chosen = st.radio("Choose one", options, index=options.index(current_answer) if current_answer in options else None, label_visibility="collapsed", captions=labels)
    st.session_state.answers[idx] = chosen

    cols = st.columns(4)
    with cols[0]:
        if st.button("Reveal", key=f"reveal_{idx}"):
            st.session_state.revealed[idx] = True
    with cols[1]:
        st.session_state.bookmarks[idx] = st.toggle("Bookmark", value=st.session_state.bookmarks[idx], key=f"bm_{idx}")
    with cols[2]:
        if st.button("Prev", key=f"prev_{idx}"):
            st.session_state.current_idx = max(0, st.session_state.current_idx - 1)
    with cols[3]:
        if st.button("Next", key=f"next_{idx}"):
            st.session_state.current_idx = min(total - 1, st.session_state.current_idx + 1)

    if st.session_state.revealed[idx]:
        correct_letter = str(q_row["correct"]).strip().upper()
        is_correct = (st.session_state.answers[idx] == correct_letter)
        st.markdown("---")
        st.subheader("Answer & Explanation")
        st.markdown(f"**Correct answer: {correct_letter}**")
        if st.session_state.answers[idx] is not None:
            st.markdown(f"**Your answer: {st.session_state.answers[idx]}** {'✅' if is_correct else '❌'}")
        st.markdown(q_row["explanation"])

def summarize_results(df: pd.DataFrame):
    n = len(df)
    if n == 0:
        st.info("No questions loaded.")
        return
    correct_letters = [str(x).strip().upper() for x in df["correct"].tolist()]
    chosen = st.session_state.answers
    revealed = st.session_state.revealed

    total_answered = sum(1 for a in chosen if a is not None)
    total_revealed = sum(1 for r in revealed if r)
    total_correct = sum(1 for a, c in zip(chosen, correct_letters) if a == c and a is not None)

    st.metric("Answered", f"{total_answered}/{n}")
    st.metric("Revealed", f"{total_revealed}/{n}")
    st.metric("Correct", f"{total_correct}/{n}")

    # Show a small table of incorrect answers for review
    rows = []
    for i, (a, c) in enumerate(zip(chosen, correct_letters)):
        if a is not None and a != c:
            rows.append({
                "Q#": i+1,
                "Your": a,
                "Correct": c,
                "Subject": df.iloc[i]["subject"],
                "Stem (first 80 chars)": (str(df.iloc[i]["stem"])[:80] + "...") if len(str(df.iloc[i]["stem"])) > 80 else str(df.iloc[i]["stem"]),
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.success("No incorrect answers so far.")

# ---------- Sidebar: Data Loading ----------
st.sidebar.header("1) Load questions")
example_url = "https://raw.githubusercontent.com/streamlit/example-data/main/qbank/questions_sample.csv"
load_choice = st.sidebar.radio(
    "Source:",
    ["Upload CSV", "From URL (raw CSV)"],
    help="Upload your own CSV or load from a raw GitHub CSV URL."
)

df = pd.DataFrame()
if load_choice == "Upload CSV":
    uploaded = st.sidebar.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df = load_questions_from_csv(uploaded)
else:
    url = st.sidebar.text_input("Raw CSV URL", value="")
    if url:
        df = load_questions_from_csv(url)

# ---------- Sidebar: Options ----------
st.sidebar.header("2) Options")
shuffle = st.sidebar.toggle("Shuffle order", value=True)
exam_mode = st.sidebar.toggle("Exam mode (hide explanations until revealed)", value=True)
st.session_state.exam_mode = exam_mode

# ---------- Main ----------
st.title("🧠 Mini QBank")
st.caption("Lightweight, TrueLearn-style single-best-answer question bank.")

with st.expander("CSV format (required columns)"):
    st.markdown("""
    Your CSV **must include** these column headers (case-sensitive):
    - `id`, `subject`, `stem`, `A`, `B`, `C`, `D`, `E`, `correct`, `explanation`
    Optional columns:
    - `difficulty` (e.g., 'Easy', 'Medium', 'Hard')
    - `tags` (comma-separated, e.g., 'BA, Kasai, neonatal')
    """)

if df.empty:
    st.info("Load a CSV to begin. You can use the sample in the GitHub repo to test.")
    st.stop()

# Validate columns
missing = validate_df(df)
if missing:
    st.error(f"CSV is missing required columns: {missing}")
    st.stop()

# Normalize optional columns
if "difficulty" not in df.columns:
    df["difficulty"] = "Unlabeled"
if "tags" not in df.columns:
    df["tags"] = ""

# Filter controls
with st.sidebar:
    st.header("3) Filters")
    subj_opts = sorted(df["subject"].dropna().astype(str).unique().tolist())
    diff_opts = sorted(df["difficulty"].dropna().astype(str).unique().tolist())
    tag_opts = sorted({t.strip() for cell in df["tags"].dropna().astype(str).tolist() for t in cell.split(",") if t.strip()})

    pick_subjects = st.multiselect("Subject", subj_opts)
    pick_diffs = st.multiselect("Difficulty", diff_opts)
    pick_tags = st.multiselect("Tags", tag_opts)

fdf = filter_df(df, pick_subjects, pick_diffs, pick_tags)
if fdf.empty:
    st.warning("No questions matched your filters.")
    st.stop()

# Prepare order
n = len(fdf)
if "order_index" not in st.session_state or st.session_state.get("base_hash") != hash(tuple(fdf["id"].tolist())):
    order = list(range(n))
    if shuffle:
        random.shuffle(order)
    st.session_state.order_index = order
    st.session_state.current_idx = 0
    st.session_state.base_hash = hash(tuple(fdf["id"].tolist()))

ensure_session_lists(n)

# Navigation bar
st.progress((st.session_state.current_idx + 1) / n)
cols = st.columns([2,1,1,1,1])
with cols[0]:
    st.write(f"Question {st.session_state.current_idx + 1} of {n}")
with cols[1]:
    if st.button("◀ Prev"):
        st.session_state.current_idx = max(0, st.session_state.current_idx - 1)
with cols[2]:
    if st.button("Next ▶"):
        st.session_state.current_idx = min(n - 1, st.session_state.current_idx + 1)
with cols[3]:
    if st.button("Reveal All"):
        st.session_state.revealed = [True] * n
with cols[4]:
    if st.button("Reset Session"):
        st.session_state.answers = [None] * n
        st.session_state.revealed = [False] * n
        st.session_state.bookmarks = [False] * n
        st.session_state.current_idx = 0

# Current question
idx = st.session_state.current_idx
q_idx = st.session_state.order_index[idx]
q_row = fdf.iloc[q_idx]
show_question(q_row, idx, n)

st.markdown("---")
st.subheader("Session Summary")
summarize_results(fdf)

st.markdown("---")
c1, c2 = st.columns(2)
with c1:
    st.download_button(
        "⬇️ Export Progress (.json)",
        data=export_progress(fdf),
        file_name="qbank_progress.json",
        mime="application/json"
    )
with c2:
    progress_file = st.file_uploader("Import Progress (.json)", type=["json"], key="imp")
    if progress_file is not None:
        import_progress(progress_file.read(), n)

# Bookmarks panel
with st.expander("🔖 Bookmarked Questions"):
    bookmarked_idxs = [i for i, b in enumerate(st.session_state.bookmarks) if b]
    if not bookmarked_idxs:
        st.caption("No bookmarks yet.")
    else:
        st.write(f"{len(bookmarked_idxs)} bookmarked.")
        for bi in bookmarked_idxs:
            st.write(f"- Q{bi+1}: {fdf.iloc[st.session_state.order_index[bi]]['stem'][:120]}...")

st.caption("Built with Streamlit. CSV-driven. Minimal and reliable.")
