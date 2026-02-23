import streamlit as st
from pathlib import Path

def apply_goat_theme():
    st.markdown(
        """
<style>
:root{
  --goat-accent:#FF183A;
  --goat-navy:#003E71;
  --goat-teal:#00959C;
  --goat-mint:#6ECDCF;
  --goat-gray:#E8E8E8;
  --goat-bg:#FFFFFF;
  --goat-text:#0F172A;
  --goat-muted:#64748B;
  --goat-border: rgba(15, 23, 42, 0.10);
  --goat-shadow: 0 10px 30px rgba(2, 6, 23, 0.08);
}

.stApp{
  background:var(--goat-bg);
  color:var(--goat-text);
}

section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #FFFFFF 0%, var(--goat-gray) 140%);
  border-right: 1px solid var(--goat-border);
}

h1, h2, h3{
  color:var(--goat-navy);
  letter-spacing:-0.02em;
}

/* Buttons */
div.stButton > button{
  width:100%;
  background:var(--goat-navy);
  color:#fff;
  border: 1px solid rgba(0,0,0,0);
  border-radius:12px;
  padding:0.65rem 0.9rem;
  font-weight:800;
  letter-spacing:0.02em;
  box-shadow:0 6px 18px rgba(0,62,113,0.18);
}
div.stButton > button:hover{
  background:#00355F;
}

/* Labels */
label, .stNumberInput label{
  color: var(--goat-navy) !important;
  font-weight: 800 !important;
}

/* Metrics */
.metric-container{
  border:1px solid var(--goat-border);
  border-radius:18px;
  padding:16px 18px;
  background: linear-gradient(180deg, rgba(110,205,207,0.16) 0%, rgba(232,232,232,0.26) 120%);
  box-shadow:0 8px 20px rgba(2,6,23,0.06);
}
.metric-label{
  font-size:.9rem;
  color:var(--goat-navy);
  font-weight:800;
  letter-spacing:.06em;
  text-transform:uppercase;
}
.metric-value{
  font-size:2.1rem;
  font-weight:900;
  color:var(--goat-accent);
  margin-top:4px;
}
.metric-sub{
  margin-top:4px;
  color:var(--goat-muted);
  font-weight:700;
}

/* File uploader: FIX visibility for titles + filenames */
div[data-testid="stFileUploader"] label{
  color: var(--goat-navy) !important;
  font-weight: 900 !important;
}
div[data-testid="stFileUploader"] small{
  color: var(--goat-muted) !important;
  font-weight: 700 !important;
}
/* File name and size lines inside uploader */
div[data-testid="stFileUploader"] *{
  color: var(--goat-text);
}
/* But keep uploader button readable */
div[data-testid="stFileUploader"] button *{
  color: #FFFFFF !important;
}

</style>
        """,
        unsafe_allow_html=True,
    )

def load_logo(logo_dir: Path, filename: str, width: int | None = None):
    p = logo_dir / filename
    if p.exists():
        st.image(str(p), width=width) if width else st.image(str(p), use_container_width=True)