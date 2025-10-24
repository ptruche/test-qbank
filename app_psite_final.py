import os
import glob
import json
from typing import List
import pandas as pd
import streamlit as st

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ================= CSS (scroll fix + tight professional layout) =================
st.markdown(
    """
    <style>
    :root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }

    /* Global scrolling & overflow fixes */
    html, body { height: auto !important; overflow-y: auto !important; }
    .block-container { padding-top: 1.25rem !important; padding-bottom: 0.8rem !important; }
    [data-testid="stHorizontalBlock"] { overflow: visible !important; }
    [data-testid="stAppViewContainer"] { overflow-y: auto !important; }
    [data-testid="stMain"] { overflow-y: auto !important; }

    /* Sticky header */
    .sticky-top {
      position: sticky;
      top: 0;
      z-index: 100;
      background: white;
      padding: .65rem .5rem .5rem .5rem;
      border-bottom: 1px solid #eef0f3;
      overflow: visible;
      box-shadow: 0 1px 0 rgba(0,0,0,0.02);
      margin-bottom: .35rem;
    }
    .top-title {
      font-weight: 600; letter-spacing: .2px; font-size: 1.05rem; line-height: 1.25;
      margin: 0 0 .25rem 0;
      white-space: nowrap;
      overflow: visible;
    }
    .q-progress { height: 6px; background:#eef0f3; border-radius: 999px; overflow: hidden; margin: 0 0 4px 0; }
    .q-progress > div { height:100%; background: var(--accent); width:0%; transition: width .25s ease; }

    /* Header buttons row */
    .hdr-row { display: flex; gap: .5rem; justify-content: flex-end; align-items: center; flex-wrap: wrap; }
    .stButton>button { padding: 0.4rem 0.85rem; border-radius: 8px; line-height: 1.25; }

    /* Question card & prompt */
    .q-card { background: var(--card-bg); border: 1px solid var(--card-border);
              border-radius: 12px; padding: 1rem; box-shadow: 0 1px 6px rgba(0,0,0,.04); }
    .q-prompt { border: 1px solid var(--card-border); background: #fafbfc; border-radius: 10px;
                padding: 12px; margin: 6px 0 8px 0; }
    .q-actions-bottom { margin-top: 8px; }

    /* Explanation panel: scrollable */
    .explain-panel {
      max-height: 52vh;
      overflow-y: auto;
      padding: 8px 10px;
      border: 1px solid var(--card-border);
      border-radius: 10px;
      background: #fcfdff;
    }

    /* Radios: compact, no label bubble */
    div[role="radiogroup"] > label {
      padding: 6px 8px; border: 1px solid var(--card-border); border-radius: 8px; margin-bottom: 6px;
    }
    .stRadio div[role="radiogroup"] { gap: 4px !important; }

    .stDivider { margin: 8px 0 !important; }
    .stMarkdown p { margin-bottom: 0.35rem; }

    /* Prevent phantom top gap in question card */
    .q-card > div:first-child { margin-top: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True
)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# ================= Dynamic topic discovery =================
CSV_FOLDER = "data"

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
            continue
        pretty = _pretty_name_from_filename(f)
        mapping[pretty] = f
    return dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

TOPIC_TO_CSV = discover_topic_csvs(CSV_FOLDER)
SUBJECT_OPTIONS = list(TOPIC_TO_CSV.keys())

# ================= CSV readers =================
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
    frames = []
    for subj, csv_path in TOPIC_TO_CSV.items():
        try:
            df = _read_csv_strict(csv_path)
            df = df[df["subject"] == subj]
            frames.append(df)
        except Exception:
            continue
    if not frames:
        st.error("No valid CSVs found in 'data' folder.")
        st.stop()
    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df_all

def load_questions_for_subjects(selected_subjects, random_all: bool) -> pd.DataFrame:
    if random_all:
        return _load_all_topics()
    frames = []
    for subj in selected_subjects:
        csv_path = TOPIC_TO_CSV.get(subj)
        if csv_path and os.path.exists(csv_path):
            try:
                df = _read_csv_strict(csv_path)
                df = df[df["subject"] == subj]
                frames.append(df)
            except Exception:
                pass
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df_all = pd.concat(frames, ignore_index=True)
    df_all = df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df_all

# ================= Quiz helpers / UI =================
def init_session_state(n:int):
    st.session_state.answers = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current = 0
    st.session_state.finished = False

def _go_prev(n: int):
    st.session_state.current = max(st.session_state.current - 1, 0)
def _go_next(n: int):
    st.session_state.current = min(st.session_state.current + 1, n - 1)
def _skip(n: int): _go_next(n)
def _finish(): st.session_state.finished = True
def _reveal(i: int): st.session_state.revealed[i] = True

def render_header(n:int, title_text: str):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)

    left, right = st.columns([6,6])
    with left:
        st.markdown(f"<div class='top-title'>{title_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with right:
        st.markdown("<div class='hdr-row'>", unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        with c1: st.button("Previous", key="hdr_prev", on_click=_go_prev, args=(n,), disabled=(pos == 0))
        with c2: st.button("Next", key="hdr_next", on_click=_go_next, args=(n,), disabled=(pos == n-1))
        with c3: st.button("Skip", key="hdr_skip", on_click=_skip, args=(n,), disabled=(pos == n-1))
        with c4: st.button("Finish", key="hdr_finish", on_click=_finish)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    n = len(pool)
    row = pool.iloc[i]

    st.markdown("<div class='q-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='q-prompt'>{str(row['stem'])}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    fmt = lambda L: str(row[L])
    selected = st.radio(
        label="",
        options=letters,
        format_func=fmt,
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed",
        key="radio_choice"
    )
    st.session_state.answers[i] = selected

    st.divider()
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

        # Scrollable explanation
        st.markdown("<div class='explain-panel'>", unsafe_allow_html=True)
        st.markdown(str(row["explanation"]), unsafe_allow_html=False)
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
    with cols[0]: st.metric("Answered", f"{total_revealed}/{n}")
    with cols[1]: st.metric("Correct", f"{total_correct}/{n}")
    with cols[2]: st.metric("Score", f"{int(100*total_correct/max(n,1))}%")

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

# ================= Sidebar =================
with st.sidebar:
    st.header("Build Quiz")

    if not SUBJECT_OPTIONS:
        st.error(f"No topic CSVs found in '{CSV_FOLDER}'. Add files like 'biliary_atresia.csv' and reload.")
        st.stop()

    random_all = st.toggle("Random from all topics", value=False)
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS, disabled=random_all)

    df = load_questions_for_subjects(pick_subjects, random_all=random_all)
    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5

    n_questions = st.number_input("Number of Questions", min_value=min_q, max_value=max_q, step=step_q, value=default_q)

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

# ================= Main stage =================
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
