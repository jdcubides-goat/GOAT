# pages/3_03_Use_Cases.py
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv
from html import escape as html_escape
from xml.sax.saxutils import escape as xml_escape

from core.category_context import build_category_context
from core.product_enricher import generate_product_long_descriptions
from core.short_enricher import generate_product_short_descriptions
from core.product_naming import generate_product_names
from core.ui_theme import inject_theme
inject_theme()
# ----------------------------
# ENV + PATHS
# ----------------------------
load_dotenv()
DEMO_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DEMO = DEMO_DIR / "outputs_demo"

STAGING_PRODUCTS_JSONL = OUTPUTS_DEMO / "staging_products.jsonl"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

ATTR_LONG = "THD.PR.WebLongDescription"
ATTR_SHORT = "THD.PR.WebShortDescription"
ATTR_NAME = "THD.PR.WebName"  # ajusta al AttributeID real en STEP


# ----------------------------
# Helpers
# ----------------------------
def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(__import__("json").loads(line))
    return out


def _safe_get_bundle() -> Any:
    return st.session_state.get("staging")


def _get_products_from_staging(bundle: Any) -> List[Dict[str, Any]]:
    if STAGING_PRODUCTS_JSONL.exists():
        return _read_jsonl(STAGING_PRODUCTS_JSONL)
    # fallback (si alguna vez guardas path dentro del bundle)
    for attr in ["products_path", "staging_products_path", "products_jsonl_path"]:
        if hasattr(bundle, attr):
            try:
                p = Path(getattr(bundle, attr))
                if p.exists():
                    return _read_jsonl(p)
            except Exception:
                pass
    return []


def _build_category_context_map(bundle: Any) -> Dict[str, Dict[str, Any]]:
    rows = build_category_context(bundle)
    mp: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = str(r.get("category_key") or "").strip()
        if k:
            mp[k] = r
    return mp


def _product_id(prod: Dict[str, Any]) -> str:
    return str(prod.get("product_id") or prod.get("id") or "").strip()


def _guess_parent_id(prod: Dict[str, Any]) -> str:
    pid = (prod.get("parent_id") or "").strip()
    if pid:
        return pid
    labels = prod.get("labels") or {}
    return str(labels.get("parent_id") or "").strip()


def _web_name(prod: Dict[str, Any]) -> str:
    return str(prod.get("name") or prod.get("web_name") or prod.get("webname") or "").strip()


def _category_path(prod: Dict[str, Any]) -> str:
    v = str(prod.get("category_path") or prod.get("category_path_str") or "").strip()
    if v:
        return v
    labels = prod.get("labels") or {}
    parts = [labels.get("web_department"), labels.get("web_category"), labels.get("web_subcategory")]
    parts = [p for p in parts if p]
    return " > ".join(parts) if parts else "-"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _head_lines(text: str, n: int) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[: max(1, n)])


def _filter_xml_by_product_id(xml_text: str, product_id: str) -> str:
    import re
    if not product_id:
        return ""
    pattern = rf'(<Product\s+ID="{re.escape(product_id)}".*?</Product>)'
    m = re.search(pattern, xml_text, flags=re.S)
    return m.group(1) if m else ""


