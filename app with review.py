import os
import glob
import json
import re
from typing import List, Dict, Set, Tuple, Optional
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="PSITE", page_icon=None, layout="wide")

# ============================= Base UI CSS =============================
st.markdown("""
<style>
:root { --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280; }
html, body { height:auto!important; overflow-y:auto!important; }
.block-container { padding-top:1.1rem!important; padding-bottom:0.9rem!important; }

/* Sticky quiz header */
.sticky-top { position: sticky; top: 0; z-index: 1000; background: #fff; border-bottom: 1px solid #eef0f3;
  padding: 0.85rem 0.6rem 0.6rem; overflow: visible; box-sizing: border-box; }
.top-title { font-weight:600; font-size:1.06rem; margin:0 0 .3rem 0; }
.q-progress { height:6px; background:#eef0f3; border-radius:999px; overflow:hidden; margin:0 0 6px 0; }
.q-progress>div { height:100%; background:var(--accent); width:0%; transition:width .25s ease; }

.stButton>button { border-radius: 8px !important; }
.q-prompt { border:1px solid var(--card-border); background:#fafbfc; border-radius:10px; padding:12px; margin-bottom:6px; }

div[role="radiogroup"]>label { padding:8px 4px!important; margin:2px 0!important; border-radius:6px; }
div[role="radiogroup"]>label:hover { background:#f5f7fb!important; }

.verdict { font-weight:600; padding:.22rem .6rem; border-radius:999px; border:1px solid transparent; display:inline-flex; align-items:center; }
.verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
.verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }

.explain-plain { padding-top:8px; }

/* Nav header look (no emojis) */
.nav-tabs { display:flex; gap:10px; border-bottom:1px solid #eef0f3; margin-bottom:12px; }
.tab { padding:8px 12px; border:1px solid #e5e7eb; border-bottom:none; border-radius:8px 8px 0 0; background:#f9fafb; font-weight:600; }
.tab.active { background:#fff; border-color:#d1d5db; }

/* Topics UI (3 columns) */
.topic-grid { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap:12px; }
.topic-card { border:1px solid #e5e7eb; border-radius:12px; background:#fff; padding:10px; display:flex; flex-direction:column; gap:8px; }
.topic-title { font-weight:600; line-height:1.25; font-size:.98rem; }
.topic-actions { display:flex; gap:8px; flex-wrap:wrap; }
.badge-done { display:inline-block; font-size:.78rem; padding:2px 8px; border:1px solid #10b98166; border-radius:999px; background:#10b98114; color:#065f46; }

/* Review page */
.review-header { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; }
.review-title { font-weight:700; font-size:1.25rem; }
.review-meta { color:#6b7280; font-size:.9rem; }

/* Avoid H clipping when a section renders first beneath sticky header */
.top-spacer { height: 10px; }
</style>
""", unsafe_allow_html=True)

# ============================= Paths =============================
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER    = os.getenv("QBANK_DATA_DIR", os.path.join(BASE_DIR, "data"))
MD_FOLDER      = os.getenv("QBANK_MD_DIR", os.path.join(DATA_FOLDER, "questions"))
REVIEWS_FOLDER = os.path.join(DATA_FOLDER, "reviews")
PROGRESS_PATH  = os.path.join(DATA_FOLDER, "tracker_progress.json")

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(MD_FOLDER, exist_ok=True)
os.makedirs(REVIEWS_FOLDER, exist_ok=True)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# ============================= Markdown rendering helpers =============================
SVG_BLOCK_RE = re.compile(r"(<svg[\s\S]*?</svg>)", re.IGNORECASE)
EXPLAIN_SCOPE_CSS = """
<style>
.explain-scope { font-family: 'Segoe UI', Arial, sans-serif; font-size: 1.02rem; line-height: 1.55; color:#222; }
.explain-scope table { border-collapse:collapse; width:100%; margin:.4rem 0; border:2px solid #444; }
.explain-scope th, td { border:1px solid #d1d5db; padding:.45rem .5rem; text-align:center; }
.explain-scope thead th { background:#1d4ed8; color:white; border-color:#1d4ed8; }
.explain-scope tr:nth-child(even) { background:#f9fafb; }
</style>
"""
def render_explanation_block(explain_text: str):
    if not explain_text or not str(explain_text).strip():
        return
    st.markdown("<div class='explain-scope'>", unsafe_allow_html=True)
    st.markdown(EXPLAIN_SCOPE_CSS, unsafe_allow_html=True)
    parts = SVG_BLOCK_RE.split(explain_text)
    for chunk in parts:
        if not chunk or not chunk.strip():
            continue
        if chunk.lstrip().lower().startswith("<svg"):
            m = re.search(r'height="(\d+)"', chunk, re.IGNORECASE)
            height = int(m.group(1)) if m else 320
            components.html(chunk, height=height + 20, scrolling=False)
        else:
            st.markdown(chunk, unsafe_allow_html=False)
    st.markdown("</div>", unsafe_allow_html=True)

