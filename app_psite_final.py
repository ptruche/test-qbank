import os
import glob
import json
from typing import List
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ---- Minimal CSS ----
st.markdown(
    """
    <style>
    :root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
    .q-card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:14px; padding:1.25rem; box-shadow:0 2px 10px rgba(0,0,0,.04); }
    .q-progress { height:8px; background:#e5e7eb; border-radius:999px; overflow:hidden; margin:4px 0 8px 0; }
    .q-progress > div { height:100%; background:var(--accent); width:0%; transition:width .3s ease; }
    .stat { border:1px solid var(--card-border); border-radius:12px; padding:.9rem 1rem; text-align:center; }
    .sticky-top { position:sticky; top:0; z-index:50; background:white; padding:.6rem .5rem; border-bottom:1px solid #eef0f3; }
    .top-title { font-weight:600; letter-spacing:.2px; }
    div[role="radiogroup"] > label { padding:8px 10px; border:1px solid var(--card-border); border-radius:10px; margin-bottom:8px; }
    </style>
    """, unsafe_allow_html=True
)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# ========= Dynamic topic discovery =========
# Put your per-topic CSVs in this folder. If you prefer repo root, set CSV_FOLDER = "."
CSV_FOLDER = "data"  # change to "." if your CSVs are alongside app.py

def _pretty_name_from_filename(path: str) -> str:
    name = os.path.basename(path)
    if name.lower().endswith(".csv"):
        name = name[:-4]
    # convert underscores/dashes to spaces, title-case the result
    return name.replace("_", " ").replace("-", " ").strip().title()

def discover_topic_csvs(folder: str) -> dict:
    """
    Returns a mapping { 'Pretty Subject Name': '/path/to/file.csv' }
    Ignores a generic 'questions.csv' so the list is truly topic CSVs.
    """
    pattern = os.path.join(folder, "*.csv")
    files = glob.glob(pattern)
    mapping = {}
    for f in files:
        base = os.path.basename(f).lower()
        if base == "questions.csv":
            # keep a generic combined file available as a fallback but don't show it as a "topic"
            continue
        pretty = _pretty_name_from_filename(f)
        mapping[pretty] = f
    return dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

TOPIC_TO_CSV = discover_topic_csvs(CSV_FOLDER)
SUBJECT_OPTIONS = list(TOPIC_TO_CSV.keys())

# ========= Safe, topic-aware loader =========
def _read_csv_strict(path: str) -> pd.DataFrame:
    """Read a CSV and validate required columns."""
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    df = df[REQUIRED_COLS].copy()
    df["id"] = df["id"].astype(str).str.strip()
    df["subject"] = df["subject"].astype(str).str.strip()
    return df

def load_questions_for_subjects(selected_subjects) -> pd.DataFrame:
    """
    Load questions only from CSVs corresponding to the selected subjects.
    - Skips any file that is missing or malformed (notes shown in sidebar).
    - If nothing loads but a fallback 'questions.csv' exists at CSV_FOLDER or repo root, uses it.
    - If still nothing, stops with a friendly error.
    """
    frames = []
    notes = []

    # Load per-topic files
    if selected_subjects:
        for subj in selected_subjects:
            csv_path = TOPIC_TO_CSV.get(subj)
            if not csv_path:
                notes.append(f"• No CSV mapped for subject: {subj} (skipped)")
                continue
            if not os.path.exists(csv_path):
                notes.append(f"• CSV not found for {subj}: {csv_path} (skipped)")
                continue
            try:
                df = _read_csv_strict(csv_path)
            except Exception as e:
                notes.append(f"• Problem reading {csv_path}: {e} (skipped)")
                continue

            # Keep only rows that match the intended subject (in case of mix-ups)
            bad = df["subject"] != subj
            if bad.any():
                kept = df[~bad].copy()
                removed = int(bad.sum())
                if removed:
                    notes.append(f"• {os.path.basename(csv_path)}: removed {removed} row(s) with mismatched subject.")
                df = kept

            frames.append(df)

    # Fallback: a generic combined file named 'questions.csv' in CSV_FOLDER or repo root
    def try_fallback() -> pd.DataFrame | None:
        cands = [
            os.path.join(CSV_FOLDER, "questions.csv"),
            "questions.csv",
        ]
        for p in cands:
            if os.path.exists(p):
                try:
                    fb = _read_csv_strict(p)
                    notes.append(f"• Loaded fallback '{p}' because no subject CSVs were usable.")
                    return fb
                except Exception as e:
                    notes.append(f"• Fallback '{p}' unreadable: {e}")
        return None

    if selected_subjects and not frames:
        fb = try_fallback()
        if fb is None:
            st.error("No valid subject CSVs found and no usable fallback 'questions.csv'.")
            st.stop()
        frames.append(fb)

    if not selected_subjects and not frames:
        # No subjects picked yet: return an empty frame
        return pd.DataFrame(columns=REQUIRED_COLS)

    df_all = pd.concat(frames, ignore_index=True)

    # Deduplicate by id across selected files (keep first)
    before = len(df_all)
    df_all = df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    dups = before - len(df_all)
    if dups:
        notes.append(f"• Removed {dups} duplicate id(s) across selected subjects.")

    # Developer-friendly notes in sidebar
    if notes:
        with st.sidebar.expander("Data load notes", expanded=False):
            for n in notes:
                st.caption(n)

    return df_all

