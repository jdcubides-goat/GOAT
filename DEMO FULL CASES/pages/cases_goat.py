import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from html import escape as html_escape
from xml.sax.saxutils import escape as xml_escape

import streamlit as st
from dotenv import load_dotenv

# Eliminamos la importación del logo para evitar duplicados con tu app.py
# from ui_theme import load_logo
from core.step_extract import iter_products_from_step_xml

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ==============================================================================
# CSS
# ==============================================================================
def inject_cases_css():
    st.markdown(
        """
<style>
/* ──────────────────────────────────────────────────────────────────────
   Number input (st.number_input) — light input + hover ONLY on +/- buttons
   ────────────────────────────────────────────────────────────────────── */

/* Wrapper (BaseWeb) */
div[data-testid="stNumberInput"] div[data-baseweb="input"]{
  background-color: #F0F2F6 !important;
  border: 1px solid #BCCAD6 !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}

/* Actual input box */
div[data-testid="stNumberInput"] input{
  background-color: #F0F2F6 !important;
  color: #003E71 !important;
  border: 0 !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}

/* Ensure typed value is visible (some themes dim it) */
div[data-testid="stNumberInput"] input::placeholder{
  color: rgba(0,62,113,0.55) !important;
}

/* +/- buttons default */
div[data-testid="stNumberInput"] button{
  background-color: #F0F2F6 !important;
  color: #003E71 !important;
  border: 1px solid transparent !important;
  border-radius: 10px !important;
  box-shadow: none !important;
}

/* +/- icons */
div[data-testid="stNumberInput"] button svg{
  fill: #003E71 !important;
}

/* Hover gesture ONLY on +/- */
div[data-testid="stNumberInput"] button:hover{
  background-color: rgba(0,62,113,0.10) !important;  /* navy hover */
  border-color: rgba(0,62,113,0.35) !important;
}

/* Keep container hover subtle (optional, NOT the "gesture") */
div[data-testid="stNumberInput"] div[data-baseweb="input"]:hover{
  border-color: rgba(188,202,214,1) !important;
}

/* ──────────────────────────────────────────────────────────────────────
   Sidebar titles
   ────────────────────────────────────────────────────────────────────── */
.sidebar-title {
  color: #003E71;
  font-weight: 900;
  font-size: 1.05rem;
  margin: 10px 0 4px 0;
}
.sidebar-subtitle {
  color: #003E71;
  font-weight: 900;
  font-size: 0.92rem;
  margin: 8px 0 4px 0;
}

/* ──────────────────────────────────────────────────────────────────────
   Selectbox
   ────────────────────────────────────────────────────────────────────── */
div[data-testid="stSelectbox"] > div > div {
  background-color: #F0F2F6 !important;
  border: 1px solid #BCCAD6 !important;
  border-radius: 8px !important;
}
div[data-testid="stSelectbox"] * {
  color: #003E71 !important;
  background-color: transparent !important;
}
div[data-testid="stSelectbox"] svg {
  fill: #003E71 !important;
}
div[data-baseweb="popover"] ul,
div[data-baseweb="menu"] ul {
  background-color: #FFFFFF !important;
}
div[data-baseweb="popover"] li,
div[data-baseweb="menu"] li {
  color: #003E71 !important;
  background-color: #FFFFFF !important;
}
div[data-baseweb="popover"] li:hover,
div[data-baseweb="menu"] li:hover {
  background-color: rgba(0,149,156,0.10) !important;
}

/* ──────────────────────────────────────────────────────────────────────
   Text input (Tone override)
   ────────────────────────────────────────────────────────────────────── */
div[data-testid="stTextInput"] input {
  background-color: #F0F2F6 !important;
  color: #003E71 !important;
  border: 1px solid #BCCAD6 !important;
  border-radius: 8px !important;
}
div[data-testid="stTextInput"] input::placeholder {
  color: rgba(0,62,113,0.55) !important;
}

/* ──────────────────────────────────────────────────────────────────────
   File uploader
   ────────────────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] section {
  background-color: #F0F2F6 !important;
  border: 1.5px dashed #BCCAD6 !important;
  border-radius: 12px !important;
}
[data-testid="stFileUploader"] section * {
  color: #003E71 !important;
}
[data-testid="stFileUploader"] section svg {
  fill: #003E71 !important;
}

/* ──────────────────────────────────────────────────────────────────────
   Download button
   ────────────────────────────────────────────────────────────────────── */
div[data-testid="stDownloadButton"] button {
  background-color: transparent !important;
  color: #00959C !important;
  border: 1.5px solid #00959C !important;
  border-radius: 8px !important;
  font-weight: 800 !important;
  transition: all 0.2s ease-in-out;
}
div[data-testid="stDownloadButton"] button:hover {
  background-color: #00959C !important;
  color: #FFFFFF !important;
}

/* ──────────────────────────────────────────────────────────────────────
   Tabs
   ────────────────────────────────────────────────────────────────────── */
div[data-testid="stTabs"] button {
  background-color: transparent !important;
  color: #003E71 !important;
  font-weight: 700;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
  color: #00959C !important;
  border-bottom: 2px solid #00959C !important;
}
div[data-testid="stTabs"] div[role="tabpanel"] {
  background-color: transparent !important;
}

/* ──────────────────────────────────────────────────────────────────────
   Teal success
   ────────────────────────────────────────────────────────────────────── */
.goat-success {
  background-color: rgba(0,149,156,0.10);
  border: 1px solid rgba(0,149,156,0.30);
  border-radius: 8px;
  padding: 12px 16px;
  color: #00959C;
  font-weight: 800;
  font-size: 0.97rem;
  margin: 8px 0;
}

/* ──────────────────────────────────────────────────────────────────────
   Progress / utils  (force visible text)
   ────────────────────────────────────────────────────────────────────── */
.small-muted {
  color: rgba(0,62,113,0.75) !important;
  font-size: 0.92rem;
  line-height: 1.3rem;
}
.progress-box {
  border: 1px solid rgba(188,202,214,0.85);
  border-radius: 14px;
  padding: 12px 14px;
  background: rgba(110,205,207,0.14);
  color: #003E71;
  font-weight: 900;
}

/* ──────────────────────────────────────────────────────────────────────
   Product cards (your existing styles)
   ────────────────────────────────────────────────────────────────────── */
.goat-card { margin: 20px 0; border: 1px solid rgba(188,202,214,0.85); border-radius: 20px; background: #FFFFFF; overflow: hidden; }
.card-header { display: flex; gap: 18px; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid rgba(188,202,214,0.85); background: linear-gradient(90deg,rgba(0,62,113,0.06) 0%,rgba(0,149,156,0.06) 60%,rgba(110,205,207,0.06) 100%); flex-wrap: wrap; }
.card-body { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; padding: 18px 20px 24px 20px; background: #FFFFFF; }
@media (max-width: 800px) { .card-body { grid-template-columns: 1fr; } }
.card-column { display: flex; flex-direction: column; }
.card-header-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.card-header-right { display: flex; flex-direction: column; gap: 2px; min-width: 280px; }
.pid-badge { display: inline-flex; align-items: center; justify-content: center; padding: 6px 10px; border-radius: 999px; background: rgba(255,24,58,0.12); color: #FF183A; border: 1px solid rgba(255,24,58,0.25); font-weight: 950; font-size: 0.88rem; }
.product-label { color: #003E71; font-weight: 950; letter-spacing: 0.02em; }
.time-pill { padding: 5px 10px; border-radius: 999px; background: rgba(0,62,113,0.10); color: #003E71; border: 1px solid rgba(0,62,113,0.18); font-weight: 850; font-size: 0.82rem; }
.locale-pill { padding: 5px 10px; border-radius: 999px; background: rgba(0,149,156,0.12); color: #00959C; border: 1px solid rgba(0,149,156,0.28); font-weight: 900; font-size: 0.82rem; }
.meta-row { display: flex; gap: 8px; align-items: baseline; }
.meta-key { min-width: 110px; color: #00959C; font-weight: 950; letter-spacing: 0.06em; text-transform: uppercase; font-size: 0.76rem; }
.meta-val { color: rgba(15,23,42,0.92); font-weight: 850; overflow-wrap: anywhere; font-size: 0.88rem; }
.desc-header { color: #003E71; font-weight: 950; letter-spacing: 0.05em; text-transform: uppercase; font-size: 0.82rem; margin: 0 0 8px 0; }
.desc-box { border: 1px solid rgba(188,202,214,0.85); border-radius: 16px; padding: 14px; background: linear-gradient(180deg,rgba(232,232,232,0.30) 0%,rgba(110,205,207,0.10) 120%); color: rgba(15,23,42,0.92); font-weight: 650; line-height: 1.35rem; }
.name-box { border: 1px solid rgba(188,202,214,0.85); border-radius: 16px; padding: 14px; background: linear-gradient(180deg,rgba(232,232,232,0.24) 0%,rgba(110,205,207,0.06) 120%); }
.name-slab { border: 1px solid rgba(188,202,214,0.85); border-radius: 14px; padding: 10px 12px; background: rgba(255,255,255,0.75); }
.name-label { color: #00959C; font-weight: 950; letter-spacing: 0.06em; text-transform: uppercase; font-size: 0.76rem; }
.name-value { margin-top: 6px; font-weight: 900; color: rgba(15,23,42,0.92); overflow-wrap: anywhere; }
.divider { height: 1px; background: rgba(15,23,42,0.08); margin: 10px 0; }
.viewer-title { color: #003E71; font-weight: 950; font-size: 1.05rem; margin: 18px 0 10px 0; padding-bottom: 6px; border-bottom: 2px solid rgba(0,149,156,0.25); }

</style>
""",
        unsafe_allow_html=True,
    )