# ============================= Question loaders =============================
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

# ============================= Topics list (ordered) =============================
TOPIC_TRACKER = [
    # Foundations / Physiology
    "Fluids/and/Electrolytes","Nutrition","Pediatric Anesthesia/and/Pain Management",
    "Neonatal Physiology/and/Pathophysiology: Transition from Fetal Circulation/Cardiovascular Monitoring/Shock",
    "Lung Physiology/Pathophysiology/Ventilators/Pneumonia","ARDS","Coagulation",
    # Neonatal congenital abdomen
    "Neonatal Obstruction","Duodenal Atresia/Stenosis/Webs/Annular Pancreas","Intestinal Atresia","Malrotation",
    "Meconium Ileus/Peritonitis/Plug","Necrotizing Enterocolitis",
    # Abdominal wall
    "Gastroschisis","Omphalocele","Umbilical Hernia/and/Other Umbilical Disorders",
    # Esophagus & foregut
    "Esophageal Atresia/and/Tracheoesophageal Fistula","Esophageal Stenosis/Webs/Diverticuli",
    "Esophageal Stricture: Caustic Ingestion/and/Other Causes","Esophageal Perforation","Esophageal Replacement","Esophagoscopy",
    "Gastroesophageal Reflux/Barrett’s Esophagus","Gastric Volvulus","Peptic Ulcer Disease",
    # Airway & thoracic congenital
    "Congenital Diaphragmatic Hernia","Eventration of the Diaphragm","Lobar Emphysema","Cystic Pulmonary Airway Malformation",
    "Pulmonary Sequestration","Cystic Diseases of the Lung","Chylothorax","Empyema","Pneumothorax","Pulmonary Abscess",
    "Pulmonary Hypoplasia/Hypertension","Vascular Ring/and/Pulmonary Artery Sling","Tracheomalacia",
    # Airway foreign bodies / bronchoscopy
    "Tracheobronchial Foreign Bodies","Bronchoscopy","Laryngomalacia",
    # Hepatobiliary / portal
    "Biliary Atresia","Choledochal Cysts","Gallbladder Disease/Gallstones","Hepatic Infections: Hepatitis/Abscess/Cysts","Portal Hypertension",
    # Small bowel / colorectal
    "Hirschsprung Disease","Inflammatory Bowel Disease","Short Bowel Syndrome/Intestinal Failure","Gastrointestinal Bleeding","Polyps",
    "Alimentary Tract Duplications","Mesenteric/and/Omental Cysts","Ascites: Chylous","Omphalomesenteric Duct Remnants/Urachus/and/Meckel’s",
    "Abdominal Pain","Neonatal Gastric Perforation",
    # Pediatric urology / endocrine / thyroid
    "Inguinal Hernia","Undescended Testicle (Cryptorchidism)","Torsions: Appendix Testes/Testicular",
    "Circumcision/and/Abnormalities of the Urethra/Penis/Scrotum","Disorders of Sexual Development","Ovarian Torsion/Cysts/and/Tumors",
    "Ovarian/and/Adnexal Problems","Renal Diseases: Nephrotic Syndrome/DI/Renal Vein Thrombosis/Chronic Failure/Prune Belly Syndrome",
    "Endocrine Diseases","Thyroid Nodules","Thyroglossal Duct Cyst/Sinus","Vaginal Atresia/Hydrometrocolpos",
    # Head & neck / vascular / skin / lymph
    "Branchial Cleft/Arch Anomalies","Breast Disorders","Torticollis","Lymphadenopathy/Atypical Mycobacteria",
    "Vascular Anomalies","Dermoid/Epidermoid Cysts/Soft Tissue Nodules","Subacute Bacterial Endocarditis Prophylaxis","Patent Ductus Arteriosus",
    "Prenatal Anomalies/and/Therapy","Mediastinal Cysts/Masses",
    # Oncology
    "Abdominal Mass/in/the/Newborn","Benign Liver Tumors: Hepatic Mesenchymal Hamartoma/Adenoma/FNH",
    "Malignant Liver Tumors: Hepatoblastoma/Hepatocellular Carcinoma","Lung/and/Chest Wall Tumors",
    "Gastrointestinal Tumors","Bone Tumors: Osteogenic Sarcoma/Ewing Sarcoma","Rhabdomyosarcoma","Neuroblastoma",
    "Wilms Tumor/Renal Cell Carcinoma/and/Hemihypertrophy","Mesoblastic Nephroma","Testicular Tumors","Lymphoma/Leukemia",
    "Nevi/Melanoma","Adrenal Cancer","Chemo/Radiation Therapy/Immunotherapy Concepts/Genetics","Splenic Diseases","Teratoma",
    # Trauma / Critical care
    "Trauma: Initial Assessment/and/Resuscitation","Thoracic Trauma","Abdominal Trauma","Musculoskeletal Trauma: Pelvis/Long Bone",
    "Cardiovascular Trauma: Tamponade/Contusion/Arch Disruption/Peripheral Vascular Injuries","Nonaccidental Injuries: Diagnosis/Evaluation/Legal Issues",
    "Burns: Resuscitation/Airway/Electrical/Nutrition/Wound/Sepsis","Extracorporeal Life Support","Acute Renal Failure","Neurosurgical Trauma",
    # Transplant
    "Transplantation"
]

