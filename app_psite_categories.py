import os
import json
import random
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
    /* Clean radio list */
    div[role="radiogroup"] > label { padding:8px 10px; border:1px solid var(--card-border); border-radius:10px; margin-bottom:8px; }
    </style>
    """, unsafe_allow_html=True
)

REQUIRED_COLS = ["id","subject","stem","A","B","C","D","E","correct","explanation"]

# Fixed PSITE subject categories
SUBJECT_OPTIONS = ['Bronchoscopy', 'Chest Wall Deformities: Pectus Excavatum/Carinatum, Marfan’s and Poland’s Syndromes', 'Chylothorax', 'Congenital Diaphragmatic Hernia', 'Cystic Diseases of the Lung', 'Cystic Fibrosis', 'Cystic Pulmonary Airway Malformation', 'Empyema', 'Esophageal Atresia and Tracheoesophageal Fistula', 'Esophageal Perforation', 'Esophageal Replacement', 'Esophageal Stenosis, Webs, Diverticuli', 'Esophageal Stricture: Caustic Ingestion and Other Causes', 'Esophagoscopy', 'Eventration of the Diaphragm', "Gastroesophageal Reflux/Barrett's Esophagus", 'Laryngomalacia', 'Lobar Emphysema', 'Mediastinal Cysts, Masses', 'Patent Ductus Arteriosus', 'Pneumothorax', 'Prenatal Anomalies and Therapy', 'Pulmonary Abscess', 'Pulmonary Hypoplasia/Hypertension', 'Pulmonary Sequestration', 'Subacute Bacterial Endocarditis Prophylaxis', 'Tracheobronchial Foreign Bodies', 'Tracheomalacia', 'Vascular Ring and Pulmonary Artery Sling', 'Abdominal Pain', 'Alimentary Tract Duplications', 'Appendicitis', 'Ascites: Chylous', 'Biliary Atresia', 'Choledochal Cysts', 'Cloacal Exstrophy/Bladder Exstrophy', 'Duodenal Atresia/Stenosis/Webs/Annular Pancreas', 'Gallbladder Disease, Gallstones', 'Gastric Volvulus', 'Gastrointestinal Bleeding', 'Gastroschisis', 'Hepatic Infections: Hepatitis, Abscess, Cysts', 'Hirschsprung Disease', 'Hypertrophic Pyloric Stenosis', 'Inflammatory Bowel Disease', 'Inguinal Hernia', 'Intestinal Atresia', 'Intussusception', 'Malrotation', 'Meconium Ileus/Peritonitis/Plug', 'Mesenteric and Omental Cysts', 'Necrotizing Enterocolitis', 'Neonatal Gastric Perforation', 'Neonatal Obstruction', 'Omphalocele', "Omphalomesenteric Duct Remnants, Urachus, and Meckel's", 'Peptic Ulcer Disease', 'Polyps', 'Portal Hypertension', 'Umbilical Hernia and Other Umbilical Disorders', 'Adrenal Cortical Tumors, Pheochromocytoma', 'Anal Pathology: Fissures, Abscesses, Fistulae, Pilonidal, Prolapse', 'Anorectal Malformation', 'Arterial Diseases and Vasculitis', 'Branchial Cleft, Arch Anomalies', 'Breast Disorders', 'Circumcision and Abnormalities of the Urethra, Penis, Scrotum', 'Disorders of Sexual Development', 'Endocrine Diseases', 'Lymphadenopathy, Atypical Mycobacteria', 'Neurological: Shunt Complications, Dermal Sinuses', 'Ovarian Torsion, Cysts, and Tumors', 'Renal Diseases: Nephrotic Syndrome, DI, Renal Vein Thrombosis, Chronic Failure, Prune Belly Syndrome', 'Thyroglossal Duct Cyst/Sinus', 'Thyroid Nodules', 'Torsions: Appendix Testes, Testicular', 'Torticollis', 'Undescended Testicle (Cryptorchidism)', 'Vaginal Atresia, Hydrometrocolpos', 'Vascular Anomalies', 'Abdominal Trauma', 'Acute Renal Failure', 'ARDS', 'Burns: Resuscitation, Airway, Electrical, Nutrition, Wound, Sepsis', 'Cardiovascular Trauma: Tamponade, Contusion, Arch Disruption, Peripheral Vascular Injuries', 'Coagulation', 'Extracorporeal Life Support', 'Fluids and Electrolytes', 'Hematologic Diseases: Spherocytosis, Sickle Cell, ITP, HSP', 'Lung Physiology, Pathophysiology, Ventilators, Pneumonia', 'Musculoskeletal Trauma: Pelvis, Long Bone', 'Neonatal Physiology and Pathophysiology: Transition from Fetal Circulation, Cardiovascular Monitoring, Shock', 'Neurosurgical Trauma', 'Nonaccidental Injuries: Diagnosis, Evaluation, Legal Issues', 'Nutrition', 'Obesity', 'Pediatric Anesthesia and Pain Management', 'Short Bowel Syndrome/Intestinal Failure', 'Soft Tissue Trauma: Tetanus, Bites, Wound Infection, Crush Injuries', 'Thoracic Trauma', 'Transplantation', 'Trauma: Initial Assessment and Resuscitation', 'Abdominal Mass in the Newborn', 'Adrenal Cancer', 'Benign Liver Tumors: Hepatic Mesenchymal Hamartoma/Adenoma/FNH', 'Bone Tumors: Osteogenic Sarcoma, Ewing Sarcoma', 'Chemo/Radiation Therapy, Immunotherapy Concepts, Genetics', 'Dermoid/Epidermoid Cysts, Soft Tissue Nodules', 'Gastrointestinal Tumors', 'Lung and Chest Wall Tumors', 'Lymphoma/Leukemia', 'Malignant Liver Tumors: Hepatoblastoma/Hepatocellular Carcinoma', 'Mesoblastic Nephroma', 'Neuroblastoma', 'Nevi, Melanoma', 'Ovarian and Adrexal Problems', 'Rhabdomyosarcoma', 'Splenic Diseases', 'Teratoma', 'Testicular Tumors', 'Wilms Tumor, Renal Cell Carcinoma, and Hemihypertrophy']

def load_fixed_csv() -> pd.DataFrame:
    path = os.environ.get("QBANK_CSV_PATH","questions.csv")
    try:
        return pd.read_csv(path)
    except Exception:
        RAW_URL = st.secrets.get("CSV_URL", os.environ.get("CSV_URL",""))
        if RAW_URL:
            try:
                return pd.read_csv(RAW_URL)
            except Exception:
                pass
        return pd.DataFrame()

def validate_df(df: pd.DataFrame) -> List[str]:
    return [c for c in REQUIRED_COLS if c not in df.columns]

def build_quiz_pool(df: pd.DataFrame, subjects: List[str], tags: List[str]) -> pd.DataFrame:
    out = df.copy()
    if subjects:
        out = out[out["subject"].astype(str).isin(subjects)]
    if tags and "tags" in out.columns:
        tag_set = set([t.strip().lower() for t in tags])
        def has_any(cell):
            if pd.isna(cell): return False
            cell_tags = [t.strip().lower() for t in str(cell).split(",")]
            return any(t in tag_set for t in cell_tags)
        out = out[out["tags"].apply(has_any)]
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

# ---- Load Data ----
df = load_fixed_csv()
if df.empty:
    st.error("Question set could not be loaded.")
    st.stop()
missing = validate_df(df)
if missing:
    st.error(f"CSV missing required columns: {missing}")
    st.stop()

if "tags" not in df.columns:
    df["tags"] = ""

# ---- Sidebar ----
with st.sidebar:
    st.header("Build Quiz")
    pick_subjects = st.multiselect("Subject", SUBJECT_OPTIONS)
    tag_opts = sorted({t.strip() for cell in df["tags"].dropna().astype(str).tolist() for t in cell.split(",") if t.strip()})
    pick_tags = st.multiselect("Tags", tag_opts)

    total = len(df)
    min_q = 1 if total >= 1 else 0
    max_q = total if total >= 1 else 1
    default_q = min(20, max_q) if max_q >= 1 else 1
    step_q = 1 if max_q < 10 else 5

    n_questions = st.number_input("Number of Questions", min_value=min_q, max_value=max_q, step=step_q, value=default_q)

    if st.button("Start ▶"):
        pool = build_quiz_pool(df, pick_subjects, pick_tags)
        if pool.empty:
            pool = df.copy().reset_index(drop=True)
        if len(pool) > n_questions:
            pool = pool.sample(n=int(n_questions), random_state=42).reset_index(drop=True)
        else:
            pool = pool.sample(frac=1.0, random_state=42).reset_index(drop=True)
        st.session_state.pool = pool
        init_session_state(len(pool))

pool = st.session_state.get("pool", None)
if pool is None:
    st.write("Use the sidebar to start a quiz.")
    st.stop()

render_header(len(pool))
if st.session_state.finished:
    render_results(pool)
else:
    render_question(pool)