def _render_card(pid: str, prod: Dict[str, Any], result: Dict[str, Any]) -> None:
    web_name = html_escape(_web_name(prod) or "-")
    parent_id = html_escape(_guess_parent_id(prod) or "-")
    cat_path = html_escape(_category_path(prod) or "-")

    long_txt = html_escape(result.get("long") or "")
    short_txt = html_escape(result.get("short") or "")
    name_txt = html_escape(result.get("name") or "")

    t_long = result.get("t_long")
    t_short = result.get("t_short")
    t_name = result.get("t_name")

    time_line = []
    if t_long is not None:
        time_line.append(f"LONG {t_long:.3f}s")
    if t_short is not None:
        time_line.append(f"SHORT {t_short:.3f}s")
    if t_name is not None:
        time_line.append(f"NAME {t_name:.3f}s")

    st.markdown(
        f"""
<div class="goat-card">
  <div class="header-flex">
    <div class="header-left">
      <span class="pid-badge">{html_escape(pid)}</span>
      <div class="product-label">STEP Writeback Preview</div>
      <div class="time-pill">{html_escape(" • ".join(time_line))}</div>
    </div>
    <div class="header-right">
      <div class="meta-row"><span class="meta-key">WEBNAME</span><span class="meta-val">{web_name}</span></div>
      <div class="meta-row"><span class="meta-key">PARENTID</span><span class="meta-val">{parent_id}</span></div>
      <div class="meta-row"><span class="meta-key">CATEGORYPATH</span><span class="meta-val">{cat_path}</span></div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("<div class='desc-header'>LONG DESCRIPTION</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='desc-box'>{long_txt or '<span style=color:#9CA3AF;font-weight:800>Pending</span>'}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='desc-header'>SHORT DESCRIPTION</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='desc-box'>{short_txt or '<span style=color:#9CA3AF;font-weight:800>Pending</span>'}</div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div class='desc-header'>NAMING</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='desc-box'>{name_txt or '<span style=color:#9CA3AF;font-weight:800>Pending</span>'}</div>", unsafe_allow_html=True)


# ----------------------------
# Load staging
# ----------------------------
bundle = _safe_get_bundle()
if bundle is None:
    st.warning("No staging found. Ve a Home y ejecuta Parse & Preview primero.")
    st.stop()

products = _get_products_from_staging(bundle)
if not products:
    st.error(f"No encontré productos staging. Esperaba: {STAGING_PRODUCTS_JSONL}")
    st.stop()

category_context_map = _build_category_context_map(bundle)

inventory = []
for p in products:
    pid = _product_id(p)
    if not pid:
        continue
    inventory.append({
        "product_id": pid,
        "parent_id": _guess_parent_id(p),
        "category_path": _category_path(p),
        "name": _web_name(p),
        "attributes_count": len((p.get("attributes") or {})),
    })

all_ids = [r["product_id"] for r in inventory]
default_ids = all_ids[:25]


# ----------------------------
# UI (usa el mismo look & feel ya inyectado desde app.py)
# ----------------------------
st.markdown("## Enrichment Use Cases")
st.markdown("<div class='small-muted'>Generación consistente para STEP: LONG + SHORT + NAMING con delta XML.</div>", unsafe_allow_html=True)

api_key = os.getenv("OPENAI_API_KEY", "").strip()
if not api_key:
    st.warning("Falta OPENAI_API_KEY en tu .env o en tu environment.")

# Selección
left, right = st.columns([2, 1])
with left:
    selected_ids = st.multiselect("Selecciona productos", options=all_ids, default=default_ids)

with right:
    limit_safety = st.number_input("Limit (safety)", min_value=1, max_value=500, value=min(25, len(default_ids)), step=1)
    long_max = st.number_input("Max chars (long)", min_value=300, max_value=2000, value=1200, step=50)
    short_max = st.number_input("Max chars (short)", min_value=60, max_value=300, value=120, step=10)
    name_max = st.number_input("Max chars (name)", min_value=30, max_value=180, value=80, step=5)

    st.markdown("<br>", unsafe_allow_html=True)
    gen_clicked = st.button("GENERATE (LONG + SHORT + NAME)", use_container_width=True)
    reset_clicked = st.button("RESET RUN", use_container_width=True)

if "uc_results" not in st.session_state:
    st.session_state.uc_results = {}  # pid -> {long, short, name, timings...}

if reset_clicked:
    st.session_state.uc_results = {}
    # limpia outputs típicos
    for fname in [
        "product_long_descriptions.jsonl",
        "delta_product_long_descriptions.xml",
        "product_long_generation_report.json",
        "product_short_descriptions.jsonl",
        "delta_product_short_descriptions.xml",
        "product_short_generation_report.json",
        "product_names.jsonl",
        "delta_product_names.xml",
        "product_naming_report.json",
    ]:
        p = OUTPUTS_DEMO / fname
        if p.exists():
            p.unlink()
    st.success("Run reseteado.")
    st.rerun()

# Generación
if gen_clicked:
    if not api_key:
        st.error("No puedo generar sin OPENAI_API_KEY.")
        st.stop()
    if not selected_ids:
        st.error("Selecciona al menos 1 producto.")
        st.stop()

    selected_ids = selected_ids[: int(limit_safety)]
    selected_set = set(selected_ids)

    selected_products = [p for p in products if _product_id(p) in selected_set]
    if not selected_products:
        st.error("No se encontraron productos seleccionados dentro del staging.")
        st.stop()

    prog = st.progress(0)
    status = st.empty()

    # 1) LONG
    status.markdown("<div class='progress-box'>Generating LONG...</div>", unsafe_allow_html=True)
    jsonl_long, xml_long, rep_long = generate_product_long_descriptions(
        selected_products,
        category_context_map,
        OUTPUTS_DEMO,
        ATTR_LONG,
        int(long_max),
        DEFAULT_MODEL,
        [],  # forbidden_terms (v2: luego por categoría)
        [],  # required_terms (v2: luego por categoría)
    )
    prog.progress(0.33)

    # 2) SHORT
    status.markdown("<div class='progress-box'>Generating SHORT...</div>", unsafe_allow_html=True)
    jsonl_short, xml_short, rep_short = generate_product_short_descriptions(
        selected_products,
        category_context_map,
        OUTPUTS_DEMO,
        ATTR_SHORT,
        int(short_max),
        DEFAULT_MODEL,
        [],
        [],
    )
    prog.progress(0.66)

    # 3) NAMING
    status.markdown("<div class='progress-box'>Generating NAMING...</div>", unsafe_allow_html=True)
    jsonl_name, xml_name, rep_name = generate_product_names(
        selected_products,
        category_context_map,
        OUTPUTS_DEMO,
        ATTR_NAME,
        int(name_max),
        DEFAULT_MODEL,
        [],
        [],
        language="es-ES",
        casing="Proper",
    )
    prog.progress(1.0)
    status.success("Done. LONG + SHORT + NAME + XML deltas listos.")

    # cargar outputs a memoria para render cards
    long_rows = _read_jsonl(Path(jsonl_long))
    short_rows = _read_jsonl(Path(jsonl_short))
    name_rows = _read_jsonl(Path(jsonl_name))

    long_by = {r["product_id"]: r.get("web_long_description") or r.get("web_long_desc") or r.get("web_long_description_generated") for r in long_rows}
    short_by = {r["product_id"]: r.get("web_short_description") or r.get("web_short_desc") or r.get("web_short_description_generated") for r in short_rows}
    name_by = {r["product_id"]: r.get("web_name_generated") or r.get("web_name") or r.get("name_generated") for r in name_rows}

    for p in selected_products:
        pid = _product_id(p)
        st.session_state.uc_results[pid] = {
            "long": long_by.get(pid, ""),
            "short": short_by.get(pid, ""),
            "name": name_by.get(pid, ""),
        }

    st.rerun()


# Render results
st.markdown("---")
st.markdown("### Preview — STEP Writeback Cards")

if not st.session_state.uc_results:
    st.info("No hay resultados aún. Ejecuta GENERATE.")
else:
    # cards
    for pid in selected_ids[: int(limit_safety)]:
        prod = next((p for p in products if _product_id(p) == pid), None)
        if not prod:
            continue
        _render_card(pid, prod, st.session_state.uc_results.get(pid, {}))

st.markdown("---")
st.markdown("### XML Deltas (Download + View)")

c1, c2, c3 = st.columns(3)
with c1:
    xml_long_path = OUTPUTS_DEMO / "delta_product_long_descriptions.xml"
    st.download_button("Download LONG delta XML", data=_read_text(xml_long_path), file_name=xml_long_path.name, mime="application/xml", use_container_width=True)
with c2:
    xml_short_path = OUTPUTS_DEMO / "delta_product_short_descriptions.xml"
    st.download_button("Download SHORT delta XML", data=_read_text(xml_short_path), file_name=xml_short_path.name, mime="application/xml", use_container_width=True)
with c3:
    xml_name_path = OUTPUTS_DEMO / "delta_product_names.xml"
    st.download_button("Download NAME delta XML", data=_read_text(xml_name_path), file_name=xml_name_path.name, mime="application/xml", use_container_width=True)

with st.expander("XML Viewer (head)"):
    head_n = st.number_input("XML head lines", min_value=20, max_value=400, value=120, step=20)
    st.code(_head_lines(_read_text(xml_long_path), int(head_n)), language="xml")

with st.expander("XML filtered by Product ID"):
    pid_filter = st.selectbox("Product ID", options=[""] + all_ids[:500])
    if pid_filter:
        txt = _read_text(xml_long_path)
        block = _filter_xml_by_product_id(txt, pid_filter)
        st.code(block or "No block found.", language="xml")