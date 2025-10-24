import os
import glob
import json
from typing import List, Dict, Set
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ================= CSS: Uniform font size for question, answers, and explanation =================
st.markdown(
    """
    <style>
    :root {
      --font-size: 1.15rem;  /* Universal font size for all text */
      --line-height: 1.55;
      --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280;
    }

    html, body {
      height: auto !important;
      overflow-y: auto !important;
      font-size: var(--font-size) !important;
      line-height: var(--line-height) !important;
    }

    .block-container { padding-top: 1.1rem !important; padding-bottom: 0.8rem !important; }
    [data-testid="stHorizontalBlock"] { overflow: visible !important; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-y: auto !important; }

    /* Sticky header */
    .sticky-top {
      position: sticky; top: 0; z-index: 100; background: white;
      padding: .65rem .5rem .5rem .5rem;
      border-bottom: 1px solid #eef0f3;
      overflow: visible; box-shadow: 0 1px 0 rgba(0,0,0,0.02);
      margin-bottom: .35rem;
    }
    .top-title {
      font-weight: 600;
      letter-spacing:.2px;
      font-size: 1.05rem;
      line-height: 1.25;
      margin: 0 0 .25rem 0;
    }
    .q-progress { height: 6px; background:#eef0f3; border-radius: 999px; overflow: hidden; margin: 0 0 4px 0; }
    .q-progress > div { height:100%; background: var(--accent); width:0%; transition: width .25s ease; }

    /* Header controls */
    .hdr-row { display:flex; gap:.5rem; justify-content:flex-end; align-items:center; flex-wrap:wrap; }
    .stButton>button { padding:.4rem .85rem; border-radius:8px; line-height:1.25; }

    /* Question container */
    .q-card { border:none; background:transparent; padding:0; box-shadow:none; }
    .q-prompt {
      border:1px solid var(--card-border);
      background:#fafbfc;
      border-radius:10px;
      padding:12px;
      margin:0 0 8px 0;
      font-size: var(--font-size);
      line-height: var(--line-height);
    }

    /* Answer choices: clean, consistent font */
    div[role="radiogroup"] { gap: 0 !important; }
    div[role="radiogroup"] > label {
      border:none !important;
      background:transparent !important;
      padding:8px 4px !important;
      margin:2px 0 !important;
      border-radius:6px;
      transition: background-color .15s ease;
    }
    div[role="radiogroup"] > label:hover { background:#f5f7fb !important; }
    div[role="radiogroup"] > label p {
      font-size: var(--font-size) !important;
      line-height: var(--line-height) !important;
      margin: 0 !important;
    }
    div[role="radiogroup"] input:checked + div > p {
      text-decoration: underline;
      text-underline-offset: 3px;
    }

    /* Reveal and verdict row */
    .q-actions-row {
      display:flex;
      align-items:center;
      gap:.6rem;
      margin:0;
      font-size: var(--font-size);
    }
    .verdict {
      display:inline-flex;
      align-items:center;
      font-weight:600;
      padding:.22rem .6rem;
      border-radius:999px;
      white-space:nowrap;
      border:1px solid transparent;
      font-size: var(--font-size);
    }
    .verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
    .verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }

    /* Explanation: plain background, same font size */
    .explain-plain {
      margin-top:0;
      padding:10px 0 0 0;
      background:transparent !important;
      border:none !important;
      box-shadow:none !important;
      font-size: var(--font-size);
      line-height: var(--line-height);
    }

    .stDivider { margin:8px 0 !important; }
    .stMarkdown p { margin-bottom:0.35rem; }
    </style>
    """,
    unsafe_allow_html=True
)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]
CSV_FOLDER = "data"

# ===== CSV Handling =====
def _read_csv_strict(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{os.path.basename(path)} missing: {missing}")
    df = df[REQUIRED_COLS].copy()
    for c in ["id","subject","A","B","C","D","E","stem","explanation","correct"]:
        df[c] = df[c].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    return df

def discover_subjects_from_csvs(folder: str) -> Dict[str, Set[str]]:
    pattern = os.path.join(folder, "*.csv")
    files = glob.glob(pattern)
    subj_map: Dict[str, Set[str]] = {}
    for f in files:
        try:
            df = _read_csv_strict(f)
        except Exception:
            continue
        for s in df["subject"].dropna().astype(str).str.strip().unique():
            subj_map.setdefault(s, set()).add(f)
    return subj_map

SUBJECT_TO_FILES = discover_subjects_from_csvs(CSV_FOLDER)
SUBJECT_OPTIONS = sorted(SUBJECT_TO_FILES.keys(), key=lambda s: s.lower())

def _load_all_topics() -> pd.DataFrame:
    frames = []
    for files in SUBJECT_TO_FILES.values():
        for f in files:
            try:
                frames.append(_read_csv_strict(f))
            except Exception:
                pass
    if not frames:
        st.error("No valid CSVs found.")
        st.stop()
    df_all = pd.concat(frames, ignore_index=True)
    return df_all.drop_duplicates(subset=["id"], keep="first")

def load_questions_for_subjects(selected_subjects: List[str], random_all: bool) -> pd.DataFrame:
    if random_all:
        return _load_all_topics()
    if not selected_subjects:
        return pd.DataFrame(columns=REQUIRED_COLS)
    frames = []
    files_to_read = set()
    for subj in selected_subjects:
        files_to_read |= SUBJECT_TO_FILES.get(subj, set())
    for f in files_to_read:
        try:
            df = _read_csv_strict(f)
            frames.append(df[df["subject"].isin(selected_subjects)])
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLS)
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["id"], keep="first")

