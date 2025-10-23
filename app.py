import streamlit as st
import pandas as pd
import numpy as np
import os

st.set_page_config(page_title="Simple Question Bank", page_icon="🧠", layout="centered")
st.title("🧠 Simple Question Bank")
st.caption("CSV-only • One question at a time • Minimal & reliable")

DATA_DIR = "data"
REQUIRED = ["Question","A","B","C","D","E","Correct","Explanation","Reference","Category","Difficulty"]

# --- Sidebar controls (very small) ---
with st.sidebar:
    st.header("Controls")
    show_diag = st.toggle("Show diagnostics", value=False)
    review_mode = st.toggle("Review mode (no grading)", value=False)
    shuffle = st.toggle("Shuffle questions", value=True)

def diag(msg):
    if show_diag:
        st.sidebar.write(msg)

# --- Find CSV files ---
if not os.path.isdir(DATA_DIR):
    st.error("Missing `data/` folder at repo root. Create it and add at least one CSV.")
    st.stop()

csv_files = sorted([f for f in os.listdir(DATA_DIR)
                    if f.lower().endswith(".csv") and not f.startswith(".")])

diag({"csv_files": csv_files})

if not csv_files:
    st.error("No CSV files found in `data/`. Add at least one CSV with headers:\n" + ", ".join(REQUIRED))
    st.stop()

# Pick one set (simpler & more robust)
file_choice = st.sidebar.selectbox("Question set", options=csv_files, index=0)

# --- Load CSV robustly ---
def load_csv(path: str) -> pd.DataFrame:
    full = os.path.join(DATA_DIR, path)
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(full, encoding=enc, dtype=str,
                             keep_default_na=False, na_filter=False, low_memory=False)
            df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
            missing = [c for c in REQUIRED if c not in df.columns]
            if missing:
                raise ValueError(f"{path}: missing columns {missing}")
            for c in ["Question","A","B","C","D","E","Explanation","Reference","Category","Difficulty"]:
                df[c] = df[c].astype(str).str.strip()
            df["Correct"] = df["Correct"].astype(str).str.strip().str.upper()
            return df
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to read {path}: {last_err}")

try:
    df = load_csv(file_choice)
except Exception as e:
    st.error(f"Could not load `{file_choice}`: {e}")
    st.stop()

# --- Filters (kept minimal) ---
cats = sorted([c for c in df["Category"].dropna().unique() if c])
diffs = sorted([d for d in df["Difficulty"].dropna().unique() if d])

with st.sidebar.expander("Filters", expanded=False):
    sel_cats = st.multiselect("Category", cats, default=[])
    sel_diffs = st.multiselect("Difficulty", diffs, default=[])

mask = pd.Series(True, index=df.index)
if sel_cats:
    mask &= df["Category"].isin(sel_cats)
if sel_diffs:
    mask &= df["Difficulty"].isin(sel_diffs)
sub = df[mask].reset_index(drop=True)

if len(sub) == 0:
    st.warning("No questions match current filters.")
    st.stop()

# --- Session state (tiny) ---
if "order" not in st.session_state or st.session_state.get("last_file") != file_choice:
    st.session_state.order = list(range(len(sub)))
    if shuffle:
        np.random.default_rng().shuffle(st.session_state.order)
    st.session_state.pos = 0
    st.session_state.answers = {}
    st.session_state.last_file = file_choice

# Rebuild order if filter changed the available count
if len(st.session_state.order) != len(sub):
    st.session_state.order = list(range(len(sub)))
    if shuffle:
        np.random.default_rng().shuffle(st.session_state.order)
    st.session_state.pos = 0
    st.session_state.answers = {}

# --- Current question ---
idx = st.session_state.order[st.session_state.pos]
q = sub.loc[idx]

answered = len(st.session_state.answers)
total = len(st.session_state.order)
pct = int(100 * answered / total) if total else 0
st.progress(pct / 100, text=f"Progress: {answered}/{total} • {pct}%")

# Small badges row
bits = []
if q["Category"]:
    bits.append(f"**Category:** {q['Category']}")
if q["Difficulty"]:
    bits.append(f"**Difficulty:** {q['Difficulty']}")
if bits:
    st.write(" | ".join(bits))

st.markdown("---")
st.subheader(f"Q{st.session_state.pos + 1}")
st.write(q["Question"])

choices = {"A": q["A"], "B": q["B"], "C": q["C"], "D": q["D"], "E": q["E"]}
options = [f"{k}. {v}" for k, v in choices.items()]

prev_choice = st.session_state.answers.get(st.session_state.pos, {}).get("choice")
default_index = list(choices.keys()).index(prev_choice) if prev_choice in choices else 0
picked = st.radio("Choose one:", options, index=default_index, key=f"radio_{st.session_state.pos}")
picked_letter = picked.split(".")[0]

cols = st.columns([1,1,6])
if cols[0].button("✅ Submit", disabled=review_mode):
    correct = (picked_letter == q["Correct"])
    st.session_state.answers[st.session_state.pos] = {"choice": picked_letter, "correct": correct}
    if correct:
        st.success("Correct ✅")
    else:
        st.error(f"Incorrect ❌ — Correct: **{q['Correct']}**")

show_expl = st.toggle("Show explanation", value=False, key=f"expl_{st.session_state.pos}")
if show_expl:
    st.info(q["Explanation"])
    if str(q["Reference"]).lower().startswith(("http://","https://")):
        st.markdown(f"[Reference]({q['Reference']})")

# Nav
n1, n2 = st.columns(2)
if n1.button("⬅️ Previous", disabled=st.session_state.pos == 0):
    st.session_state.pos = max(0, st.session_state.pos - 1)
    st.rerun()
if n2.button("Next ➡️", disabled=st.session_state.pos >= total - 1):
    st.session_state.pos = min(total - 1, st.session_state.pos + 1)
    st.rerun()

# Diagnostics
if show_diag:
    st.sidebar.write("Current file:", file_choice)
    st.sidebar.write("Questions in set:", len(df))
    st.sidebar.write("After filters:", len(sub))
    st.sidebar.write("Order len:", len(st.session_state.order))
    st.sidebar.write("Position:", st.session_state.pos + 1, "/", len(st.session_state.order))
