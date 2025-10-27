import os
import glob
import json
import re
from typing import List, Dict, Set, Tuple
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ============================= Base UI CSS (neutral everywhere) =============================
st.markdown("""
<style>
:root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
html, body { height:auto!important; overflow-y:auto!important; }
.block-container { padding-top:1.1rem!important; padding-bottom:0.7rem!important; }

/* Header / progress */
.sticky-top {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: #fff;
  border-bottom: 1px solid #eef0f3;
  padding: 0.85rem 0.6rem 0.6rem;
  overflow: visible;
  box-sizing: border-box;
}
.top-title { font-weight:600; font-size:1.06rem; margin:0 0 .3rem 0; }
.q-progress { height:6px; background:#eef0f3; border-radius:999px; overflow:hidden; margin:0 0 6px 0; }
.q-progress>div { height:100%; background:var(--accent); width:0%; transition:width .25s ease; }

/* Buttons in sticky header */
.sticky-top .stButton>button {
  padding: 0.48rem 0.9rem !important;
  line-height: 1.2 !important;
  min-height: 38px !important;
  border-radius: 8px !important;
  vertical-align: middle;
}

/* Neutral question prompt */
.q-prompt { border:1px solid var(--card-border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }

/* Neutral answers (no bubbles) */
div[role="radiogroup"] { gap:0!important; }
div[role="radiogroup"]>label { border:none!important; background:transparent!important; padding:8px 4px!important; margin:2px 0!important; border-radius:6px; }
div[role="radiogroup"]>label:hover { background:#f5f7fb!important; }

/* Verdict (compact, neutral) */
.verdict { font-weight:600; padding:.22rem .6rem; border-radius:999px; border:1px solid transparent; display:inline-flex; align-items:center; }
.verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
.verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }

/* Plain container for explanation; no card/bubble */
.explain-plain { padding-top:8px; background:transparent!important; border:none!important; box-shadow:none!important; }

/* Review header tweaks */
.review-title { font-weight:700; font-size:1.3rem; margin:0.25rem 0 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ============================= Resolve data paths robustly =============================
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER  = os.getenv("QBANK_DATA_DIR", os.path.join(BASE_DIR, "data"))
MD_FOLDER    = os.getenv("QBANK_MD_DIR", os.path.join(DATA_FOLDER, "questions"))
REVIEW_FOLDER= os.getenv("QBANK_REVIEW_DIR", os.path.join(DATA_FOLDER, "reviews"))

# Ensure folders exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(MD_FOLDER, exist_ok=True)
os.makedirs(REVIEW_FOLDER, exist_ok=True)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# ============================= SVG rendering + Scoped styling =============================
SVG_BLOCK_RE = re.compile(r"(<svg[\s\S]*?</svg>)", re.IGNORECASE)

EXPLAIN_SCOPE_CSS = """
<style>
.explain-scope { font-family: 'Segoe UI', Arial, sans-serif; font-size: 1.02rem; line-height: 1.55; color:#222; }
.explain-scope h3     { margin:.4rem 0 .25rem 0; font-weight:700; }
.explain-scope .hdr-blue  { color:#1d4ed8; }
.explain-scope .hdr-green { color:#059669; }
.explain-scope .hdr-violet{ color:#7c3aed; }
.explain-scope .hdr-rose  { color:#e11d48; }
.explain-scope table    { border-collapse:collapse; width:100%; margin:.4rem 0; border:2px solid #444; }
.explain-scope th, td   { border:1px solid #d1d5db; padding:.45rem .5rem; text-align:center; }
.explain-scope thead th { background:#1d4ed8; color:white; border-color:#1d4ed8; }
.explain-scope tr:nth-child(even) { background:#f9fafb; }
.explain-scope .t-blue  { color:#0b5394; }
.explain-scope .t-red   { color:#b32400; }
.explain-scope ul { margin:.2rem 0 .2rem 1.1rem; }
</style>
"""

def _render_markdown_with_svg(md_text: str, scoped: bool = False):
    """Render arbitrary Markdown + inline SVG safely. Optionally include scoped CSS."""
    if not md_text or not str(md_text).strip():
        return
    if scoped:
        st.markdown("<div class='explain-scope'>", unsafe_allow_html=True)
        st.markdown(EXPLAIN_SCOPE_CSS, unsafe_allow_html=True)

    parts = SVG_BLOCK_RE.split(md_text)
    for chunk in parts:
        if not chunk or not chunk.strip():
            continue
        if chunk.lstrip().lower().startswith("<svg"):
            m = re.search(r'height="(\d+)"', chunk, re.IGNORECASE)
            height = int(m.group(1)) if m else 320
            components.html(chunk, height=height + 20, scrolling=False)
        else:
            st.markdown(chunk, unsafe_allow_html=False)

    if scoped:
        st.markdown("</div>", unsafe_allow_html=True)

def render_explanation_block(explain_text: str):
    _render_markdown_with_svg(explain_text, scoped=True)

# ============================= Markdown loaders (QBank) =============================
FRONTMATTER_RE = re.compile(r"^---\s*([\s\S]*?)\s*---\s*([\s\S]*)$", re.MULTILINE)
EXPL_SPLIT_RE  = re.compile(r"<!--\s*EXPLANATION\s*-->", re.IGNORECASE)

def _parse_front_matter(text: str):
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("Missing front-matter '--- ... ---'")
    fm, body = m.group(1), m.group(2)
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k,v = line.split(":",1)
            meta[k.strip()] = v.strip()
    return meta, body.strip()

def _split_stem_explanation(body: str) -> Tuple[str, str]:
    parts = EXPL_SPLIT_RE.split(body, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return body.strip(), ""

def _read_md_question(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    meta, body = _parse_front_matter(raw)
    stem, explanation = _split_stem_explanation(body)
    rec = {
        "id": meta.get("id","").strip(),
        "subject": meta.get("subject","").strip(),
        "A": meta.get("A","").strip(),
        "B": meta.get("B","").strip(),
        "C": meta.get("C","").strip(),
        "D": meta.get("D","").strip(),
        "E": meta.get("E","").strip(),
        "correct": meta.get("correct","").strip().upper(),
        "stem": stem,
        "explanation": explanation,
    }
    if not rec["id"] or not rec["subject"] or not rec["correct"]:
        raise ValueError("Missing 'id', 'subject', or 'correct'")
    for c in ["A","B","C","D","E"]:
        if rec[c] == "":
            raise ValueError(f"Missing choice {c}")
    return rec

def _read_all_markdown(folder: str) -> Tuple[pd.DataFrame, int]:
    files = sorted(glob.glob(os.path.join(folder, "*.md")))
    rows, skipped = [], 0
    for f in files:
        try:
            rows.append(_read_md_question(f))
        except Exception:
            skipped += 1
    if not rows:
        return pd.DataFrame(columns=REQUIRED_COLS), skipped
    df = pd.DataFrame(rows)
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].astype(str).str.strip()
    df["correct"] = df["correct"].str.upper()
    df = df.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
    return df, skipped

def discover_subjects_from_markdown(folder: str) -> Dict[str, Set[str]]:
    files = sorted(glob.glob(os.path.join(folder, "*.md")))
    subj_to_files: Dict[str, Set[str]] = {}
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as h:
                raw = h.read()
            meta, _ = _parse_front_matter(raw)
            subj = (meta.get("subject") or "").strip()
            if subj:
                subj_to_files.setdefault(subj, set()).add(f)
        except Exception:
            continue
    return subj_to_files

# ============================= (Optional) CSV support =============================
def _read_csv_strict(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{os.path.basename(path)} missing cols: {missing}")
    df = df[REQUIRED_COLS].copy()
    for c in REQUIRED_COLS:
        df[c] = df[c].astype(str).str.strip()
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
        for s in df["subject"].dropna().unique():
            subj_to_files.setdefault(str(s), set()).add(f)
    return subj_to_files

# ============================= Subject map (MD + CSV) =============================
MD_SUBJECTS  = discover_subjects_from_markdown(MD_FOLDER)
CSV_SUBJECTS = discover_subjects_from_csvs(DATA_FOLDER)

SUBJECT_TO_FILES: Dict[str, Set[str]] = {}
for subj, paths in MD_SUBJECTS.items():
    SUBJECT_TO_FILES.setdefault(subj, set()).update(paths)
for subj, paths in CSV_SUBJECTS.items():
    SUBJECT_TO_FILES.setdefault(subj, set()).update(paths)
SUBJECT_OPTIONS = sorted(SUBJECT_TO_FILES.keys(), key=lambda s: s.lower())

def _load_all_topics() -> pd.DataFrame:
    frames = []
    df_md, _ = _read_all_markdown(MD_FOLDER)
    if not df_md.empty:
        frames.append(df_md)
    for f in set().union(*CSV_SUBJECTS.values()) if CSV_SUBJECTS else []:
        try:
            frames.append(_read_csv_strict(f))
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLS)
    df_all = pd.concat(frames, ignore_index=True)
    return df_all.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

def load_questions_for_subjects(selected_subjects: List[str], random_all: bool) -> pd.DataFrame:
    if random_all:
        return _load_all_topics()
    if not selected_subjects:
        return pd.DataFrame(columns=REQUIRED_COLS)
    frames = []
    df_md, _ = _read_all_markdown(MD_FOLDER)
    if not df_md.empty:
        frames.append(df_md[df_md["subject"].isin(selected_subjects)])
    files_to_read = set()
    for subj in selected_subjects:
        files_to_read |= CSV_SUBJECTS.get(subj, set())
    for f in files_to_read:
        try:
            df = _read_csv_strict(f)
            frames.append(df[df["subject"].isin(selected_subjects)])
        except Exception:
            pass
    if not frames:
        return pd.DataFrame(columns=REQUIRED_COLS)
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)

# ============================= Review system (NEW) =============================
def _first_heading(md: str) -> str:
    for line in md.splitlines():
        if line.strip().startswith("#"):
            return line.lstrip("#").strip()
    return ""

def _parse_optional_front_matter(md: str) -> Tuple[Dict[str,str], str]:
    m = FRONTMATTER_RE.match(md)
    if not m:
        return {}, md
    fm, body = m.group(1), m.group(2)
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k,v = line.split(":",1)
            meta[k.strip()] = v.strip()
    return meta, body.strip()

def discover_review_topics(review_folder: str) -> Dict[str, str]:
    """Returns {display_title: file_path} for .md files in review folder."""
    topics: Dict[str, str] = {}
    for path in sorted(glob.glob(os.path.join(review_folder, "*.md"))):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            meta, body = _parse_optional_front_matter(raw)
            title = meta.get("title") or meta.get("subject") or _first_heading(body)
            if not title:
                # fallback to filename
                title = os.path.splitext(os.path.basename(path))[0].replace("_", " ").strip()
            topics[title] = path
        except Exception:
            continue
    return topics

def read_review_markdown(path: str) -> Tuple[str, str]:
    """Returns (title, body) from a review .md. Title comes from front-matter 'title'/'subject' or first H1."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    meta, body = _parse_optional_front_matter(raw)
    title = meta.get("title") or meta.get("subject") or _first_heading(body)
    if not title:
        title = os.path.splitext(os.path.basename(path))[0].replace("_", " ").strip()
    return title, body

# ============================= Quiz state & UI =============================
def init_session_state(n:int):
    st.session_state.answers  = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current  = 0
    st.session_state.finished = False

def render_header(n:int, title_text:str):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)  # anti-clipping spacer

    left, right = st.columns([6,6])
    with left:
        st.markdown(f"<div class='top-title'>{title_text}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='q-progress'><div style='width:{pct}%'></div></div>", unsafe_allow_html=True)
        st.caption(f"Question {pos+1} of {n}")
    with right:
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("Previous", disabled=(pos==0)): st.session_state.current = max(pos-1,0)
        if c2.button("Next", disabled=(pos==n-1)):   st.session_state.current = min(pos+1,n-1)
        if c3.button("Skip", disabled=(pos==n-1)):   st.session_state.current = min(pos+1,n-1)
        if c4.button("Finish"):                      st.session_state.finished = True
    st.markdown("</div>", unsafe_allow_html=True)

def render_question(pool: pd.DataFrame):
    i = st.session_state.current
    row = pool.iloc[i]
    st.markdown(f"<div class='q-prompt'>{row['stem']}</div>", unsafe_allow_html=True)

    letters = ["A","B","C","D","E"]
    selected = st.radio(
        label="",
        options=letters,
        format_func=lambda L: row[L],
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed",
        key=f"radio_{i}"
    )
    st.session_state.answers[i] = selected

    cols = st.columns([1,6])
    with cols[0]:
        if st.button("Reveal", key=f"reveal_{i}"):
            st.session_state.revealed[i] = True
    with cols[1]:
        if st.session_state.revealed[i]:
            correct = str(row["correct"]).strip().upper()
            verdict_html = (
                "<span class='verdict verdict-ok'>Correct</span>"
                if selected == correct else
                "<span class='verdict verdict-err'>Incorrect</span>"
            )
            st.markdown(verdict_html, unsafe_allow_html=True)

    if st.session_state.revealed[i] and str(row["explanation"]).strip():
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

# ============================= Sidebar =============================
with st.sidebar:
    # ---------- Quiz builder ----------
    st.header("Build Quiz")

    SUBJECT_OPTIONS = sorted(SUBJECT_TO_FILES.keys(), key=lambda s: s.lower())
    if not SUBJECT_OPTIONS:
        st.error(f"No subjects found. Put .md files in `{MD_FOLDER}` with proper YAML front-matter, then reload.")
        # do not st.stop(); allow review mode even if no questions yet

    random_all = st.toggle("Random from all topics", value=False, disabled=(len(SUBJECT_OPTIONS)==0))
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS, disabled=random_all or (len(SUBJECT_OPTIONS)==0))

    df = load_questions_for_subjects(pick_subjects, random_all=random_all) if SUBJECT_OPTIONS else pd.DataFrame(columns=REQUIRED_COLS)
    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5

    n_questions = st.number_input("Number of Questions",
                                  min_value=min_q, max_value=max_q,
                                  step=step_q, value=default_q,
                                  disabled=(total == 0))

    if st.button("Start ▶", disabled=(total == 0)):
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
            # If we were in review mode, exit it
            st.session_state.mode = "quiz"
            st.session_state.review_path = None

    st.divider()

    # ---------- Review topic (NEW) ----------
    st.header("Review topic")
    reviews_map = discover_review_topics(REVIEW_FOLDER)  # {display_title: path}
    if not reviews_map:
        st.info(f"Put review .md files in `{REVIEW_FOLDER}` to enable topic review.")
        selected_review_title = None
    else:
        selected_review_title = st.selectbox("Choose a topic to review", options=sorted(reviews_map.keys(), key=str.lower))

    c1, c2 = st.columns(2)
    with c1:
        open_ok = st.button("Open Review 📖", disabled=(selected_review_title is None))
    with c2:
        clear_ok = st.button("Close Review")

    if open_ok and selected_review_title:
        st.session_state.review_path = reviews_map[selected_review_title]
        st.session_state.mode = "review"
    if clear_ok:
        st.session_state.review_path = None
        # If there is a quiz loaded, return to it; otherwise just clear mode
        st.session_state.mode = "quiz" if st.session_state.get("pool") is not None else None

# ============================= Main =============================
mode = st.session_state.get("mode")
review_path = st.session_state.get("review_path")
pool = st.session_state.get("pool")

# ---- Review mode view (NEW) ----
if mode == "review" and review_path:
    try:
        title, body = read_review_markdown(review_path)
        st.markdown(f"<div class='review-title'>{title}</div>", unsafe_allow_html=True)
        _render_markdown_with_svg(body, scoped=False)
    except Exception as e:
        st.error(f"Could not open review: {e}")
    st.stop()

# ---- Quiz flow (existing) ----
if pool is None:
    st.write("Use the sidebar to start a quiz or open a review lecture.")
    st.stop()

title_text = "Random Mix" if st.session_state.get("random_all") else ", ".join(st.session_state.get("selected_subjects", [])) or "PSITE"
render_header(len(pool), title_text)
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
