import os
import glob
import json
from typing import List
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ---- Tight, professional CSS (reduced gaps) ----
st.markdown(
    """
    <style>
    :root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
    .q-card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:12px; padding:1rem; box-shadow:0 1px 6px rgba(0,0,0,.04); }
    .q-progress { height:6px; background:#eef0f3; border-radius:999px; overflow:hidden; margin:2px 0 6px 0; }
    .q-progress > div { height:100%; background:var(--accent); width:0%; transition:width .25s ease; }
    .stat { border:1px solid var(--card-border); border-radius:10px; padding:.6rem .8rem; text-align:center; }
    .sticky-top { position:sticky; top:0; z-index:50; background:white; padding:.4rem .25rem; border-bottom:1px solid #eef0f3; }
    .top-title { font-weight:600; letter-spacing:.2px; font-size:1rem; }
    /* Clean radio list + tighter spacing */
    div[role="radiogroup"] > label { padding:6px 8px; border:1px solid var(--card-border); border-radius:8px; margin-bottom:6px; }
    /* Question "textbox" */
    .q-prompt { border:1px solid var(--card-border); background:#fafbfc; border-radius:10px; padding:12px 12px; margin-bottom:10px; }
    .q-actions-bottom { margin-top:8px; }
    /* Reduce global vertical whitespace from containers/buttons */
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    .stButton>button { padding:0.35rem 0.8rem; border-radius:8px; }
    .stRadio div[role="radiogroup"] { gap: 4px !important; }
    .stDivider { margin: 8px 0 !important; }
    .stMarkdown p { margin-bottom: 0.4rem; }
    </style>
    """, unsafe_allow_html=True
)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# ========= Dynamic topic discovery =========
CSV_FOLDER = "data"  # change to "." if CSVs live next to app.py

def _pretty_name_from_filename(path: str) -> str:
    name = os.path.basename(path)
    if name.lower().endswith(".csv"):
        name = name[:-4]
    return name.replace("_", " ").replace("-", " ").strip().title()

def discover_topic_csvs(folder: str) -> dict:
    pattern = os.path.join(folder, "*.csv")
    files = glob.glob(pattern)
    mapping = {}
    for f in files:
        base = os.path.basename(f).lower()
        if base == "questions.csv":
            continue  # keep as fallback only
        pretty = _pretty_name_from_filename(f)
        mapping[pretty] = f
    return dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

TOPIC_TO_CSV = discover_topic_csvs(CSV_FOLDER)
SUBJECT_OPTIONS = list(TOPIC_TO_CSV.keys())