def _slug(s: str) -> str:
    s2 = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s2[:100]

# ============================= Progress persistence =============================
def _load_progress() -> Dict[str, bool]:
    if os.path.exists(PROGRESS_PATH):
        try:
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for t in TOPIC_TRACKER:
                data.setdefault(t, False)
            return data
        except Exception:
            pass
    return {t: False for t in TOPIC_TRACKER}

def _save_progress(d: Dict[str, bool]):
    try:
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

if "progress" not in st.session_state:
    st.session_state.progress = _load_progress()
if "_progress_serial" not in st.session_state:
    st.session_state._progress_serial = json.dumps(st.session_state.progress, sort_keys=True)

# ============================= App mode / routing =============================
if "mode" not in st.session_state:
    st.session_state.mode = "topics"  # "topics" | "review" | "quiz"
if "active_topic" not in st.session_state:
    st.session_state.active_topic = None

# ============================= Review loader =============================
def _find_review_file_for_topic(topic: str) -> Optional[str]:
    slug = _slug(topic)
    exact = os.path.join(REVIEWS_FOLDER, f"{slug}.md")
    if os.path.exists(exact):
        return exact
    # pattern match
    for p in sorted(glob.glob(os.path.join(REVIEWS_FOLDER, "*.md"))):
        base = os.path.splitext(os.path.basename(p))[0].lower()
        if base.startswith(slug):
            return p
    # look into simple title/frontmatter
    for p in sorted(glob.glob(os.path.join(REVIEWS_FOLDER, "*.md"))):
        try:
            with open(p, "r", encoding="utf-8") as f:
                txt = f.read(4096)
            m = re.search(r"^---\s*([\s\S]*?)\s*---", txt, re.MULTILINE)
            title = None
            if m:
                for line in m.group(1).splitlines():
                    if line.lower().startswith("title:"):
                        title = line.split(":",1)[1].strip().strip('"').strip("'")
                        break
            if not title:
                h = re.search(r"^\s*#\s+(.+)$", txt, re.MULTILINE)
                if h:
                    title = h.group(1).strip()
            if title and topic.lower() in title.lower():
                return p
        except Exception:
            continue
    return None

