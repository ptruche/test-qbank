import os
import json
import random
from typing import List
import pandas as pd
import streamlit as st

# ---------------- Page Setup ----------------
st.set_page_config(page_title="Mini QBank (Fixed CSV)", page_icon="🧠", layout="wide")

REQUIRED_COLS = ["id", "subject", "stem", "A", "B", "C", "D", "E", "correct", "explanation"]

# ---------------- Helpers ----------------
def validate_df(df: pd.DataFrame) -> list:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    return missing

def filter_df(df: pd.DataFrame, subjects: List[str], difficulties: List[str], tags: List[str]) -> pd.DataFrame:
    out = df.copy()
    if subjects:
        out = out[out["subject"].astype(str).isin(subjects)]
    if difficulties and "difficulty" in out.columns:
        out = out[out["difficulty"].astype(str).isin(difficulties)]
    if tags and "tags" in out.columns:
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
        if obj.get("meta", {}).get("n_questions") != n_questions:
            st.warning("Progress file does not match this question set. Ignoring.")
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

# ---------------- Load Fixed CSV ----------------
st.title("🧠 Mini QBank (Fixed CSV)")
st.caption("This app always loads questions from a CSV in the repository.")

# Preferred: local CSV committed to the repo
CSV_PATH = os.environ.get("QBANK_CSV_PATH", "questions.csv")
df = pd.DataFrame()

try:
    df = pd.read_csv(CSV_PATH)
except Exception as e_local:
    # Fallback: allow a raw URL via secret or env var
    RAW_URL = st.secrets.get("CSV_URL", os.environ.get("CSV_URL", ""))
    if RAW_URL:
        try:
            df = pd.read_csv(RAW_URL)
            st.info("Loaded questions from configured CSV_URL.")
        except Exception as e_url:
            st.error(f"Failed to load CSV from both local path '{CSV_PATH}' and CSV_URL. Local error: {e_local}. URL error: {e_url}")
    else:
        st.error(f"Could not read local CSV '{CSV_PATH}'. Set st.secrets['CSV_URL'] or env CSV_URL to a Raw GitHub CSV URL. Error: {e_local}")
        st.stop()

# Validate
missing = validate_df(df)
if missing:
    st.error(f"CSV is missing required columns: {missing}")
    st.stop()

if "difficulty" not in df.columns:
    df["difficulty"] = "Unlabeled"
if "tags" not in df.columns:
    df["tags"] = ""

# ---------------- Sidebar Filters ----------------
st.sidebar.header("Filters")
subj_opts = sorted(df["subject"].dropna().astype(str).unique().tolist())
diff_opts = sorted(df["difficulty"].dropna().astype(str).unique().tolist())
tag_opts = sorted({t.strip() for cell in df["tags"].dropna().astype(str).tolist() for t in cell.split(",") if t.strip()})

pick_subjects = st.sidebar.multiselect("Subject", subj_opts)
pick_diffs = st.sidebar.multiselect("Difficulty", diff_opts)
pick_tags = st.sidebar.multiselect("Tags", tag_opts)

fdf = filter_df(df, pick_subjects, pick_diffs, pick_tags)
if fdf.empty:
    st.warning("No questions matched your filters.")
    st.stop()

# ---------------- Ordering / State ----------------
shuffle = st.sidebar.toggle("Shuffle order", value=True)

n = len(fdf)
if "order_index" not in st.session_state or st.session_state.get("base_hash") != hash(tuple(fdf["id"].tolist())):
    order = list(range(n))
    if shuffle:
        random.shuffle(order)
    st.session_state.order_index = order
    st.session_state.current_idx = 0
    st.session_state.base_hash = hash(tuple(fdf["id"].tolist()))

ensure_session_lists(n)

# ---------------- Nav + Display ----------------
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
    st.download_button("⬇️ Export Progress (.json)", data=export_progress(fdf), file_name="qbank_progress.json", mime="application/json")
with c2:
    progress_file = st.file_uploader("Import Progress (.json)", type=["json"], key="imp")
    if progress_file is not None:
        import_progress(progress_file.read(), n)

with st.expander("🔖 Bookmarked Questions"):
    bookmarked_idxs = [i for i, b in enumerate(st.session_state.bookmarks) if b]
    if not bookmarked_idxs:
        st.caption("No bookmarks yet.")
    else:
        st.write(f"{len(bookmarked_idxs)} bookmarked.")
        for bi in bookmarked_idxs:
            st.write(f"- Q{bi+1}: {fdf.iloc[st.session_state.order_index[bi]]['stem'][:120]}...")

st.caption("This build reads questions from a fixed CSV committed to the repo. Configure with QBANK_CSV_PATH or CSV_URL if needed.")