# ========= Safe CSV readers =========
def _read_csv_strict(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    df = df[REQUIRED_COLS].copy()
    df["id"] = df["id"].astype(str).str.strip()
    df["subject"] = df["subject"].astype(str).str.strip()
    return df

def _load_all_topics() -> pd.DataFrame:
    notes = []
    frames = []
    for subj, csv_path in TOPIC_TO_CSV.items():
        try:
            df = _read_csv_strict(csv_path)
        except Exception as e:
            notes.append(f"• Skipped {os.path.basename(csv_path)}: {e}")
            continue
        # guard: only keep rows whose subject matches display name
        bad = df["subject"] != subj
        if bad.any():
            removed = int(bad.sum())
            df = df[~bad].copy()
            if removed:
                notes.append(f"• {os.path.basename(csv_path)}: removed {removed} row(s) with mismatched subject.")
        frames.append(df)
    if not frames:
        # try fallback combined file
        for p in [os.path.join(CSV_FOLDER, "questions.csv"), "questions.csv"]:
            if os.path.exists(p):
                try:
                    fb = _read_csv_strict(p)
                    frames.append(fb)
                    notes.append(f"• Loaded fallback '{p}' (no per-topic CSVs usable).")
                    break
                except Exception as e:
                    notes.append(f"• Fallback '{p}' unreadable: {e}")
        if not frames:
            st.error("No topic CSVs found and no usable fallback 'questions.csv'.")
            st.stop()
    if notes:
        with st.sidebar.expander("Data load notes", expanded=False):
            for n in notes:
                st.caption(n)
    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df_all

def load_questions_for_subjects(selected_subjects, random_all: bool) -> pd.DataFrame:
    """Load either all topics (random mix) or only chosen subjects; safe fallbacks."""
    if random_all:
        return _load_all_topics()

    frames = []
    notes = []

    if selected_subjects:
        for subj in selected_subjects:
            csv_path = TOPIC_TO_CSV.get(subj)
            if not csv_path:
                notes.append(f"• No CSV mapped for: {subj} (skipped)")
                continue
            if not os.path.exists(csv_path):
                notes.append(f"• CSV not found: {csv_path} (skipped)")
                continue
            try:
                df = _read_csv_strict(csv_path)
            except Exception as e:
                notes.append(f"• Problem reading {csv_path}: {e} (skipped)")
                continue
            bad = df["subject"] != subj
            if bad.any():
                removed = int(bad.sum())
                df = df[~bad].copy()
                if removed:
                    notes.append(f"• {os.path.basename(csv_path)}: removed {removed} mismatched row(s).")
            frames.append(df)

    if selected_subjects and not frames:
        # fallback combined file if user picked subjects but none loaded
        for p in [os.path.join(CSV_FOLDER, "questions.csv"), "questions.csv"]:
            if os.path.exists(p):
                try:
                    fb = _read_csv_strict(p)
                    frames.append(fb)
                    notes.append(f"• Loaded fallback '{p}' because no subject CSVs were usable.")
                    break
                except Exception as e:
                    notes.append(f"• Fallback '{p}' unreadable: {e}")
        if not frames:
            st.error("No valid subject CSVs found and no usable fallback 'questions.csv'.")
            st.stop()

    if not selected_subjects and not frames:
        return pd.DataFrame(columns=REQUIRED_COLS)

    if notes:
        with st.sidebar.expander("Data load notes", expanded=False):
            for n in notes:
                st.caption(n)

    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df_all

# ========= Quiz helpers / UI =========
def validate_df(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def build_quiz_pool(df: pd.DataFrame, subjects: List[str], random_all: bool) -> pd.DataFrame:
    if random_all or not subjects:
        return df.reset_index(drop=True)
    out = df[df["subject"].astype(str).isin(subjects)].copy()
    return out.reset_index(drop=True)

def init_session_state(n:int):
    st.session_state.answers = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current = 0
    st.session_state.finished = False

def render_header(n:int, title_text: str):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    cols = st.columns([7,5])
    with cols[0]:
        st.markdown(f"<div class='top-title'>{title_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with cols[1]:
        # keep these small, non-blocking
        c1, c2 = st.columns(2)
        c1.button("Skip", key="hdr_skip")
        c2.button("Finish", key="hdr_finish")
    st.markdown("</div>", unsafe_allow_html=True)

# --- Navigation callbacks (constant keys avoid double-click issue) ---
def _go_prev(n: int):
    st.session_state.current = max(st.session_state.current - 1, 0)

def _go_next(n: int):
    st.session_state.current = min(st.session_state.current + 1, n - 1)

def _reveal(i: int):
    st.session_state.revealed[i] = True

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    n = len(pool)
    row = pool.iloc[i]

    st.markdown("<div class='q-card'>", unsafe_allow_html=True)

    # Question stem in a compact "textbox"
    st.markdown(f"<div class='q-prompt'>{str(row['stem'])}</div>", unsafe_allow_html=True)

    # Choices: single, clean radio group — remove empty label bubble by using empty label and collapsed visibility
    letters = ["A","B","C","D","E"]
    fmt = lambda L: str(row[L])
    selected = st.radio(
        label="",                     # no label string
        options=letters,
        format_func=fmt,
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed", # hide label space
        key="radio_choice"
    )
    st.session_state.answers[i] = selected

    st.divider()

    # Reveal button + explanation (tight spacing)
    st.button("Reveal", key="btn_reveal", on_click=_reveal, args=(i,))
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

    # Bottom: Prev / Next (below explanation), compact layout
    st.markdown("<div class='q-actions-bottom'>", unsafe_allow_html=True)
    bcol1, bcol2, bcol3 = st.columns([1,6,1])
    with bcol1:
        st.button("Previous", key="btn_prev", on_click=_go_prev, args=(n,), disabled=(i == 0))
    with bcol3:
        st.button("Next", key="btn_next", on_click=_go_next, args=(n,), disabled=(i == n-1))
    st.markdown("</div>", unsafe_allow_html=True)

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

# ========= Sidebar =========
with st.sidebar:
    st.header("Build Quiz")

    if not SUBJECT_OPTIONS:
        st.error(f"No topic CSVs found in '{CSV_FOLDER}'. Add files like 'biliary_atresia.csv' and reload.")
        st.stop()

    # NEW: Random-from-all toggle
    random_all = st.toggle("Random from all topics", value=False)

    # If random_all is on, disable subject picker (informational display only)
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS, disabled=random_all)

    # Load questions (either all topics or only chosen subjects)
    df = load_questions_for_subjects(pick_subjects, random_all=random_all)

    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5

    n_questions = st.number_input(
        "Number of Questions", min_value=min_q, max_value=max_q, step=step_q, value=default_q
    )

    if st.button("Start ▶", key="btn_start"):
        if df.empty:
            st.warning("No questions available for the current selection.")
        else:
            pool = (df.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
                    if len(df) > n_questions
                    else df.sample(frac=1.0, random_state=42).reset_index(drop=True))
            st.session_state.pool = pool
            init_session_state(len(pool))
            st.session_state.random_all = random_all
            st.session_state.selected_subjects = pick_subjects

# ========= Main stage =========
pool = st.session_state.get("pool", None)
if pool is None:
    st.write("Use the sidebar to start a quiz.")
    st.stop()

# Dynamic title: subjects chosen or "Random Mix"
sel_subjects = st.session_state.get("selected_subjects", [])
random_all = st.session_state.get("random_all", False)
title_text = "Random Mix" if random_all else (", ".join(sel_subjects) if sel_subjects else "PSITE")

render_header(len(pool), title_text)
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