def render_review(topic: str):
    st.markdown("<div class='top-spacer'></div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-tabs'>"
                "<div class='tab'>Topics</div>"
                "<div class='tab active'>Review</div>"
                "<div class='tab'>Quiz</div>"
                "</div>", unsafe_allow_html=True)
    st.markdown("<div class='review-header'>"
                f"<div class='review-title'>{topic}</div>"
                f"<div class='review-meta'>Review</div>"
                "</div>", unsafe_allow_html=True)
    p = _find_review_file_for_topic(topic)
    if not p:
        st.info(f"No review uploaded yet for this topic. Place a Markdown file in `data/reviews/` "
                f"(e.g., `{_slug(topic)}.md`).")
        return
    with open(p, "r", encoding="utf-8") as f:
        txt = f.read()
    fm = FRONTMATTER_RE.match(txt)
    body = txt if not fm else fm.group(2).strip()
    st.markdown(body, unsafe_allow_html=True)

# ============================= Quiz state & UI =============================
def init_quiz_state(n:int):
    st.session_state.answers  = [None]*n
    st.session_state.revealed = [False]*n
    st.session_state.current  = 0
    st.session_state.finished = False

def render_header(n:int, title_text:str):
    pos = st.session_state.current
    pct = int(((pos + 1) / max(n,1)) * 100)
    st.markdown("<div class='sticky-top'>", unsafe_allow_html=True)
    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)
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
        label="", options=letters,
        format_func=lambda L: row[L],
        index=(letters.index(st.session_state.answers[i]) if st.session_state.answers[i] in letters else None),
        label_visibility="collapsed", key=f"radio_{i}"
    )
    st.session_state.answers[i] = selected
    cols = st.columns([1,6])
    with cols[0]:
        if st.button("Reveal", key=f"reveal_{i}"):
            st.session_state.revealed[i] = True
    with cols[1]:
        if st.session_state.revealed[i]:
            correct = str(row["correct"]).strip().upper()
            verdict_html = ("<span class='verdict verdict-ok'>Correct</span>" if selected == correct
                            else "<span class='verdict verdict-err'>Incorrect</span>")
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
        init_quiz_state(len(pool))

# ============================= Sidebar (always available) =============================
with st.sidebar:
    tabs = st.segmented_control(
        "Navigation",
        options=["Topics","Review","Quiz"],
        default=("Review" if st.session_state.mode=="review" else ("Quiz" if st.session_state.mode=="quiz" else "Topics"))
    )
    st.session_state.mode = "topics" if tabs=="Topics" else ("review" if tabs=="Review" else "quiz")

    st.markdown("---")
    st.subheader("Quiz")

    SUBJECT_OPTIONS = sorted(SUBJECT_TO_FILES.keys(), key=lambda s: s.lower())
    random_all = st.toggle("Random from all subjects", value=False)
    pick_subjects = st.multiselect("Subjects", SUBJECT_OPTIONS, disabled=random_all)

    df_quiz = load_questions_for_subjects(pick_subjects, random_all=random_all)
    total = len(df_quiz)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5
    n_questions = st.number_input("Number of Questions", min_value=min_q, max_value=max_q,
                                  step=step_q, value=default_q)

    if st.button("Start Quiz"):
        if df_quiz.empty:
            st.warning("No questions available for the current selection.")
        else:
            pool = (df_quiz.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
                    if len(df_quiz) > n_questions
                    else df_quiz.sample(frac=1.0, random_state=42).reset_index(drop=True))
            st.session_state.pool = pool
            init_quiz_state(len(pool))
            st.session_state.mode = "quiz"
            st.session_state.selected_subjects = pick_subjects
            st.session_state.random_all = random_all

