import os
import glob
import json
import re
from typing import List, Dict, Set
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ================== CSS ==================
st.markdown("""
<style>
:root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
html, body { height:auto!important; overflow-y:auto!important; }
.block-container { padding-top:1rem!important; padding-bottom:0.5rem!important; }
.sticky-top { position:sticky; top:0; z-index:100; background:white; border-bottom:1px solid #eef0f3; padding:.5rem .5rem; }
.top-title { font-weight:600; font-size:1.05rem; margin-bottom:.25rem; }
.q-progress { height:6px; background:#eef0f3; border-radius:999px; overflow:hidden; margin:0 0 4px 0; }
.q-progress>div { height:100%; background:var(--accent); width:0%; transition:width .25s ease; }
.q-prompt { border:1px solid var(--card-border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; font-size:1.05rem; }
div[role="radiogroup"]>label { border:none!important; background:transparent!important; padding:6px 4px!important; margin:1px 0!important; }
.verdict { font-weight:600; padding:.22rem .6rem; border-radius:999px; border:1px solid transparent; display:inline-flex; align-items:center; }
.verdict-ok { background:#10b9811a; color:#065f46; border-color:#34d399; }
.verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }
.explain-plain { padding-top:8px; background:transparent!important; border:none!important; box-shadow:none!important; }
</style>
""", unsafe_allow_html=True)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]
CSV_FOLDER = "data"

# ================== SVG renderer ==================
SVG_BLOCK_RE = re.compile(r"(<svg[\\s\\S]*?</svg>)", re.IGNORECASE)
def render_explanation_block(explain_text: str):
    """Renders explanation Markdown and inline SVG graphics."""
    if not explain_text or not str(explain_text).strip():
        return
    parts = SVG_BLOCK_RE.split(explain_text)
    for chunk in parts:
        if not chunk.strip():
            continue
        if chunk.strip().lower().startswith("<svg"):
            m = re.search(r'height="(\\d+)"', chunk, re.IGNORECASE)
            height = int(m.group(1)) if m else 320
            components.html(chunk, height=height + 20, scrolling=False)
        else:
            st.markdown(chunk, unsafe_allow_html=False)

# ================== CSV Helpers ==================
def _read_csv_strict(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{os.path.basename(path)} missing cols: {missing}")
    for col in REQUIRED_COLS:
        df[col] = df[col].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    return df

def discover_subjects_from_csvs(folder: str) -> Dict[str, Set[str]]:
    files = glob.glob(os.path.join(folder, "*.csv"))
    subj_to_files: Dict[str, Set[str]] = {}
    for f in files:
        try:
            df = _read_csv_strict(f)
        except Exception:
            continue
        for subj in df["subject"].dropna().unique():
            subj_to_files.setdefault(subj, set()).add(f)
    return subj_to_files

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
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=REQUIRED_COLS)

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
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=REQUIRED_COLS)

# ================== Quiz Logic ==================
def init_session_state(n:int):
    st.session_state.answers = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current = 0
    st.session_state.finished = False

def render_header(n:int, title_text:str):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    left, right = st.columns([6,6])
    with left:
        st.markdown(f"<div class='top-title'>{title_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with right:
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Previous", disabled=(pos==0)):
            st.session_state.current = max(pos-1,0)
        if c2.button("Next", disabled=(pos==n-1)):
            st.session_state.current = min(pos+1,n-1)
        if c3.button("Skip", disabled=(pos==n-1)):
            st.session_state.current = min(pos+1,n-1)
        if c4.button("Finish"):
            st.session_state.finished = True
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    row = pool.iloc[i]
    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    selected = st.radio("", letters,
                        format_func=lambda L: row[L],
                        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
                        label_visibility="collapsed",
                        key=f"radio_{i}")
    st.session_state.answers[i] = selected

    # Reveal logic
    st.write("")  # small spacing
    cols = st.columns([1,6])
    with cols[0]:
        if st.button("Reveal", key=f"reveal_{i}"):
            st.session_state.revealed[i] = True
    with cols[1]:
        if st.session_state.revealed[i]:
            correct = str(row["correct"]).strip().upper()
            verdict_html = (
                "<span class='verdict verdict-ok'>Correct</span>" if selected == correct
                else "<span class='verdict verdict-err'>Incorrect</span>"
            )
            st.markdown(verdict_html, unsafe_allow_html=True)

    if st.session_state.revealed[i]:
        st.markdown("<div class='explain-plain'>", unsafe_allow_html=True)
        render_explanation_block(str(row["explanation"]))
        st.markdown("</div>", unsafe_allow_html=True)

def render_results(pool: pd.DataFrame):
    n = len(pool)
    answers = st.session_state.answers
    revealed = st.session_state.revealed
    corrects = [str(x).strip().upper() for x in pool["correct"]]
    score = sum(a==c and r for a,c,r in zip(answers, corrects, revealed))
    st.markdown("## Results")
    st.metric("Score", f"{int(100*score/max(n,1))}%")
    if st.button("Restart"):
        init_session_state(len(pool))

# ================== Sidebar ==================
with st.sidebar:
    st.header("Build Quiz")
    if not SUBJECT_OPTIONS:
        st.error("No subjects found in your data folder.")
        st.stop()

    random_all = st.toggle("Random from all topics", value=False)
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS, disabled=random_all)

    df = load_questions_for_subjects(pick_subjects, random_all)
    total = len(df)
    n_questions = st.number_input("Number of Questions", 1, max(1,total), min(20,total))
    if st.button("Start ▶"):
        if df.empty:
            st.warning("No questions found for selection.")
        else:
            pool = df.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
            st.session_state.pool = pool
            init_session_state(len(pool))
            st.session_state.random_all = random_all
            st.session_state.selected_subjects = pick_subjects

# ================== Main Stage ==================
pool = st.session_state.get("pool")
if pool is None:
    st.write("Use the sidebar to start a quiz.")
    st.stop()

title_text = "Random Mix" if st.session_state.get("random_all") else ", ".join(st.session_state.get("selected_subjects", []))
render_header(len(pool), title_text or "PSITE")
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