# ===== App Logic =====
def init_session_state(n:int):
    st.session_state.answers = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current = 0
    st.session_state.finished = False

def _go_prev(n:int): st.session_state.current = max(st.session_state.current - 1, 0)
def _go_next(n:int): st.session_state.current = min(st.session_state.current + 1, n - 1)
def _skip(n:int): _go_next(n)
def _finish(): st.session_state.finished = True
def _reveal(i:int): st.session_state.revealed[i] = True

def render_header(n:int, title_text:str):
    pos = st.session_state.current
    pct = int(((pos+1)/max(n,1))*100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    left,right = st.columns([6,6])
    with left:
        st.markdown(f"<div class='top-title'>{title_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with right:
        st.markdown("<div class='hdr-row'>", unsafe_allow_html=True)
        c1,c2,c3,c4 = st.columns([1,1,1,1])
        with c1: st.button("Previous", key="hdr_prev", on_click=_go_prev, args=(n,), disabled=(pos==0))
        with c2: st.button("Next", key="hdr_next", on_click=_go_next, args=(n,), disabled=(pos==n-1))
        with c3: st.button("Skip", key="hdr_skip", on_click=_skip, args=(n,), disabled=(pos==n-1))
        with c4: st.button("Finish", key="hdr_finish", on_click=_finish)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    row = pool.iloc[i]
    st.markdown("<div class='q-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    fmt = lambda L: str(row[L])
    selected = st.radio(
        label="", options=letters, format_func=fmt,
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed", key=f"radio_choice_{i}"
    )
    st.session_state.answers[i] = selected

    st.markdown("<div class='q-actions-row'>", unsafe_allow_html=True)
    col_btn,col_v = st.columns([1,6], gap="small")
    with col_btn:
        st.button("Reveal", key=f"btn_reveal_{i}", on_click=_reveal, args=(i,))
    with col_v:
        if st.session_state.revealed[i]:
            correct = row["correct"].strip().upper()
            verdict = "<span class='verdict verdict-ok'>Correct</span>" if selected == correct else "<span class='verdict verdict-err'>Incorrect</span>"
            st.markdown(verdict, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.revealed[i]:
        st.markdown("<div class='explain-plain'>", unsafe_allow_html=True)
        st.markdown(row["explanation"], unsafe_allow_html=False)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

def render_results(pool: pd.DataFrame):
    n = len(pool)
    answers = st.session_state.answers
    revealed = st.session_state.revealed
    correct_letters = [str(x).strip().upper() for x in pool["correct"]]
    is_correct = [a == c and a is not None and r for a,c,r in zip(answers, correct_letters, revealed)]
    total_correct = sum(is_correct)
    total_revealed = sum(1 for r in revealed if r)
    st.markdown("## Results")
    cols = st.columns(3)
    with cols[0]: st.metric("Answered", f"{total_revealed}/{n}")
    with cols[1]: st.metric("Correct", f"{total_correct}/{n}")
    with cols[2]: st.metric("Score", f"{int(100*total_correct/max(n,1))}%")
    if st.button("Restart"):
        init_session_state(len(pool))

with st.sidebar:
    st.header("Build Quiz")
    if not SUBJECT_OPTIONS:
        st.error(f"No subjects found in '{CSV_FOLDER}'. Ensure CSVs have a 'subject' column.")
        st.stop()

    random_all = st.toggle("Random from all topics", value=False)
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS, disabled=random_all)
    df = load_questions_for_subjects(pick_subjects, random_all=random_all)

    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q)
    step_q = 1 if max_q < 10 else 5
    n_questions = st.number_input("Number of Questions", min_value=min_q, max_value=max_q, step=step_q, value=default_q)

    if st.button("Start ▶"):
        if df.empty:
            st.warning("No questions available.")
        else:
            pool = df.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
            st.session_state.pool = pool
            init_session_state(len(pool))
            st.session_state.random_all = random_all
            st.session_state.selected_subjects = pick_subjects

pool = st.session_state.get("pool", None)
if pool is None:
    st.write("Use the sidebar to start a quiz.")
    st.stop()

sel_subjects = st.session_state.get("selected_subjects", [])
random_all = st.session_state.get("random_all", False)
title_text = "Random Mix" if random_all else (", ".join(sel_subjects) if sel_subjects else "PSITE")

render_header(len(pool), title_text)
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
