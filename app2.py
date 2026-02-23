import streamlit as st
import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from html import escape as html_escape
from xml.sax.saxutils import escape as xml_escape
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ==============================================================================
# 0) ENV + PATHS (FIJOS, NO UI)
# ==============================================================================
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs" if (BASE_DIR / "outputs").exists() else (BASE_DIR.parent / "outputs")
LOGO_DIR = BASE_DIR / "logos"

INPUT_PRODUCTS_JSONL = OUTPUTS_DIR / "products_for_long_desc.jsonl"
CATEGORY_CONTEXT_JSONL = OUTPUTS_DIR / "category_context_dir.jsonl"

OUT_LONG_JSONL = OUTPUTS_DIR / "product_long_desc.jsonl"
OUT_SHORT_JSONL = OUTPUTS_DIR / "product_short_desc.jsonl"
OUT_LONG_XML = OUTPUTS_DIR / "delta_web_long_desc.xml"
OUT_SHORT_XML = OUTPUTS_DIR / "delta_web_short_desc.xml"
OUT_CONTEXT_MAP_JSONL = OUTPUTS_DIR / "product_context_map.jsonl"

ATTR_LONG = "THD.PR.WebLongDescription"
ATTR_SHORT = "THD.PR.WebShortDescription"

# Fijo / oculto
MODEL_NAME = "gpt-4.1-mini"

st.set_page_config(
    page_title="GOAT AI INNOVATION LABS | Enrichment Platform",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=None,
)

# ==============================================================================
# 1) THEME (PALETA EMPRESA)
# ==============================================================================
# Paleta recibida:
#   Accent:   #FF183A
#   Navy:     #003E71
#   Teal:     #00959C
#   Mint:     #6ECDCF
#   Gray:     #E8E8E8
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

/* App background */
.stApp{
  background: var(--goat-bg);
  color: var(--goat-text);
}