# ============================= Topics Page =============================
def render_topics_page():
    prog: Dict[str, bool] = st.session_state.progress
    st.markdown("<div class='top-spacer'></div>", unsafe_allow_html=True)
    st.markdown("<div class='nav-tabs'>"
                "<div class='tab active'>Topics</div>"
                "<div class='tab'>Review</div>"
                "<div class='tab'>Quiz</div>"
                "</div>", unsafe_allow_html=True)

    st.subheader("All Topics")
    completed = sum(bool(prog.get(t, False)) for t in TOPIC_TRACKER)
    st.caption(f"Completed: {completed}/{len(TOPIC_TRACKER)} ({int(100*completed/len(TOPIC_TRACKER))}%)")

    top_cols = st.columns([2,1,1])
    with top_cols[0]:
        query = st.text_input("Search", "", placeholder="filter topics…")
    with top_cols[1]:
        only_incomplete = st.toggle("Only incomplete", value=False)
    with top_cols[2]:
        bulk_done = st.button("Mark all visible done")

    filtered = [t for t in TOPIC_TRACKER if (query.lower() in t.lower())]
    if only_incomplete:
        filtered = [t for t in filtered if not prog.get(t, False)]

    if bulk_done:
        for t in filtered:
            prog[t] = True

    st.markdown("<div class='topic-grid'>", unsafe_allow_html=True)
    cols = st.columns(3)
    for i, topic in enumerate(filtered):
        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"<div class='topic-card'>", unsafe_allow_html=True)
                st.markdown(f"<div class='topic-title'>{topic}</div>", unsafe_allow_html=True)

                key_chk = f"done_{_slug(topic)}"
                checked = st.checkbox("Completed", value=prog.get(topic, False), key=key_chk)
                prog[topic] = checked

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Open Review", key=f"open_{_slug(topic)}"):
                        st.session_state.active_topic = topic
                        st.session_state.mode = "review"
                with c2:
                    if st.button("Start Quiz", key=f"quiz_{_slug(topic)}"):
                        if topic in SUBJECT_TO_FILES:
                            df = load_questions_for_subjects([topic], random_all=False)
                        else:
                            df = pd.DataFrame(columns=REQUIRED_COLS)
                        if df.empty:
                            st.warning("No questions found for this topic. Add .md files to data/questions/.")
                        else:
                            st.session_state.pool = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
                            init_quiz_state(len(st.session_state.pool))
                            st.session_state.mode = "quiz"
                            st.session_state.active_topic = topic
                            st.session_state.selected_subjects = [topic]
                            st.session_state.random_all = False

                if prog.get(topic, False):
                    st.markdown("<span class='badge-done'>Completed</span>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Auto-save progress if changed
    current_serial = json.dumps(prog, sort_keys=True)
    if current_serial != st.session_state._progress_serial:
        _save_progress(prog)
        st.session_state._progress_serial = current_serial

# ============================= Main Router =============================
if st.session_state.mode == "topics":
    render_topics_page()

elif st.session_state.mode == "review":
    if not st.session_state.active_topic:
        st.info("Pick a topic from the Topics page to open its review.")
    else:
        render_review(st.session_state.active_topic)

elif st.session_state.mode == "quiz":
    st.markdown("<div class='nav-tabs'>"
                "<div class='tab'>Topics</div>"
                "<div class='tab'>Review</div>"
                "<div class='tab active'>Quiz</div>"
                "</div>", unsafe_allow_html=True)
    pool = st.session_state.get("pool")
    if pool is None or pool.empty:
        st.write("Configure and start a quiz from the sidebar.")
    else:
        title_text = (st.session_state.active_topic or
                      ("Random Mix" if st.session_state.get("random_all") else
                       ", ".join(st.session_state.get("selected_subjects", [])) or "PSITE"))
        render_header(len(pool), title_text)
        if st.session_state.finished:
            render_results(pool)
        else:
            render_question(pool)