# ==============================================================================
# Helpers
# ==============================================================================
load_dotenv()

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

ATTR_LONG  = "THD.PR.WebLongDescription"
ATTR_SHORT = "THD.PR.WebShortDescription"
ATTR_NAME  = "THD.PR.WebName"

def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def to_single_paragraph(text: str) -> str:
    return normalize_ws(re.sub(r"[\r\n]+", " ", (text or "")))


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
    return str(v).strip() or None


def build_category_path_str(labels: Dict[str, str]) -> str:
    parts = [labels.get(k) or "" for k in ("web_department", "web_category", "web_subcategory")]
    parts = [p for p in parts if p]
    return " > ".join(parts) if parts else "-"


def call_llm(prompt: str, model: str, max_output_tokens: int) -> str:
    if OpenAI is None:
        raise RuntimeError("Missing openai package.")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    client = OpenAI(api_key=api_key)
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "Responde con precisión. No inventes datos. Entrega solo el texto final solicitado."},
            {"role": "user",   "content": prompt},
        ],
        max_output_tokens=max_output_tokens,
        timeout=120,
    )
    out: List[str] = []
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    out.append(c.text)
    return normalize_ws(" ".join(out))


# ── Prompts ────────────────────────────────────────────────────────────────────

def build_prompt_long(prod: Dict[str, Any], max_chars: int, cc: Optional[Dict[str, Any]]) -> str:
    labels = prod.get("labels", {}) or {}
    attrs  = prod.get("attributes", {}) or {}
    keys   = ["THD.CT.MATERIAL","THD.CT.COLOR","THD.CT.ANCHO","THD.CT.LARGO",
              "THD.CT.ALTO","THD.CT.PROFUNDIDAD","THD.CT.CAPACIDAD","THD.CT.POTENCIA",
              "THD.CT.ACABADOS","THD.CT.MODELO"]
    picked = []
    for k in keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append(f"{k.split('.')[-1]}: {v}")
        if len(picked) >= 8:
            break
    focus = ", ".join((cc or {}).get("recommended_focus") or []) or "N/A"
    kws   = ", ".join(((cc or {}).get("keywords") or [])[:15]) or "N/A"
    return f"""
Genera UNA descripción larga (web long description) en español neutro para eCommerce.
REGLAS: 1 solo párrafo (sin viñetas). Máximo {max_chars} caracteres. Explica beneficios SIN inventar datos.
No menciones precio, promos, envíos, disponibilidad, garantía.
CONTEXTO: Dept={labels.get('web_department','')}, Cat={labels.get('web_category','')}, Sub={labels.get('web_subcategory','')}, Enfoque={focus}, KW={kws}
DATOS: WebName={prod.get('web_name','')}, Brand={prod.get('brand','N/A')}, Modelo={prod.get('model','N/A')}, Atributos={' | '.join(picked) or 'N/A'}
ENTREGA: Devuelve SOLO la long final (sin comillas).
""".strip()