# ========= Quiz helpers / UI (unchanged) =========
def validate_df(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def build_quiz_pool(df: pd.DataFrame, subjects: List[str]) -> pd.DataFrame:
    out = df.copy()
    if subjects:
        out = out[out["subject"].astype(str).isin(subjects)]
    return out.reset_index(drop=True)

def init_session_state(n:int):
    st.session_state.answers = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current = 0
    st.session_state.finished = False

def render_header(n:int):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    cols = st.columns([7,5])
    with cols[0]:
        st.markdown("<div class='top-title'>PSITE</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with cols[1]:
        c1, c2 = st.columns(2)
        if c1.button("Skip"):
            st.session_state.current = min(st.session_state.current + 1, n - 1)
        if c2.button("Finish"):
            st.session_state.finished = True
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    n = len(pool)
    row = pool.iloc[i]

    st.markdown("<div class='q-card'>", unsafe_allow_html=True)
    st.markdown(str(row["stem"]))

    letters = ["A","B","C","D","E"]
    fmt = lambda L: str(row[L])
    selected = st.radio(
        label=" ",
        options=letters,
        format_func=fmt,
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed",
        key=f"radio_{i}"
    )
    st.session_state.answers[i] = selected

    st.divider()
    ac = st.columns([1,1,1,6])
    with ac[0]:
        if st.button("Reveal", key=f"reveal_{i}"):
            st.session_state.revealed[i] = True
    with ac[1]:
        if st.button("Prev", key=f"prev_{i}"):
            st.session_state.current = max(st.session_state.current - 1, 0)
    with ac[2]:
        if st.button("Next", key=f"next_{i}"):
            st.session_state.current = min(st.session_state.current + 1, n - 1)

    if st.session_state.revealed[i]:
        correct_letter = str(row["correct"]).strip().upper()
        st.divider()
        if st.session_state.answers[i] is None:
            st.warning("No answer selected.")
        elif st.session_state.answers[i] == correct_letter:
            st.success("Correct")
        else:
            st.error("Incorrect")
        st.info(str(row["explanation"]))

    st.markdown("</div>", unsafe_allow_html=True)

def render_results(pool: pd.DataFrame):
    n = len(pool)
    answers = st.session_state.answers
    revealed = st.session_state.revealed
    correct_letters = [str(x).strip().upper() for x in pool["correct"].tolist()]
    is_correct = [a == c and a is not None and r for a,c,r in zip(answers, correct_letters, revealed)]
    total_correct = sum(is_correct)
    total_revealed = sum(1 for r in revealed if r)
    st.markdown("## Results")
    cols = st.columns(3)
    with cols[0]: st.markdown(f"<div class='stat'><div class='q-subtle'>Answered</div><h3>{total_revealed}/{n}</h3></div>", unsafe_allow_html=True)
    with cols[1]: st.markdown(f"<div class='stat'><div class='q-subtle'>Correct</div><h3>{total_correct}/{n}</h3></div>", unsafe_allow_html=True)
    with cols[2]: st.markdown(f"<div class='stat'><div class='q-subtle'>Score</div><h3>{int(100*total_correct/max(n,1))}%</h3></div>", unsafe_allow_html=True)

    df = pool.copy()
    df["user_answer"] = answers
    df["revealed"] = revealed
    review = []
    for i,row in df.iterrows():
        if row["revealed"]:
            review.append([i+1, str(row["stem"])[:140]+"…", row["user_answer"], str(row["correct"]).upper()])
    if review:
        st.markdown("### Review")
        st.dataframe(pd.DataFrame(review, columns=["#","stem","user_answer","correct"]), use_container_width=True)

    st.download_button(
        "Export Progress (.json)",
        data=json.dumps({"answers": answers, "revealed": revealed, "current": st.session_state.current}, indent=2).encode("utf-8"),
        file_name="psite_progress.json",
        mime="application/json",
    )
    if st.button("Restart"):
        init_session_state(len(pool))

# ========= Sidebar: pick subjects, load only those CSVs, then start =========
with st.sidebar:
    st.header("Build Quiz")

    # Auto-discovered topics
    if not SUBJECT_OPTIONS:
        st.error(f"No topic CSVs found in '{CSV_FOLDER}'. Add files like 'biliary_atresia.csv' and reload.")
        st.stop()

    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS)

    # Load only the CSVs for the selected subjects (safe, with fallback)
    df = load_questions_for_subjects(pick_subjects)

    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5

    n_questions = st.number_input("Number of Questions",
                                  min_value=min_q, max_value=max_q,
                                  step=step_q, value=default_q)

    if st.button("Start ▶"):
        if df.empty:
            st.warning("No questions available for the selected subject(s).")
        else:
            pool = (df.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
                    if len(df) > n_questions
                    else df.sample(frac=1.0, random_state=42).reset_index(drop=True))
            st.session_state.pool = pool
            init_session_state(len(pool))

# ========= Main stage =========
pool = st.session_state.get("pool", None)
if pool is None:
    st.write("Use the sidebar to start a quiz.")
    st.stop()

render_header(len(pool))
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
