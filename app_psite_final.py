st.markdown(
    """
    <style>
    :root {
      --card-bg:#ffffff; --card-border:#e6e8ec; --accent:#1d4ed8; --muted:#6b7280;
      /* >>> tweak these two to taste <<< */
      --q-font: 1.22rem;   /* question stem font size */
      --a-font: 1.08rem;   /* answer choice font size */
    }

    /* Global scrolling & overflow fixes */
    html, body { height: auto !important; overflow-y: auto !important; }
    .block-container { padding-top: 1.1rem !important; padding-bottom: 0.8rem !important; }
    [data-testid="stHorizontalBlock"] { overflow: visible !important; }
    [data-testid="stAppViewContainer"], [data-testid="stMain"] { overflow-y: auto !important; }

    /* Sticky header */
    .sticky-top {
      position: sticky; top: 0; z-index: 100; background: white;
      padding: .65rem .5rem .5rem .5rem; border-bottom: 1px solid #eef0f3;
      overflow: visible; box-shadow: 0 1px 0 rgba(0,0,0,0.02); margin-bottom: .35rem;
    }
    .top-title { font-weight: 600; letter-spacing:.2px; font-size:1.05rem; line-height:1.25; margin:0 0 .25rem 0; white-space:nowrap; overflow:visible; }
    .q-progress { height: 6px; background:#eef0f3; border-radius: 999px; overflow: hidden; margin: 0 0 4px 0; }
    .q-progress > div { height:100%; background: var(--accent); width:0%; transition: width .25s ease; }

    /* Header controls */
    .hdr-row { display:flex; gap:.5rem; justify-content:flex-end; align-items:center; flex-wrap:wrap; }
    .stButton>button { padding:.4rem .85rem; border-radius:8px; line-height:1.25; }

    /* Flat outer container; only the stem uses a soft bubble */
    .q-card { border:none; background:transparent; padding:0; box-shadow:none; }
    .q-prompt {
      border:1px solid var(--card-border); background:#fafbfc; border-radius:10px;
      padding:12px; margin:0 0 8px 0;
      font-size: var(--q-font); line-height: 1.6;   /* BIGGER STEM */
    }

    /* Choices: clean list, no per-choice bubbles; BIGGER text */
    div[role="radiogroup"] { gap: 0 !important; }
    div[role="radiogroup"] > label {
      border:none !important; background:transparent !important;
      padding:8px 4px !important; margin:2px 0 !important; border-radius:6px;
      transition: background-color .15s ease;
    }
    div[role="radiogroup"] > label:hover { background:#f5f7fb !important; }
    /* Ensure the text inside the choice grows (Streamlit nests it in a <p>) */
    div[role="radiogroup"] > label p {
      font-size: var(--a-font) !important; line-height: 1.5 !important; margin: 0 !important;
    }
    /* Selected state: subtle underline */
    div[role="radiogroup"] input:checked + div > p { text-decoration: underline; text-underline-offset: 3px; }

    /* Reveal row: minimal verdict inline; NO extra margins */
    .q-actions-row { display:flex; align-items:center; gap:.6rem; margin:0; }
    .verdict {
      display:inline-flex; align-items:center; font-weight:600; padding:.22rem .6rem;
      border-radius:999px; white-space:nowrap; border:1px solid transparent;
      font-size: 0.95rem;
    }
    .verdict-ok  { background:#10b9811a; color:#065f46; border-color:#34d399; }
    .verdict-err { background:#ef44441a; color:#7f1d1d; border-color:#fca5a5; }

    /* Explanation: plain background (no bubble) */
    .explain-plain {
      margin-top:0; padding:10px 0 0 0; background:transparent !important;
      border:none !important; box-shadow:none !important;
      font-size: 1rem; line-height: 1.55;  /* optional bump for readability */
    }

    .stDivider { margin:8px 0 !important; }
    .stMarkdown p { margin-bottom:0.35rem; }

    /* Slightly larger on small screens for accessibility */
    @media (max-width: 900px) {
      :root { --q-font: 1.28rem; --a-font: 1.12rem; }
    }
    </style>
    """,
    unsafe_allow_html=True
)