def build_prompt_short(prod: Dict[str, Any], max_chars: int, cc: Optional[Dict[str, Any]]) -> str:
    labels = prod.get("labels", {}) or {}
    attrs  = prod.get("attributes", {}) or {}
    keys   = ["THD.CT.MATERIAL","THD.CT.COLOR","THD.CT.ANCHO","THD.CT.LARGO",
              "THD.CT.ALTO","THD.CT.PROFUNDIDAD","THD.CT.CAPACIDAD","THD.CT.POTENCIA"]
    picked = []
    for k in keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append(str(v))
        if len(picked) >= 2:
            break
    kws = ", ".join(((cc or {}).get("keywords") or [])[:12]) or "N/A"
    return f"""
Genera UNA descripción corta (short description) en español neutro para eCommerce.
REGLAS: 1 párrafo, 1-2 frases. Máximo {max_chars} caracteres. No inventes specs. No precio/promos/envíos/garantía.
CONTEXTO: Dept={labels.get('web_department','')}, Cat={labels.get('web_category','')}, Sub={labels.get('web_subcategory','')}, KW={kws}
DATOS: WebName={prod.get('web_name','')}, Brand={prod.get('brand','N/A')}, Modelo={prod.get('model','N/A')}, Atributos={', '.join(picked) or 'N/A'}
ENTREGA: Devuelve SOLO la short final (sin comillas).
""".strip()


def build_prompt_name(prod: Dict[str, Any], max_chars: int, cc: Optional[Dict[str, Any]]) -> str:
    labels = prod.get("labels", {}) or {}
    attrs  = prod.get("attributes", {}) or {}
    keys   = ["THD.CT.COLOR","THD.CT.MATERIAL","THD.CT.CAPACIDAD","THD.CT.POTENCIA",
              "THD.CT.ANCHO","THD.CT.LARGO","THD.CT.ALTO","THD.CT.PROFUNDIDAD"]
    picked = []
    for k in keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append(str(v))
        if len(picked) >= 3:
            break
    kws = ", ".join(((cc or {}).get("keywords") or [])[:10]) or "N/A"
    return f"""
Mejora el nombre de producto para eCommerce.
REGLAS: SOLO 1 título. Máximo {max_chars} caracteres. No inventes specs. No precio/promos/garantía. Alta intención comercial.
CONTEXTO: Dept={labels.get('web_department','')}, Cat={labels.get('web_category','')}, Sub={labels.get('web_subcategory','')}, KW={kws}
DATOS: Nombre actual={prod.get('web_name','')}, Brand={prod.get('brand','N/A')}, Modelo={prod.get('model','N/A')}, Atributos={', '.join(picked) or 'N/A'}
ENTREGA: Devuelve SOLO el título final.
""".strip()


# ── IO ─────────────────────────────────────────────────────────────────────────

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_category_context(path: Path) -> Dict[str, Dict[str, Any]]:
    mp: Dict[str, Dict[str, Any]] = {}
    for row in read_jsonl(path):
        k = row.get("category_key") or row.get("parent_id")
        if k:
            mp[str(k)] = row
    return mp