/* Sidebar */
section[data-testid="stSidebar"]{
  background: linear-gradient(180deg, #FFFFFF 0%, var(--goat-gray) 140%);
  border-right: 1px solid var(--goat-border);
}
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3{
  color: var(--goat-navy);
}

/* Titles */
h1, h2, h3{
  letter-spacing: -0.02em;
}
h1{
  color: var(--goat-navy);
}

/* Buttons */
div.stButton > button{
  width: 100%;
  background: var(--goat-navy);
  color: #FFFFFF;
  border: 1px solid rgba(0,0,0,0);
  border-radius: 12px;
  padding: 0.65rem 0.9rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  box-shadow: 0 6px 18px rgba(0, 62, 113, 0.18);
  transition: all 140ms ease;
}
div.stButton > button:hover{
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(0, 62, 113, 0.22);
  background: #00355F;
}
div.stButton > button:active{
  transform: translateY(0px);
}

/* Number inputs labels */
label, .stNumberInput label{
  color: var(--goat-navy) !important;
  font-weight: 700 !important;
}

/* Progress bar */
div[data-testid="stProgress"] > div{
  background: rgba(0, 149, 156, 0.18);
  border-radius: 999px;
}
div[data-testid="stProgress"] > div > div{
  background: linear-gradient(90deg, var(--goat-teal), var(--goat-mint));
  border-radius: 999px;
}

/* Info/Success boxes tweaks (streamlit native) */
div[data-testid="stAlert"]{
  border-radius: 14px;
}

/* Custom UI blocks */
.small-muted{
  color: var(--goat-muted);
  font-size: 0.92rem;
  line-height: 1.3rem;
}

/* Metrics */
.metric-container{
  border: 1px solid var(--goat-border);
  border-radius: 18px;
  padding: 16px 18px;
  background: linear-gradient(180deg, rgba(110,205,207,0.16) 0%, rgba(232,232,232,0.26) 120%);
  box-shadow: 0 8px 20px rgba(2, 6, 23, 0.06);
}
.metric-label{
  font-size: 0.9rem;
  color: var(--goat-navy);
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.metric-value{
  font-size: 2.1rem;
  font-weight: 900;
  color: var(--goat-accent);
  margin-top: 4px;
}
.metric-sub{
  margin-top: 4px;
  color: var(--goat-muted);
  font-weight: 700;
}

/* Progress status pill */
.progress-box{
  border: 1px solid var(--goat-border);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(110,205,207,0.14);
  color: var(--goat-navy);
  font-weight: 800;
}

/* Product Card */
.goat-card{
  margin: 14px 0;
  border: 1px solid var(--goat-border);
  border-radius: 20px;
  background: #FFFFFF;
  box-shadow: var(--goat-shadow);
  overflow: hidden;
}
.header-flex{
  display:flex;
  gap: 18px;
  justify-content: space-between;
  align-items: stretch;
  padding: 16px 16px 10px 16px;
  border-bottom: 1px solid var(--goat-border);
  background: linear-gradient(90deg, rgba(0,62,113,0.05) 0%, rgba(0,149,156,0.05) 60%, rgba(110,205,207,0.05) 100%);
}
.header-left{
  display:flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.header-right{
  min-width: 340px;
  max-width: 52%;
}
.pid-badge{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(255, 24, 58, 0.12);
  color: var(--goat-accent);
  border: 1px solid rgba(255, 24, 58, 0.25);
  font-weight: 900;
}
.product-label{
  color: var(--goat-navy);
  font-weight: 900;
  letter-spacing: 0.02em;
}
.time-pill{
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(0,62,113,0.10);
  color: var(--goat-navy);
  border: 1px solid rgba(0,62,113,0.18);
  font-weight: 900;
}

.meta-row{
  display:flex;
  gap: 10px;
  align-items: baseline;
  margin: 2px 0;
}
.meta-key{
  min-width: 110px;
  color: var(--goat-teal);
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-size: 0.78rem;
}
.meta-val{
  color: var(--goat-text);
  font-weight: 800;
  overflow-wrap: anywhere;
}

/* Description areas */
.desc-header{
  color: var(--goat-navy);
  font-weight: 900;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  font-size: 0.82rem;
  margin: 10px 0 8px 0;
}
.desc-box{
  border: 1px solid var(--goat-border);
  border-radius: 16px;
  padding: 14px 14px;
  background: linear-gradient(180deg, rgba(232,232,232,0.34) 0%, rgba(110,205,207,0.10) 120%);
  color: var(--goat-text);
  font-weight: 650;
  line-height: 1.35rem;
}

/* Reduce default top padding a bit */
.block-container{
  padding-top: 1.2rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# 2) HELPERS
# ==============================================================================
def load_logo(filename: str, width: int | None = None) -> None:
    p = LOGO_DIR / filename
    if p.exists():
        if width:
            st.image(str(p), width=width)
        else:
            st.image(str(p), use_container_width=True)


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def to_single_paragraph(text: str) -> str:
    text = re.sub(r"[\r\n]+", " ", (text or ""))
    return normalize_ws(text)


def clamp_chars(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    m = re.search(r"[.!?]\s+[^.!?]*$", cut)
    if m:
        cut = cut[: m.start()].rstrip()
    return cut.rstrip(" ,;:-") + "."


def pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        s = str(v[0]).strip()
        return s or None
    s = str(v).strip()
    return s or None


def load_category_context(path: Path) -> Dict[str, Dict[str, Any]]:
    mp: Dict[str, Dict[str, Any]] = {}
    for row in read_jsonl(path):
        k = row.get("category_key") or row.get("labels", {}).get("parent_id")
        if not k:
            continue
        mp[str(k)] = row
    return mp


def build_category_path_str(prod: Dict[str, Any]) -> str:
    labels = prod.get("labels", {}) or {}
    dep = labels.get("web_department") or ""
    cat = labels.get("web_category") or ""
    sub = labels.get("web_subcategory") or ""
    parts = [p for p in [dep, cat, sub] if p]
    return " > ".join(parts) if parts else "-"


def call_llm(prompt: str, model: str, max_output_tokens: int) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")
    client = OpenAI(api_key=api_key)

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "Responde con precisión. No inventes datos. Entrega solo el texto final solicitado."},
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=max_output_tokens,
        timeout=90,
    )

    out: List[str] = []
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    out.append(c.text)
    return normalize_ws(" ".join(out))


def build_prompt_short(prod: Dict[str, Any], max_chars: int, category_ctx: Optional[Dict[str, Any]]) -> str:
    labels = prod.get("labels", {}) or {}
    web_department = labels.get("web_department") or ""
    web_category = labels.get("web_category") or ""
    web_subcategory = labels.get("web_subcategory") or ""

    web_name = prod.get("web_name") or ""
    model = prod.get("model") or ""
    brand = prod.get("brand") or prod.get("marca") or ""

    attrs = prod.get("attributes", {}) or {}
    candidate_keys = [
        "THD.CT.MATERIAL",
        "THD.CT.COLOR",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.ALTO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
    ]
    picked: List[str] = []
    for k in candidate_keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append(str(v))
        if len(picked) >= 2:
            break
    attrs_str = ", ".join(picked) if picked else "N/A"

    keywords = (category_ctx.get("keywords") or []) if category_ctx else []
    kw_str = ", ".join(keywords[:12]) if keywords else "N/A"

    return f"""
Genera UNA descripción corta (short description) en español neutro para eCommerce.

REGLAS:
- 1 solo párrafo.
- 1 a 2 frases.
- Máximo {max_chars} caracteres (con espacios).
- No inventes especificaciones ni claims.
- No menciones precio, promos, envíos, disponibilidad, garantía.
- Evita repetir el nombre del producto (0 o 1 vez máximo).
- Debe incluir: tipo/categoría + (marca si existe) + 1–2 atributos disponibles.

CONTEXTO:
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- Keywords de categoría (referencia): {kw_str}

DATOS PRODUCTO:
- WebName: {web_name}
- Brand: {brand if brand else "N/A"}
- Modelo: {model if model else "N/A"}
- Atributos disponibles (elige 1–2): {attrs_str}

ENTREGA:
- Devuelve SOLO la short final (sin comillas).
""".strip()


def build_prompt_long(prod: Dict[str, Any], max_chars: int, category_ctx: Optional[Dict[str, Any]]) -> str:
    labels = prod.get("labels", {}) or {}
    web_department = labels.get("web_department") or ""
    web_category = labels.get("web_category") or ""
    web_subcategory = labels.get("web_subcategory") or ""

    web_name = prod.get("web_name") or ""
    model = prod.get("model") or ""
    brand = prod.get("brand") or prod.get("marca") or ""

    attrs = prod.get("attributes", {}) or {}
    candidate_keys = [
        "THD.CT.MATERIAL",
        "THD.CT.COLOR",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.ALTO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
        "THD.CT.ACABADOS",
        "THD.CT.MODELO",
    ]
    picked: List[str] = []
    for k in candidate_keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append(f"{k.split('.')[-1]}: {v}")
        if len(picked) >= 8:
            break
    attrs_str = " | ".join(picked) if picked else "N/A"

    recommended_focus = (category_ctx.get("recommended_focus") or []) if category_ctx else []
    keywords = (category_ctx.get("keywords") or []) if category_ctx else []
    focus_str = ", ".join(recommended_focus) if recommended_focus else "N/A"
    kw_str = ", ".join(keywords[:15]) if keywords else "N/A"

    return f"""
Genera UNA descripción larga (web long description) en español neutro para eCommerce.

REGLAS:
- 1 solo párrafo (sin viñetas).
- Máximo {max_chars} caracteres (con espacios).
- Explica beneficios de uso SIN inventar datos técnicos.
- No menciones precio, promos, envíos, disponibilidad, garantía.
- No afirmes certificaciones o compatibilidades no presentes en atributos.
- Usa solo información disponible + contexto de categoría.

CONTEXTO DE CATEGORÍA:
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- Enfoque recomendado: {focus_str}
- Keywords (referencia): {kw_str}

DATOS PRODUCTO:
- WebName: {web_name}
- Brand: {brand if brand else "N/A"}
- Modelo: {model if model else "N/A"}
- Atributos disponibles (incorpora algunos de forma natural si aplica): {attrs_str}

ENTREGA:
- Devuelve SOLO la long final (sin comillas).
""".strip()


def build_delta_xml(rows: List[Dict[str, Any]], attr_id: str, text_field: str) -> str:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<STEP-ProductInformation>")
    parts.append("  <Products>")
    for r in rows:
        pid = r.get("product_id")
        val = r.get(text_field)
        if not pid or not val:
            continue
        parts.append(f'    <Product ID="{xml_escape(str(pid))}">')
        parts.append("      <Values>")
        parts.append(f'        <Value AttributeID="{xml_escape(attr_id)}">{xml_escape(str(val))}</Value>')
        parts.append("      </Values>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</STEP-ProductInformation>")
    return "\n".join(parts) + "\n"


def render_product_card(pid: str, payload: Dict[str, Any]) -> None:
    web_name = html_escape(payload.get("web_name") or "-")
    parent_id = html_escape(payload.get("parent_id") or "-")
    cat_path = html_escape(payload.get("category_path_str") or "-")

    long_txt = payload.get("long") or ""
    short_txt = payload.get("short") or ""

    t_long = payload.get("t_long")
    t_short = payload.get("t_short")

    long_show = html_escape(long_txt) if long_txt else "<span style='color:#9CA3AF;font-weight:800'>Waiting for generation...</span>"
    short_show = html_escape(short_txt) if short_txt else "<span style='color:#9CA3AF;font-weight:800'>Waiting for generation...</span>"

    time_line = ""
    if t_long is not None and t_short is not None:
        time_line = f"LONG {t_long:.3f}s • SHORT {t_short:.3f}s"

    st.markdown(
        f"""
<div class="goat-card">
  <div class="header-flex">
    <div class="header-left">
      <span class="pid-badge">{html_escape(pid)}</span>
      <div class="product-label">STEP Writeback Preview</div>
      <div class="time-pill">{html_escape(time_line)}</div>
    </div>
    <div class="header-right">
      <div class="meta-row"><span class="meta-key">WEBNAME</span><span class="meta-val">{web_name}</span></div>
      <div class="meta-row"><span class="meta-key">PARENTID</span><span class="meta-val">{parent_id}</span></div>
      <div class="meta-row"><span class="meta-key">CATEGORYPATH</span><span class="meta-val">{cat_path}</span></div>
    </div>
  </div>
""",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"<div><div class='desc-header'>CASE 1: LONG DESCRIPTION</div><div class='desc-box'>{long_show}</div></div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"<div><div class='desc-header'>CASE 2: SHORT DESCRIPTION</div><div class='desc-box'>{short_show}</div></div>",
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# 3) SESSION STATE
# ==============================================================================
if "results" not in st.session_state:
    st.session_state.results = {}  # pid -> meta + long/short + times
if "run_stats" not in st.session_state:
    st.session_state.run_stats = {"processed": 0, "total_s": 0.0, "avg_s": 0.0}
if "running" not in st.session_state:
    st.session_state.running = False


# ==============================================================================
# 4) SIDEBAR (SIN MODELO, SIN TEMPERATURE, SIN RUTAS)
# ==============================================================================
with st.sidebar:
    load_logo("goat.png", width=140)
    st.markdown("### GENERATION SETTINGS")

    limit = st.number_input("Limit", min_value=1, max_value=500, value=15, step=1)
    short_max = st.number_input("Short max chars", min_value=60, max_value=200, value=120, step=5)
    long_max = st.number_input("Long max chars", min_value=300, max_value=2000, value=1200, step=50)

    st.markdown("<br>", unsafe_allow_html=True)
    generate_clicked = st.button("GENERATE", use_container_width=True)

    st.markdown("<div class='small-muted'>Genera LONG + SHORT y escribe deltas en <b>outputs/</b></div>", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("RESET VIEW", use_container_width=True):
        st.session_state.results = {}
        st.session_state.run_stats = {"processed": 0, "total_s": 0.0, "avg_s": 0.0}
        st.session_state.running = False
        st.rerun()


# ==============================================================================
# 5) HEADER (LOGO STIBO ARREGLADO)
# ==============================================================================
c1, c2 = st.columns([4, 1])
with c1:
    st.title("GOAT AI INNOVATION LABS | Enrichment Platform")
    st.markdown("Automated Content Generation for **Home Depot STEP**")
with c2:
    st.write("")
    load_logo("stibo.png", width=180)

st.markdown("---")


# ==============================================================================
# 6) METRICS PLACEHOLDERS
# ==============================================================================
mcol1, mcol2 = st.columns(2)
metric_ph_1 = mcol1.empty()
metric_ph_2 = mcol2.empty()


def render_metrics(loaded: int, generated: int, total_s: float, avg_s: float) -> None:
    metric_ph_1.markdown(
        f"""
<div class="metric-container">
  <div class="metric-label">Generated</div>
  <div class="metric-value">{generated}</div>
  <div class="metric-sub">LONG + SHORT</div>
</div>
""",
        unsafe_allow_html=True,
    )
    metric_ph_2.markdown(
        f"""
<div class="metric-container">
  <div class="metric-label">Total Time</div>
  <div class="metric-value">{total_s:.2f}s</div>
  <div class="metric-sub">Avg {avg_s:.2f}s / product</div>
</div>
""",
        unsafe_allow_html=True,
    )


st.markdown("<br>", unsafe_allow_html=True)

progress_bar = st.progress(0)
status_ph = st.empty()
timing_ph = st.empty()
cards_container = st.container()


# ==============================================================================
# 7) LOAD INPUTS
# ==============================================================================
products = read_jsonl(INPUT_PRODUCTS_JSONL)
cat_ctx_map = load_category_context(CATEGORY_CONTEXT_JSONL)

valid_products = [p for p in products if p.get("product_id")]
loaded_n = min(int(limit), len(valid_products))


# ==============================================================================
# 8) INITIAL VIEW: VACÍO HASTA GENERATE
# ==============================================================================
if not st.session_state.results and not generate_clicked and not st.session_state.running:
    render_metrics(loaded=loaded_n, generated=0, total_s=0.0, avg_s=0.0)
    status_ph.info("System Ready. Click GENERATE to start.")
    st.stop()


# ==============================================================================
# 9) GENERATION
# ==============================================================================
def get_category_ctx_for_product(prod: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    parent_id = prod.get("parent_id") or (prod.get("labels", {}) or {}).get("parent_id")
    if not parent_id:
        return None
    return cat_ctx_map.get(str(parent_id))


def persist_outputs(long_rows: List[Dict[str, Any]], short_rows: List[Dict[str, Any]], ctx_rows: List[Dict[str, Any]]) -> None:
    write_jsonl(OUT_LONG_JSONL, long_rows)
    write_jsonl(OUT_SHORT_JSONL, short_rows)
    write_jsonl(OUT_CONTEXT_MAP_JSONL, ctx_rows)

    OUT_LONG_XML.write_text(build_delta_xml(long_rows, ATTR_LONG, "web_long_description"), encoding="utf-8")
    OUT_SHORT_XML.write_text(build_delta_xml(short_rows, ATTR_SHORT, "web_short_description"), encoding="utf-8")


if generate_clicked and not st.session_state.running:
    if not INPUT_PRODUCTS_JSONL.exists():
        st.error(f"No existe el input JSONL: {INPUT_PRODUCTS_JSONL}")
        st.stop()
    if OpenAI is None:
        st.error("Falta instalar openai: pip install openai")
        st.stop()
    if not os.getenv("OPENAI_API_KEY", "").strip():
        st.error("Falta OPENAI_API_KEY en tu .env / environment.")
        st.stop()

    st.session_state.running = True
    st.session_state.results = {}
    st.session_state.run_stats = {"processed": 0, "total_s": 0.0, "avg_s": 0.0}

    batch = valid_products[: int(limit)]
    total = len(batch)

    status_ph.markdown("<div class='progress-box'>Starting generation...</div>", unsafe_allow_html=True)
    progress_bar.progress(0)
    timing_ph.write("")

    out_long_rows: List[Dict[str, Any]] = []
    out_short_rows: List[Dict[str, Any]] = []
    out_ctx_rows: List[Dict[str, Any]] = []

    t0 = time.perf_counter()
    sum_product_s = 0.0

    for i, prod in enumerate(batch, start=1):
        pid = str(prod.get("product_id"))
        web_name = prod.get("web_name") or ""
        parent_id = prod.get("parent_id") or (prod.get("labels", {}) or {}).get("parent_id") or ""
        cat_path_str = prod.get("category_path_str") or build_category_path_str(prod)

        cc = get_category_ctx_for_product(prod)

        p_long = build_prompt_long(prod, int(long_max), cc)
        tL0 = time.perf_counter()
        long_text = call_llm(p_long, model=MODEL_NAME, max_output_tokens=650)
        long_text = clamp_chars(to_single_paragraph(long_text), int(long_max))
        t_long = time.perf_counter() - tL0

        p_short = build_prompt_short(prod, int(short_max), cc)
        tS0 = time.perf_counter()
        short_text = call_llm(p_short, model=MODEL_NAME, max_output_tokens=140)
        short_text = clamp_chars(to_single_paragraph(short_text), int(short_max))
        t_short = time.perf_counter() - tS0

        st.session_state.results[pid] = {
            "web_name": web_name,
            "parent_id": parent_id,
            "category_path_str": cat_path_str,
            "long": long_text,
            "short": short_text,
            "t_long": t_long,
            "t_short": t_short,
        }

        out_long_rows.append({
            "product_id": pid,
            "parent_id": parent_id,
            "web_name": web_name,
            "decision": "generate",
            "model": MODEL_NAME,
            "latency_s": round(t_long, 3),
            "web_long_description": long_text,
        })
        out_short_rows.append({
            "product_id": pid,
            "parent_id": parent_id,
            "web_name": web_name,
            "decision": "generate",
            "model": MODEL_NAME,
            "latency_s": round(t_short, 3),
            "web_short_description": short_text,
        })
        out_ctx_rows.append({
            "product_id": pid,
            "web_name": web_name,
            "parent_id": parent_id,
            "category_path_str": cat_path_str,
        })

        per_product = float(t_long + t_short)
        sum_product_s += per_product
        total_s = time.perf_counter() - t0
        avg_s = sum_product_s / i

        progress_bar.progress(i / total)
        status_ph.markdown(
            f"<div class='progress-box'>Generating {i}/{total} | <b>{html_escape(pid)}</b></div>",
            unsafe_allow_html=True,
        )
        timing_ph.write(f"[{i}/{total}] {pid} | long={t_long:.3f}s | short={t_short:.3f}s | total={per_product:.3f}s")

        render_metrics(loaded=loaded_n, generated=i, total_s=total_s, avg_s=avg_s)

        with cards_container:
            render_product_card(pid, st.session_state.results[pid])

        time.sleep(0.03)

    persist_outputs(out_long_rows, out_short_rows, out_ctx_rows)

    total_s = time.perf_counter() - t0
    avg_s = (sum_product_s / total) if total else 0.0
    st.session_state.run_stats = {"processed": total, "total_s": total_s, "avg_s": avg_s}
    st.session_state.running = False

    status_ph.success("Generation complete.")
    progress_bar.progress(1.0)

    with cards_container:
        for pid in sorted(st.session_state.results.keys()):
            render_product_card(pid, st.session_state.results[pid])

    render_metrics(loaded=loaded_n, generated=total, total_s=total_s, avg_s=avg_s)
    st.stop()


# ==============================================================================
# 10) SI YA HAY RESULTS (VIEW NORMAL)
# ==============================================================================
stats = st.session_state.run_stats or {"processed": 0, "total_s": 0.0, "avg_s": 0.0}
render_metrics(
    loaded=loaded_n,
    generated=int(stats.get("processed", 0)),
    total_s=float(stats.get("total_s", 0.0)),
    avg_s=float(stats.get("avg_s", 0.0)),
)

status_ph.success("Loaded results.")
progress_bar.progress(1.0)

with cards_container:
    for pid in sorted(st.session_state.results.keys()):
        render_product_card(pid, st.session_state.results[pid])
