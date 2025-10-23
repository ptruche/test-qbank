import streamlit as st
import pandas as pd
import numpy as np
import os

# ---------- BASIC PAGE ----------
st.set_page_config(page_title="Simple Question Bank", page_icon="🧠", layout="centered")
st.title("🧠 Simple Question Bank")
st.caption("CSV-only • Minimal • One question at a time")

DATA_DIR = "data"
REQUIRED_COLS = ["Question","A","B","C","D","E","Correct","Explanation","Reference","Category","Difficulty"]

# ---------- DIAGNOSTICS (toggle) ----------
with st.sidebar:
    st.header("Settings")
    show_diag = st.toggle("Show diagnostics", value=False)

def diag(msg):
    if show_diag:
        st.sidebar.write(msg)

# ---------- FILE DISCOVERY ----------
if not os.path.isdir(DATA_DIR):
    st.error("Missing `data/` folder at repo root. Create it and add at least one CSV.")
    st.stop()

csv_files = sorted([f for f in os.listdir(DATA_DIR)
                    if f.lower().endswith(".csv") and not f.startswith(".")])

if show_diag:
    st.sidebar.write("CSV files:", csv_files)

if not csv_files:
    st.error("No CSV files found in `data/`. Add at least one CSV with headers:\n" +
             ", ".join(REQUIRED_COLS))
    st.stop()

# pick sets
use_all = st.sidebar.toggle("Use ALL sets", value=True)
if use_all:
    selected = csv_files
else:
    selected = st.sidebar.multiselect("Choose set(s)", csv_files, default=csv_files[:1])

if not selected:
    st.info("Select at least one CSV on the left.")
    st.stop()

# ---------- LOAD CSVs (robust & simple) ----------
def load_csv(path: str) -> pd.DataFrame:
    full = os.path.join(DATA_DIR, path)
    last_err = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            df = pd.read_csv(full, encoding=enc, dtype=str, keep_default_na=False, na_filter=False, low_memory=False)
            # clean headers
            df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
            # validate
            missing = [c for c in REQUIRED_COLS if c not in df.columns]
            if missing:
                raise ValueError(f"{path}: missing columns {missing}")
            # normalize basic fields
            for c in ["Question","A","B","C","D","E","Explanation","Reference","Category","Difficulty"]:
                df[c] = df[c].astype(str).str.strip()
            df["Correct"] = df["Correct"].astype(str).str.strip().str.upper()
            df["__sourcefile__"] = path
            return df
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Failed to read {path}: {last_err}")

frames = []
errors = []
for f in selected:
    try:
        frames.append(load_csv(f))
    except Exception as e:
        errors.append(f"{f}: {e}")

if errors:
    st.error("Some files failed to load:")
    for e in errors:
        st.code(e)
if not frames:
    st.stop()

df = pd.concat(frames, ignore_index=True)

# ---------- FILTERS (simple) ----------
cats = sorted([c for c in df["Category"].dropna().unique() if c])
diffs = sorted([d for d in df["Difficulty"].dropna().unique() if d])

with st.sidebar.expander("Filters", expanded=False):
    sel_cats = st.multiselect("Category", cats, default=[])
    sel_diffs = st.multiselect("Difficulty", diffs, default=[])
    shuffle = st.toggle("Shuffle questions", value=True)
    review_mode = st.toggle("Review mode (no grading)", value=False)

mask = pd.Series(True, index=df.index)
if sel_cats:  mask &= df["Category"].isin(sel_cats)
if sel_diffs: mask &= df["Difficulty"].isin(sel_diffs)
sub = df[mask].reset_index(drop=True)

if len(sub) == 0:
    st.warning("No questions match the current filters.")
    st.stop()

# ---------- STATE ----------
if "order" not in st.session_state:
    st.session_state.order = list(range(len(sub)))
    if shuffle: np.random.default_rng().shuffle(st.session_state.order)
if "pos" not in st.session_state:
    st.session_state.pos = 0
if "answers" not in st.session_state:
    st.session_state.answers = {}   # pos -> {choice, correct}

# If filter set changed size vs previous, rebuild order
if len(st.session_state.order) != len(sub):
    st.session_state.order = list(range(len(sub)))
    if shuffle: np.random.default_rng().shuffle(st.session_state.order)
    st.session_state.pos = 0
    st.session_state.answers = {}

# ---------- CURRENT QUESTION ----------
idx = st.session_state.order[st.session_state.pos]
q = sub.loc[idx]

# Progress
answered = len(st.session_state.answers)
total = len(st.session_state.order)
pct = int(100 * answered / total) if total else 0
st.progress(pct / 100, text=f"Progress: {answered}/{total} • {pct}%")

# Badge row
badges = []
if q["Category"]: badges.append(f"**Category:** {q['Category']}")
if q["Difficulty"]: badges.append(f"**Difficulty:** {q['Difficulty']}")
if "__sourcefile__" in q and q["__sourcefile__"]: badges.append(f"**Set:** {q['__sourcefile__']}")
if badges: st.write(" | ".join(badges))

st.markdown("---")
st.subheader(f"Q{st.session_state.pos + 1}")
st.write(q["Question"])

choices = {"A": q["A"], "B": q["B"], "C": q["C"], "D": q["D"], "E": q["E"]}
options = [f"{k}. {v}" for k, v in choices.items()]

prev_choice = st.session_state.answers.get(st.session_state.pos, {}).get("choice")
default_index = list(choices.keys()).index(prev_choice) if prev_choice in choices else 0
selected_option = st.radio("Choose one:", options, index=default_index, key=f"radio_{st.session_state.pos}")
picked_letter = selected_option.split(".")[0]

# Actions
cols = st.columns([1,1,6])
if cols[0].button("✅ Submit", disabled=review_mode):
    is_correct = (picked_letter == q["Correct"])
    st.session_state.answers[st.session_state.pos] = {"choice": picked_letter, "correct": is_correct}
    if is_correct: st.success("Correct ✅")
    else: st.error(f"Incorrect ❌ — Correct answer: **{q['Correct']}**")

show_expl = st.toggle("Show explanation", value=False, key=f"expl_{st.session_state.pos}")
if show_expl:
    st.info(q["Explanation"])
    if str(q["Reference"]).lower().startswith(("http://","https://")):
        st.markdown(f"[Reference]({q['Reference']})")

# Nav
with st.container():
    n1, n2 = st.columns(2)
    if n1.button("⬅️ Previous", disabled=st.session_state.pos == 0):
        st.session_state.pos = max(0, st.session_state.pos - 1)
        st.experimental_rerun()
    if n2.button("Next ➡️", disabled=st.session_state.pos >= total - 1):
        st.session_state.pos = min(total - 1, st.session_state.pos + 1)
        st.experimental_rerun()

# Simple performance table
with st.expander("📊 Performance (this session)"):
    if st.session_state.answers:
        rows = []
        for p, rec in st.session_state.answers.items():
            row_idx = st.session_state.order[p]
            rows.append({
                "Q#": p + 1,
                "Category": sub.loc[row_idx, "Category"],
                "Your choice": rec["choice"],
                "Correct": "Yes" if rec["correct"] else "No"
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    else:
        st.write("No graded submissions yet.")