def ensure_basic_category_context(products: List[Dict[str, Any]], out_path: Path) -> Dict[str, Dict[str, Any]]:
    ctx: Dict[str, Dict[str, Any]] = {}
    for p in products:
        pid = str(p.get("parent_id") or "")
        if not pid:
            continue
        labels   = p.get("labels", {}) or {}
        cat_path = build_category_path_str(labels)
        seed     = " ".join([p.get("web_name") or "", labels.get("web_category") or "", labels.get("web_subcategory") or ""]).strip()
        bucket   = ctx.setdefault(pid, {"category_key": pid, "breadcrumb": cat_path, "keywords": [], "recommended_focus": []})
        tokens   = [t.lower() for t in re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", seed) if len(t) >= 4]
        for t in tokens[:8]:
            if t not in bucket["keywords"]:
                bucket["keywords"].append(t)
    rows = list(ctx.values())
    write_jsonl(out_path, rows)
    return {str(r["category_key"]): r for r in rows}


def build_delta_xml(rows: List[Dict[str, Any]], attr_id: str, text_field: str) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<STEP-ProductInformation>", "  <Products>"]
    for r in rows:
        pid = r.get("product_id")
        val = r.get(text_field)
        if not pid or not val:
            continue
        parts += [
            f'    <Product ID="{xml_escape(str(pid))}">',
            "      <Values>",
            f'        <Value AttributeID="{xml_escape(attr_id)}">{xml_escape(str(val))}</Value>',
            "      </Values>",
            "    </Product>",
        ]
    parts += ["  </Products>", "</STEP-ProductInformation>"]
    return "\n".join(parts) + "\n"


def build_combined_xml(results: Dict[str, Any], filter_pid: str = "All") -> str:
    pids = sorted(results.keys())
    if filter_pid != "All":
        pids = [p for p in pids if p == filter_pid]

    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<STEP-ProductInformation>", "  <Products>"]
    for pid in pids:
        p      = results[pid]
        long_  = (p.get("long")  or "").strip()
        short_ = (p.get("short") or "").strip()
        name_  = (p.get("name")  or "").strip()
        if not long_ and not short_ and not name_:
            continue
        parts.append(f'    <Product ID="{xml_escape(str(pid))}">')
        parts.append("      <Values>")
        if long_:
            parts.append(f'        <Value AttributeID="{xml_escape(ATTR_LONG)}">{xml_escape(long_)}</Value>')
        if short_:
            parts.append(f'        <Value AttributeID="{xml_escape(ATTR_SHORT)}">{xml_escape(short_)}</Value>')
        if name_:
            parts.append(f'        <Value AttributeID="{xml_escape(ATTR_NAME)}">{xml_escape(name_)}</Value>')
        parts.append("      </Values>")
        parts.append("    </Product>")
    parts += ["  </Products>", "</STEP-ProductInformation>"]
    return "\n".join(parts) + "\n"


def validate_xml_xsd(xml_text: str) -> Tuple[bool, str]:
    required = ["STEP-ProductInformation", "Products", "Product", "Values", "Value", "AttributeID"]
    missing  = [t for t in required if t not in xml_text]
    if missing:
        return False, f"Structural check failed — missing elements: {', '.join(missing)}"
    return True, "Valid XML — STEP structural check passed."


# ==============================================================================
# Locales
# ==============================================================================
LOCALES: Dict[str, Dict[str, str]] = {
    "": {"label": "None (original)", "language": "", "region": "", "notes": ""},
    "en-US": {"label": "en-US  —  English, United States", "language": "English", "region": "United States", "notes": "Retail tone for US eCommerce; clear, factual."},
    "en-GB": {"label": "en-GB  —  English, United Kingdom", "language": "English", "region": "United Kingdom", "notes": "UK spelling and phrasing; measured tone."},
    "es-MX": {"label": "es-MX  —  Español, México", "language": "Español", "region": "México", "notes": "Español mexicano neutral; natural retail phrasing."},
    "es-CO": {"label": "es-CO  —  Español, Colombia", "language": "Español", "region": "Colombia", "notes": "Español colombiano neutral."},
    "es-AR": {"label": "es-AR  —  Español, Argentina", "language": "Español", "region": "Argentina", "notes": "Español rioplatense suave."},
    "fr-FR": {"label": "fr-FR  —  Français, France", "language": "French", "region": "France", "notes": "Professional French eCommerce tone."},
    "de-DE": {"label": "de-DE  —  Deutsch, Germany", "language": "German", "region": "Germany", "notes": "Direct, technical, and precise German."},
    "it-IT": {"label": "it-IT  —  Italiano, Italy", "language": "Italian", "region": "Italy", "notes": "Engaging and descriptive Italian."},
    "pt-BR": {"label": "pt-BR  —  Português, Brasil", "language": "Portuguese", "region": "Brazil", "notes": "Warm and persuasive Brazilian Portuguese."},
    "pt-PT": {"label": "pt-PT  —  Português, Portugal", "language": "Portuguese", "region": "Portugal", "notes": "Standard European Portuguese."},
    "nl-NL": {"label": "nl-NL  —  Nederlands, Netherlands", "language": "Dutch", "region": "Netherlands", "notes": "Clear and pragmatic Dutch."},
    "zh-CN": {"label": "zh-CN  —  中文 (Chinese, Simplified)", "language": "Chinese (Simplified)", "region": "China", "notes": "Professional Mandarin for eCommerce."},
    "ja-JP": {"label": "ja-JP  —  日本語 (Japanese)", "language": "Japanese", "region": "Japan", "notes": "Polite and detailed Japanese retail tone."},
    "ko-KR": {"label": "ko-KR  —  한국어 (Korean)", "language": "Korean", "region": "South Korea", "notes": "Modern and trendy Korean eCommerce style."},
    "ar-SA": {"label": "ar-SA  —  العربية (Arabic)", "language": "Arabic", "region": "Saudi Arabia", "notes": "Formal and persuasive Arabic."},
    "ru-RU": {"label": "ru-RU  —  Русский (Russian)", "language": "Russian", "region": "Russia", "notes": "Clear and direct Russian."},
    "hi-IN": {"label": "hi-IN  —  हिन्दी (Hindi)", "language": "Hindi", "region": "India", "notes": "Natural and engaging Hindi for retail."},
}


def build_translate_prompt(
    source_locale: str, target_locale: str, tone_override: str,
    web_category: str, web_subcategory: str,
    existing_name: str, proposed_name: str,
    short_txt: str, long_txt: str,
    name_max: int, short_max: int, long_max: int,
) -> str:
    tgt       = LOCALES.get(target_locale, {})
    tone_line = f"Tone override: {tone_override.strip()}" if tone_override.strip() else ""
    return f"""
You are a retail eCommerce content localizer.
TASK: Translate/localize the 3 fields into the target locale preserving meaning and accuracy.
STRICT RULES: Do NOT invent specs/sizes/certifications. No price/promos/shipping/warranty.
Keep eCommerce style. Each field within its character limit.
OUTPUT FORMAT: Return ONLY a raw, unformatted JSON object. Do NOT wrap it in markdown blockquotes (```json).

CONTEXT: Category={web_category}, Subcategory={web_subcategory}, Target={tgt.get('language','')} ({tgt.get('region','')}), Notes={tgt.get('notes','')}, {tone_line}
SOURCE locale: {source_locale or 'original'}
LIMITS: name_max={name_max}, short_max={short_max}, long_max={long_max}
INPUT: existing_name={existing_name}, proposed_name={proposed_name}, short={short_txt}, long={long_txt}
OUTPUT: Return ONLY JSON.
""".strip()


def translate_payload(
    payload: Dict[str, Any],
    target_locale: str, tone_override: str,
    name_max: int, short_max: int, long_max: int,
) -> Tuple[str, str, str]:
    labels = payload.get("labels", {}) or {}
    prompt = build_translate_prompt(
        source_locale   = payload.get("_current_locale", "") or "",
        target_locale   = target_locale,
        tone_override   = tone_override,
        web_category    = labels.get("web_category", ""),
        web_subcategory = labels.get("web_subcategory", ""),
        existing_name   = payload.get("web_name", ""),
        proposed_name   = payload.get("name", ""),
        short_txt       = payload.get("short", ""),
        long_txt        = payload.get("long", ""),
        name_max=name_max, short_max=short_max, long_max=long_max,
    )
    raw = call_llm(prompt, MODEL_NAME, 900)
    
    try:
        clean_raw = raw.strip()
        match = re.search(r'\{.*\}', clean_raw, re.DOTALL)
        if match:
            clean_raw = match.group(0)
            
        data = json.loads(clean_raw)
        return (
            clamp_chars(to_single_paragraph(str(data.get("name",  payload.get("name", "")))), name_max),
            clamp_chars(to_single_paragraph(str(data.get("short", payload.get("short", "")))), short_max),
            clamp_chars(to_single_paragraph(str(data.get("long",  payload.get("long", "")))), long_max),
        )
    except Exception as e:
        print(f"Translation Parse Error: {e}\nRaw LLM Output:\n{raw}")
        return payload.get("name", ""), payload.get("short", ""), payload.get("long", "")


# ==============================================================================
# Card renderer
# ==============================================================================
def render_product_card(pid: str, payload: Dict[str, Any]) -> None:
    web_name_raw  = payload.get("web_name")          or ""
    parent_id_raw = payload.get("parent_id")         or ""
    cat_path_raw  = payload.get("category_path_str") or ""
    active_locale = payload.get("_current_locale")   or ""

    long_txt      = payload.get("long")  or ""
    short_txt     = payload.get("short") or ""
    proposed_name = payload.get("name")  or ""

    t_long  = payload.get("t_long")
    t_short = payload.get("t_short")
    t_name  = payload.get("t_name")

    time_parts = []
    if t_long  is not None: time_parts.append(f"LONG {t_long:.3f}s")
    if t_short is not None: time_parts.append(f"SHORT {t_short:.3f}s")
    if t_name  is not None: time_parts.append(f"NAME {t_name:.3f}s")
    time_line = " | ".join(time_parts)

    _miss = "<span style='color:#9CA3AF;font-weight:900'>Missing</span>"
    _wait = "<span style='color:#9CA3AF;font-weight:900'>Waiting for generation...</span>"

    long_show     = html_escape(long_txt)      if long_txt      else _wait
    short_show    = html_escape(short_txt)     if short_txt     else _wait
    name_show     = html_escape(proposed_name) if proposed_name else _wait
    existing_show = html_escape(web_name_raw)  if web_name_raw  else _miss
    web_name_disp = html_escape(web_name_raw)  if web_name_raw  else _miss
    parent_disp   = html_escape(parent_id_raw) if parent_id_raw else _miss
    cat_disp      = html_escape(cat_path_raw)  if cat_path_raw  else _miss

    locale_badge_html = f"<span class='locale-pill'>{html_escape(active_locale)}</span>" if active_locale else ""
    time_badge_html   = f"<span class='time-pill'>{html_escape(time_line)}</span>" if time_line else ""

    html_card = (
        f"<div class='goat-card'>"
        f"<div class='card-header'>"
        f"<div class='card-header-left'><span class='pid-badge'>{html_escape(pid)}</span><span class='product-label'>STEP Writeback Preview</span>{locale_badge_html}{time_badge_html}</div>"
        f"<div class='card-header-right'><div class='meta-row'><span class='meta-key'>WEBNAME</span><span class='meta-val'>{web_name_disp}</span></div><div class='meta-row'><span class='meta-key'>PARENTID</span><span class='meta-val'>{parent_disp}</span></div><div class='meta-row'><span class='meta-key'>CATEGORYPATH</span><span class='meta-val'>{cat_disp}</span></div></div>"
        f"</div>"
        f"<div class='card-body'>"
        f"<div class='card-column'>"
        f"<div class='desc-header'>CASE 1 — LONG DESCRIPTION</div><div class='desc-box' style='flex-grow:1;'>{long_show}</div>"
        f"</div>"
        f"<div class='card-column'>"
        f"<div class='desc-header'>CASE 2 — SHORT DESCRIPTION</div><div class='desc-box' style='margin-bottom:18px;'>{short_show}</div>"
        f"<div class='desc-header'>CASE 3 — ECOMMERCE DESCRIPTION</div>"
        f"<div class='name-box'><div class='name-slab'><div class='name-label'>Existing name</div><div class='name-value'>{existing_show}</div></div><div class='divider'></div><div class='name-slab'><div class='name-label'>Proposed E-commerce Description</div><div class='name-value'>{name_show}</div></div></div>"
        f"</div>"
        f"</div>"
        f"</div>"
    )

    st.markdown(html_card, unsafe_allow_html=True)


# ==============================================================================
# XML Viewer
# ==============================================================================
def render_viewer_section(results: Dict[str, Any]) -> None:
    st.markdown("---")
    st.markdown("<div class='viewer-title'>STEP XML Output — Cases 1, 2 &amp; 3</div>", unsafe_allow_html=True)

    if not results:
        st.info("No results yet. Run GENERATE first.")
        return

    all_pids = sorted(results.keys())

    filter_pid = st.selectbox(
        "Filter by Product ID",
        options=["All"] + all_pids,
        key="cg_viewer_filt_v4",
    )

    xml_text = build_combined_xml(results, filter_pid)

    ok, msg = validate_xml_xsd(xml_text)
    if ok:
        st.markdown(f"<div class='goat-success'>{html_escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.error(msg)

    st.download_button(
        "Download STEP delta XML (all cases)",
        data=xml_text,
        file_name="delta_step_all_cases.xml",
        mime="application/xml",
        use_container_width=True,
        key="cg_dl_xml_v4",
    )

    st.code(xml_text, language="xml")


# ==============================================================================
# Page
# ==============================================================================
def render():
    inject_cases_css()

    BASE_DIR    = Path(__file__).resolve().parents[1]
    LOGO_DIR    = BASE_DIR / "logos"
    OUTPUTS_DIR = BASE_DIR / "outputs"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    OUT_LONG_JSONL  = OUTPUTS_DIR / "product_long_desc.jsonl"
    OUT_SHORT_JSONL = OUTPUTS_DIR / "product_short_desc.jsonl"
    OUT_NAME_JSONL  = OUTPUTS_DIR / "product_name.jsonl"
    OUT_LONG_XML    = OUTPUTS_DIR / "delta_web_long_desc.xml"
    OUT_SHORT_XML   = OUTPUTS_DIR / "delta_web_short_desc.xml"
    OUT_NAMES_XML   = OUTPUTS_DIR / "delta_web_names.xml"
    OUT_CTX_JSONL   = OUTPUTS_DIR / "product_context_map.jsonl"
    CAT_CTX_JSONL   = OUTPUTS_DIR / "category_context_dir.jsonl"

    st.title("Cases GOAT")
    st.markdown("Long + Short + Naming with optional localization (translate without regenerating).")

    st.markdown("---")

    if "product_xml_path" not in st.session_state or not st.session_state.product_xml_path:
        st.error("No Product XML loaded. Go to Dataset Overview and upload Product XML first.")
        st.stop()

    product_xml_path = Path(st.session_state.product_xml_path)

    for key, default in [
        ("results",          {}),
        ("results_original", {}),
        ("run_stats",        {"processed": 0, "total_s": 0.0, "avg_s": 0.0}),
        ("running",          False),
        ("active_locale",    ""),
        ("just_generated",   False),
        ("just_translated",  False),
        ("just_reverted",    False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # ── Sidebar ────────────────────────────────────────────────────────────────
    with st.sidebar:
        # Ya no hay código para cargar el logo de goat aquí.
        st.markdown("<p class='sidebar-title'>Generation Settings</p>", unsafe_allow_html=True)
        limit = st.number_input("Limit", min_value=1, max_value=500, value=5, step=1,
                                key="cg_limit_input_v4")

        st.markdown("<p class='sidebar-subtitle'>Case 1-2 Limits</p>", unsafe_allow_html=True)
        short_max = st.number_input("Short max chars", min_value=60,  max_value=200,  value=120,  step=5,
                                    key="cg_short_max_input_v4")
        long_max  = st.number_input("Long max chars",  min_value=300, max_value=2000, value=1200, step=50,
                                    key="cg_long_max_input_v4")

        st.markdown("<p class='sidebar-subtitle'>Case 3 Limits</p>", unsafe_allow_html=True)
        name_max = st.number_input("E-commerce max chars", min_value=35, max_value=140, value=85, step=5,
                                   key="cg_name_max_input_v4")

        st.markdown("<p class='sidebar-subtitle'>Localization</p>", unsafe_allow_html=True)

        locale_keys   = list(LOCALES.keys())
        locale_labels = [LOCALES[k]["label"] for k in locale_keys]
        current_idx   = locale_keys.index(st.session_state.active_locale) if st.session_state.active_locale in locale_keys else 0

        selected_label = st.selectbox(
            "Target locale",
            locale_labels,
            index=current_idx,
            key="cg_locale_select_v4",
        )
        target_locale = locale_keys[locale_labels.index(selected_label)]

        tone_override = st.text_input(
            "Tone override (optional)",
            value="",
            placeholder="e.g. Premium, minimalist, technical...",
            key="cg_tone_input_v4",
        )

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        cta1, cta2 = st.columns(2)
        with cta1:
            generate_clicked  = st.button("GENERATE",  use_container_width=True, key="cg_btn_gen_v4")
        with cta2:
            translate_clicked = st.button("TRANSLATE", use_container_width=True, key="cg_btn_tran_v4")

        st.markdown(
            "<div class='small-muted'>GENERATE creates Cases 1-3. TRANSLATE localizes without regenerating. "
            "Select <b>None (original)</b> + TRANSLATE to revert.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        if st.button("RESET VIEW", use_container_width=True, key="cg_btn_res_v4"):
            for k in ("results", "results_original"):
                st.session_state[k] = {}
            st.session_state.run_stats     = {"processed": 0, "total_s": 0.0, "avg_s": 0.0}
            st.session_state.running       = False
            st.session_state.active_locale = ""
            st.rerun()

    # ── Load products ──────────────────────────────────────────────────────────
    products_raw: List[Dict[str, Any]] = []
    for rec in iter_products_from_step_xml(product_xml_path, limit=int(limit)):
        labels = rec.labels or {}
        products_raw.append({
            "product_id":        rec.product_id,
            "parent_id":         rec.parent_id,
            "web_name":          rec.web_name,
            "labels":            labels,
            "category_path_str": build_category_path_str(labels),
            "attributes":        rec.attributes or {},
        })

    valid_products = [p for p in products_raw if p.get("product_id")]
    loaded_n       = len(valid_products)

    if CAT_CTX_JSONL.exists():
        cat_ctx_map = load_category_context(CAT_CTX_JSONL)
    else:
        cat_ctx_map = ensure_basic_category_context(valid_products, CAT_CTX_JSONL)

    def get_cc(prod: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pid = prod.get("parent_id") or ""
        return cat_ctx_map.get(str(pid)) if pid else None

    # ── Metrics ────────────────────────────────────────────────────────────────
    mcol1, mcol2 = st.columns(2)
    metric_ph_1  = mcol1.empty()
    metric_ph_2  = mcol2.empty()

    def render_metrics(generated: int, total_s: float, avg_s: float) -> None:
        metric_ph_1.markdown(
            f'<div class="metric-container"><div class="metric-label">Generated</div>'
            f'<div class="metric-value">{generated}</div><div class="metric-sub">CASE 1-3</div></div>',
            unsafe_allow_html=True,
        )
        metric_ph_2.markdown(
            f'<div class="metric-container"><div class="metric-label">Total Time</div>'
            f'<div class="metric-value">{total_s:.2f}s</div>'
            f'<div class="metric-sub">Avg {avg_s:.2f}s / product</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    progress_bar    = st.progress(0)
    status_ph       = st.empty()
    timing_ph       = st.empty()
    cards_container = st.container()

    if not st.session_state.results and not generate_clicked and not translate_clicked and not st.session_state.running:
        render_metrics(0, 0.0, 0.0)
        status_ph.info("System Ready. Click GENERATE to start.")
        render_viewer_section(st.session_state.results)
        st.stop()

    def persist_outputs(long_rows, short_rows, name_rows, ctx_rows):
        write_jsonl(OUT_LONG_JSONL,  long_rows)
        write_jsonl(OUT_SHORT_JSONL, short_rows)
        write_jsonl(OUT_NAME_JSONL,  name_rows)
        write_jsonl(OUT_CTX_JSONL,   ctx_rows)
        OUT_LONG_XML.write_text( build_delta_xml(long_rows,  ATTR_LONG,  "web_long_description"),  encoding="utf-8")
        OUT_SHORT_XML.write_text(build_delta_xml(short_rows, ATTR_SHORT, "web_short_description"), encoding="utf-8")
        OUT_NAMES_XML.write_text(build_delta_xml(name_rows,  ATTR_NAME,  "proposed_name"),         encoding="utf-8")

    # ── TRANSLATE ──────────────────────────────────────────────────────────────
    if translate_clicked and not st.session_state.running:
        if not st.session_state.results_original:
            st.error("Nothing to translate yet. Run GENERATE first.")
            st.stop()

        if target_locale == "":
            st.session_state.results = json.loads(json.dumps(st.session_state.results_original))
            for pid in st.session_state.results:
                st.session_state.results[pid]["_current_locale"] = ""
            st.session_state.active_locale = ""
            st.session_state.just_reverted = True
            st.rerun()

        if OpenAI is None:
            st.error("Missing openai package. Install: pip install openai")
            st.stop()
        if not os.getenv("OPENAI_API_KEY", "").strip():
            st.error("Missing OPENAI_API_KEY in your environment (.env).")
            st.stop()

        st.session_state.active_locale = target_locale
        status_ph.markdown("<div class='progress-box'>Translating generated fields...</div>", unsafe_allow_html=True)
        progress_bar.progress(0)
        timing_ph.write("")

        pids        = sorted(st.session_state.results_original.keys())
        total       = len(pids)
        new_results = json.loads(json.dumps(st.session_state.results_original))

        t0 = time.perf_counter()
        for i, pid in enumerate(pids, start=1):
            payload = new_results[pid]
            payload["_current_locale"] = target_locale
            tT0 = time.perf_counter()
            name_out, short_out, long_out = translate_payload(
                payload, target_locale, tone_override,
                int(name_max), int(short_max), int(long_max),
            )
            t_tr = time.perf_counter() - tT0
            payload["name"]        = name_out
            payload["short"]       = short_out
            payload["long"]        = long_out
            payload["t_translate"] = t_tr

            progress_bar.progress(i / total)
            status_ph.markdown(
                f"<div class='progress-box'>Translating {i}/{total} | <b>{html_escape(pid)}</b> to {html_escape(target_locale)}</div>",
                unsafe_allow_html=True,
            )
            timing_ph.write(f"[{i}/{total}] {pid} | translate={t_tr:.3f}s")
            
            with cards_container:
                render_product_card(pid, payload)

        st.session_state.results = new_results
        st.session_state.just_translated = True
        st.rerun()

    # ── GENERATE ───────────────────────────────────────────────────────────────
    if generate_clicked and not st.session_state.running:
        if OpenAI is None:
            st.error("Missing openai package. Install: pip install openai")
            st.stop()
        if not os.getenv("OPENAI_API_KEY", "").strip():
            st.error("Missing OPENAI_API_KEY in your environment (.env).")
            st.stop()
        if loaded_n == 0:
            st.error("No products parsed from Product XML. Verify the export format.")
            st.stop()

        st.session_state.active_locale    = ""
        st.session_state.running          = True
        st.session_state.results          = {}
        st.session_state.results_original = {}
        st.session_state.run_stats        = {"processed": 0, "total_s": 0.0, "avg_s": 0.0}

        batch = valid_products[: int(limit)]
        total = len(batch)

        status_ph.markdown("<div class='progress-box'>Starting generation...</div>", unsafe_allow_html=True)
        progress_bar.progress(0)
        timing_ph.write("")

        out_long:  List[Dict[str, Any]] = []
        out_short: List[Dict[str, Any]] = []
        out_name:  List[Dict[str, Any]] = []
        out_ctx:   List[Dict[str, Any]] = []

        t0            = time.perf_counter()
        sum_product_s = 0.0

        for i, prod in enumerate(batch, start=1):
            pid          = str(prod.get("product_id"))
            web_name     = prod.get("web_name")          or ""
            parent_id    = prod.get("parent_id")         or ""
            cat_path_str = prod.get("category_path_str") or "-"
            cc           = get_cc(prod)

            tL0 = time.perf_counter()
            long_text = clamp_chars(to_single_paragraph(call_llm(build_prompt_long(prod, int(long_max), cc), MODEL_NAME, 650)), int(long_max))
            t_long = time.perf_counter() - tL0

            tS0 = time.perf_counter()
            short_text = clamp_chars(to_single_paragraph(call_llm(build_prompt_short(prod, int(short_max), cc), MODEL_NAME, 140)), int(short_max))
            t_short = time.perf_counter() - tS0

            tN0 = time.perf_counter()
            name_text = clamp_chars(to_single_paragraph(call_llm(build_prompt_name(prod, int(name_max), cc), MODEL_NAME, 120)), int(name_max))
            t_name = time.perf_counter() - tN0

            payload = {
                "product_id":        pid,
                "web_name":          web_name,
                "parent_id":         parent_id,
                "category_path_str": cat_path_str,
                "labels":            prod.get("labels",     {}) or {},
                "attributes":        prod.get("attributes", {}) or {},
                "long":              long_text,
                "short":             short_text,
                "name":              name_text,
                "t_long":            t_long,
                "t_short":           t_short,
                "t_name":            t_name,
                "_current_locale":   "",
            }

            st.session_state.results[pid]          = payload
            st.session_state.results_original[pid] = json.loads(json.dumps(payload))

            out_long.append({  "product_id": pid, "parent_id": parent_id, "web_name": web_name,
                               "decision": "generate", "model": MODEL_NAME,
                               "latency_s": round(t_long,  3), "web_long_description":  long_text })
            out_short.append({ "product_id": pid, "parent_id": parent_id, "web_name": web_name,
                               "decision": "generate", "model": MODEL_NAME,
                               "latency_s": round(t_short, 3), "web_short_description": short_text })
            out_name.append({  "product_id": pid, "parent_id": parent_id, "web_name": web_name,
                               "decision": "generate", "model": MODEL_NAME,
                               "latency_s": round(t_name,  3), "proposed_name":         name_text })
            out_ctx.append({   "product_id": pid, "web_name": web_name,
                               "parent_id": parent_id, "category_path_str": cat_path_str })

            per_product    = float(t_long + t_short + t_name)
            sum_product_s += per_product
            total_s        = time.perf_counter() - t0
            avg_s          = sum_product_s / i

            progress_bar.progress(i / total)
            status_ph.markdown(
                f"<div class='progress-box'>Generating {i}/{total} | <b>{html_escape(pid)}</b></div>",
                unsafe_allow_html=True,
            )
            timing_ph.write(
                f"[{i}/{total}] {pid} | long={t_long:.3f}s | short={t_short:.3f}s | name={t_name:.3f}s | total={per_product:.3f}s"
            )
            render_metrics(i, total_s, avg_s)

            with cards_container:
                render_product_card(pid, st.session_state.results[pid])

            time.sleep(0.01)

        persist_outputs(out_long, out_short, out_name, out_ctx)

        total_s = time.perf_counter() - t0
        avg_s   = (sum_product_s / total) if total else 0.0
        st.session_state.run_stats = {"processed": total, "total_s": total_s, "avg_s": avg_s}
        st.session_state.running   = False
        st.session_state.just_generated = True
        
        st.rerun()

    # ==============================================================================
    # ── NORMAL VIEW ──
    # ==============================================================================
    stats = st.session_state.run_stats or {"processed": 0, "total_s": 0.0, "avg_s": 0.0}
    render_metrics(
        int(stats.get("processed", 0)),
        float(stats.get("total_s", 0.0)),
        float(stats.get("avg_s", 0.0)),
    )
    
    if st.session_state.get("just_generated"):
        status_ph.markdown("<div class='goat-success'>Generation complete.</div>", unsafe_allow_html=True)
        st.session_state.just_generated = False
    elif st.session_state.get("just_translated"):
        loc_label = st.session_state.active_locale
        status_ph.markdown(f"<div class='goat-success'>Translation complete — {html_escape(loc_label)}.</div>", unsafe_allow_html=True)
        st.session_state.just_translated = False
    elif st.session_state.get("just_reverted"):
        status_ph.markdown("<div class='goat-success'>Reverted to original language.</div>", unsafe_allow_html=True)
        st.session_state.just_reverted = False
    else:
        status_ph.markdown("<div class='goat-success'>Loaded results.</div>", unsafe_allow_html=True)

    progress_bar.progress(1.0)

    with cards_container:
        for pid in sorted(st.session_state.results.keys()):
            render_product_card(pid, st.session_state.results[pid])

    render_viewer_section(st.session_state.results)


# Entrypoint protegido para no ejecutarse doble
if __name__ == "__main__":
    render()