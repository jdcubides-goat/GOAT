import os
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from dotenv import load_dotenv

from core.category_context import build_category_context
from core.product_enricher import generate_product_long_descriptions
from core.short_enricher import generate_product_short_descriptions
from core.product_naming import generate_product_names
from core.ui_theme import inject_theme
inject_theme()
# ==============================================================================
# ENV + PATHS
# ==============================================================================
load_dotenv()

DEMO_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DEMO = DEMO_DIR / "outputs_demo"

STAGING_PRODUCTS_JSONL = OUTPUTS_DEMO / "staging_products.jsonl"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

DEFAULT_LONG_ATTR = "THD.PR.WebLongDescription"
DEFAULT_SHORT_ATTR = "THD.PR.WebShortDescription"
DEFAULT_NAME_ATTR = "THD.PR.WebName"

st.set_page_config(page_title="GOAT | Use Cases", layout="wide")


# ==============================================================================
# Helpers (IO)
# ==============================================================================
def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _head_lines(text: str, n: int) -> str:
    lines = text.splitlines()
    return "\n".join(lines[: max(1, n)])


def _filter_xml_by_product_id(xml_text: str, product_id: str) -> str:
    if not product_id:
        return ""
    pattern = rf'(<Product\s+ID="{re.escape(product_id)}".*?</Product>)'
    m = re.search(pattern, xml_text, flags=re.S)
    return m.group(1) if m else ""


# ==============================================================================
# Helpers (terms)
# ==============================================================================
def _normalize_terms(lines: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in lines:
        t = (x or "").strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _textarea_to_terms(s: str) -> List[str]:
    lines = [(ln or "").strip() for ln in (s or "").splitlines()]
    return _normalize_terms(lines)


def _terms_to_textarea(terms: List[str]) -> str:
    return "\n".join(terms or [])


def _parse_terms_upload(upload) -> List[str]:
    if upload is None:
        return []
    raw = upload.read()
    try:
        text = raw.decode("utf-8", errors="ignore")
    except Exception:
        text = str(raw)

    name = (upload.name or "").lower()

    if name.endswith(".json"):
        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return _normalize_terms([str(x) for x in obj])
            if isinstance(obj, dict):
                for k in ["terms", "forbidden", "required", "items", "values"]:
                    if k in obj and isinstance(obj[k], list):
                        return _normalize_terms([str(x) for x in obj[k]])
        except Exception:
            pass
        return _normalize_terms(text.splitlines())

    if name.endswith(".xml"):
        candidates = re.findall(r"<(?:term|item|value)>(.*?)</(?:term|item|value)>", text, flags=re.I | re.S)
        cleaned: List[str] = []
        for c in candidates:
            c = re.sub(r"\s+", " ", c).strip()
            if c:
                cleaned.append(c)
        if cleaned:
            return _normalize_terms(cleaned)
        fallback = re.sub(r"<[^>]+>", "\n", text)
        return _normalize_terms(fallback.splitlines())

    return _normalize_terms(text.splitlines())


def _simulate_forbidden_terms() -> List[str]:
    return _normalize_terms([
        "gratis",
        "garantizado",
        "100% seguro",
        "mejor del mercado",
        "envío gratis",
        "oferta",
        "promoción",
        "sin competencia",
        "cura",
        "certificado oficial",
    ])


def _simulate_required_terms() -> List[str]:
    return _normalize_terms([
        "material",
        "color",
        "medidas",
        "uso",
    ])


# ==============================================================================
# Helpers (staging read)
# ==============================================================================
def _safe_get_bundle() -> Any:
    return st.session_state.get("staging")


def _get_products_from_staging(bundle: Any) -> List[Dict[str, Any]]:
    # 1) prefer persisted staging jsonl
    if STAGING_PRODUCTS_JSONL.exists():
        return _read_jsonl(STAGING_PRODUCTS_JSONL)

    # 2) fallback: try bundle paths
    for attr in ["products_path", "staging_products_path", "products_jsonl_path"]:
        if hasattr(bundle, attr):
            p = getattr(bundle, attr)
            try:
                p = Path(p)
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


def _guess_parent_id(prod: Dict[str, Any]) -> str:
    pid = (prod.get("parent_id") or "").strip()
    if pid:
        return pid
    labels = prod.get("labels") or {}
    return (labels.get("parent_id") or "").strip()


def _product_id(prod: Dict[str, Any]) -> str:
    return str(prod.get("product_id") or prod.get("id") or "").strip()


def _web_name(prod: Dict[str, Any]) -> str:
    return str(prod.get("name") or prod.get("web_name") or prod.get("webname") or "").strip()


def _brand(prod: Dict[str, Any]) -> str:
    return str(prod.get("brand") or prod.get("marca") or "").strip()


def _model(prod: Dict[str, Any]) -> str:
    return str(prod.get("model") or prod.get("modelo") or "").strip()


def _category_path(prod: Dict[str, Any]) -> str:
    v = str(prod.get("category_path") or prod.get("category_path_str") or "").strip()
    if v:
        return v
    labels = prod.get("labels") or {}
    parts = [labels.get("web_department"), labels.get("web_category"), labels.get("web_subcategory")]
    parts = [p for p in parts if p]
    return " > ".join(parts) if parts else "-"


# ==============================================================================
# Load staging
# ==============================================================================
bundle = _safe_get_bundle()
if bundle is None:
    st.warning("No staging found. Ve a Home y ejecuta Parse & Preview primero.")
    st.stop()

products = _get_products_from_staging(bundle)
if not products:
    st.error(f"No encontré productos staging. Esperaba: {STAGING_PRODUCTS_JSONL}")
    st.stop()

category_context_map = _build_category_context_map(bundle)

inventory: List[Dict[str, Any]] = []
for p in products:
    pid = _product_id(p)
    if not pid:
        continue
    inventory.append({
        "product_id": pid,
        "parent_id": _guess_parent_id(p),
        "category_path": _category_path(p),
        "name": _web_name(p),
        "brand": _brand(p),
        "model": _model(p),
        "attributes_count": len((p.get("attributes") or {})),
    })
inventory = inventory[:5000]

all_ids = [row["product_id"] for row in inventory]
default_ids = [row["product_id"] for row in inventory[:25]]

api_key = os.getenv("OPENAI_API_KEY", "").strip()


# ==============================================================================
# UI
# ==============================================================================
st.title("GOAT Use Cases")
st.caption("Mismo staging para todos los casos. Salida siempre XML delta para STEP.")

st.subheader("Preview (Products)")
st.dataframe(inventory[:500], use_container_width=True, height=420)

if not api_key:
    st.warning("Falta OPENAI_API_KEY en tu .env o en tu environment.")


# ==============================================================================
# Compliance block (global)
# ==============================================================================
st.markdown("---")
st.subheader("Compliance global (opcional): Forbidden + Required terms")

if "forbidden_terms_text" not in st.session_state:
    st.session_state["forbidden_terms_text"] = ""
if "required_terms_text" not in st.session_state:
    st.session_state["required_terms_text"] = ""

bcol1, bcol2, bcol3, bcol4 = st.columns(4)
with bcol1:
    if st.button("Simulate forbidden", use_container_width=True):
        st.session_state["forbidden_terms_text"] = _terms_to_textarea(_simulate_forbidden_terms())
with bcol2:
    if st.button("Clear forbidden", use_container_width=True):
        st.session_state["forbidden_terms_text"] = ""
with bcol3:
    if st.button("Simulate required", use_container_width=True):
        st.session_state["required_terms_text"] = _terms_to_textarea(_simulate_required_terms())
with bcol4:
    if st.button("Clear required", use_container_width=True):
        st.session_state["required_terms_text"] = ""

left_terms, right_terms = st.columns(2)
with left_terms:
    forbidden_upload = st.file_uploader(
        "Upload forbidden terms (txt/json/xml/csv/tsv)",
        type=["txt", "json", "xml", "csv", "tsv"],
        accept_multiple_files=False,
        key="forbidden_upload",
    )
    if forbidden_upload is not None:
        st.session_state["forbidden_terms_text"] = _terms_to_textarea(_parse_terms_upload(forbidden_upload))

    st.text_area("Forbidden terms (one per line)", value=st.session_state["forbidden_terms_text"], height=160, key="forbidden_terms_area")

with right_terms:
    required_upload = st.file_uploader(
        "Upload required terms (txt/json/xml/csv/tsv)",
        type=["txt", "json", "xml", "csv", "tsv"],
        accept_multiple_files=False,
        key="required_upload",
    )
    if required_upload is not None:
        st.session_state["required_terms_text"] = _terms_to_textarea(_parse_terms_upload(required_upload))

    st.text_area("Required terms (one per line)", value=st.session_state["required_terms_text"], height=160, key="required_terms_area")

forbidden_terms = _textarea_to_terms(st.session_state.get("forbidden_terms_area", ""))
required_terms = _textarea_to_terms(st.session_state.get("required_terms_area", ""))

p1, p2 = st.columns(2)
with p1:
    st.markdown("Preview forbidden")
    st.code(_terms_to_textarea(forbidden_terms) if forbidden_terms else "—", language="text")
with p2:
    st.markdown("Preview required")
    st.code(_terms_to_textarea(required_terms) if required_terms else "—", language="text")


# ==============================================================================
# CASE 1: LONG
# ==============================================================================
st.markdown("---")
st.header("Product Long Description")

c1_left, c1_right = st.columns([2, 1])
with c1_left:
    selected_ids_long = st.multiselect(
        "Selecciona productos para generar LONG",
        options=all_ids,
        default=default_ids,
        key="sel_long",
    )
with c1_right:
    long_attr = st.text_input("AttributeID (LONG)", value=DEFAULT_LONG_ATTR)
    long_max_chars = st.number_input("Max chars (LONG)", min_value=300, max_value=2000, value=1200, step=50, key="long_max_chars")
    limit_safety = st.number_input("Limit (safety)", min_value=1, max_value=500, value=25, step=1, key="limit_safety")

    b1, b2 = st.columns(2)
    gen_long = b1.button("Generate LONG", use_container_width=True)
    reset_long = b2.button("Reset LONG", use_container_width=True)

if reset_long:
    for fname in [
        "product_long_descriptions.jsonl",
        "delta_product_long_descriptions.xml",
        "product_long_generation_report.json",
    ]:
        p = OUTPUTS_DEMO / fname
        if p.exists():
            p.unlink()
    st.session_state.pop("last_long_xml_path", None)
    st.session_state.pop("last_long_jsonl_path", None)
    st.session_state.pop("last_long_report_path", None)
    st.success("LONG reseteado.")
    st.rerun()

if gen_long:
    if not api_key:
        st.error("No puedo generar sin OPENAI_API_KEY.")
    elif not selected_ids_long:
        st.error("Selecciona al menos 1 producto.")
    else:
        selected_ids_long = selected_ids_long[: int(limit_safety)]
        selected_set = set(selected_ids_long)
        selected_products_long = [p for p in products if _product_id(p) in selected_set]

        with st.spinner("Generating LONG..."):
            jsonl_path, xml_path, rep_path = generate_product_long_descriptions(
                selected_products_long,
                category_context_map,
                OUTPUTS_DEMO,
                long_attr.strip(),
                int(long_max_chars),
                DEFAULT_MODEL,
                forbidden_terms,
                required_terms,
            )

        st.session_state["last_long_xml_path"] = str(xml_path)
        st.session_state["last_long_jsonl_path"] = str(jsonl_path)
        st.session_state["last_long_report_path"] = str(rep_path)
        st.success("LONG generado y XML delta listo.")


# ==============================================================================
# CASE 2: SHORT
# ==============================================================================
st.markdown("---")
st.header("Product Short Description")

c2_left, c2_right = st.columns([2, 1])
with c2_left:
    selected_ids_short = st.multiselect(
        "Selecciona productos para generar SHORT",
        options=all_ids,
        default=default_ids,
        key="sel_short",
    )
with c2_right:
    short_attr = st.text_input("AttributeID (SHORT)", value=DEFAULT_SHORT_ATTR)
    short_max_chars = st.number_input("Max chars (SHORT)", min_value=60, max_value=300, value=120, step=10, key="short_max_chars")

    b1, b2 = st.columns(2)
    gen_short = b1.button("Generate SHORT", use_container_width=True)
    reset_short = b2.button("Reset SHORT", use_container_width=True)

if reset_short:
    for fname in [
        "product_short_descriptions.jsonl",
        "delta_product_short_descriptions.xml",
        "product_short_generation_report.json",
    ]:
        p = OUTPUTS_DEMO / fname
        if p.exists():
            p.unlink()
    st.session_state.pop("last_short_xml_path", None)
    st.session_state.pop("last_short_jsonl_path", None)
    st.session_state.pop("last_short_report_path", None)
    st.success("SHORT reseteado.")
    st.rerun()

if gen_short:
    if not api_key:
        st.error("No puedo generar sin OPENAI_API_KEY.")
    elif not selected_ids_short:
        st.error("Selecciona al menos 1 producto.")
    else:
        selected_ids_short = selected_ids_short[: int(limit_safety)]
        selected_set = set(selected_ids_short)
        selected_products_short = [p for p in products if _product_id(p) in selected_set]

        with st.spinner("Generating SHORT..."):
            jsonl_path, xml_path, rep_path = generate_product_short_descriptions(
                selected_products_short,
                category_context_map,
                OUTPUTS_DEMO,
                short_attr.strip(),
                int(short_max_chars),
                DEFAULT_MODEL,
                forbidden_terms,
                required_terms,
            )

        st.session_state["last_short_xml_path"] = str(xml_path)
        st.session_state["last_short_jsonl_path"] = str(jsonl_path)
        st.session_state["last_short_report_path"] = str(rep_path)
        st.success("SHORT generado y XML delta listo.")


# ==============================================================================
# CASE 3: NAMING
# ==============================================================================
st.markdown("---")
st.header("Product Naming (eCommerce title)")

c3_left, c3_right = st.columns([2, 1])
with c3_left:
    selected_ids_name = st.multiselect(
        "Selecciona productos para generar NAMES",
        options=all_ids,
        default=default_ids,
        key="sel_name",
    )
with c3_right:
    name_attr = st.text_input("AttributeID (NAME)", value=DEFAULT_NAME_ATTR)
    name_max_chars = st.number_input("Max chars (NAME)", min_value=40, max_value=200, value=120, step=5, key="name_max_chars")
    casing = st.selectbox("Casing", options=["Proper", "Upper", "Lower"], index=0)

    b1, b2 = st.columns(2)
    gen_name = b1.button("Generate NAMES", use_container_width=True)
    reset_name = b2.button("Reset NAMES", use_container_width=True)

if reset_name:
    for fname in [
        "product_names.jsonl",
        "delta_product_names.xml",
        "product_naming_report.json",
    ]:
        p = OUTPUTS_DEMO / fname
        if p.exists():
            p.unlink()
    st.session_state.pop("last_name_xml_path", None)
    st.session_state.pop("last_name_jsonl_path", None)
    st.session_state.pop("last_name_report_path", None)
    st.success("NAMES reseteado.")
    st.rerun()

if gen_name:
    if not api_key:
        st.error("No puedo generar sin OPENAI_API_KEY.")
    elif not selected_ids_name:
        st.error("Selecciona al menos 1 producto.")
    else:
        selected_ids_name = selected_ids_name[: int(limit_safety)]
        selected_set = set(selected_ids_name)
        selected_products_name = [p for p in products if _product_id(p) in selected_set]

        with st.spinner("Generating NAMES..."):
            jsonl_path, xml_path, rep_path = generate_product_names(
                selected_products_name,
                category_context_map,
                OUTPUTS_DEMO,
                name_attr.strip(),
                int(name_max_chars),
                DEFAULT_MODEL,
                forbidden_terms,
                required_terms,
                language="es-ES",
                casing=casing,
            )

        st.session_state["last_name_xml_path"] = str(xml_path)
        st.session_state["last_name_jsonl_path"] = str(jsonl_path)
        st.session_state["last_name_report_path"] = str(rep_path)
        st.success("NAMES generado y XML delta listo.")


# ==============================================================================
# XML Viewers (NO st.stop() - to not kill the rest of the page)
# ==============================================================================
st.markdown("---")
st.subheader("XML Viewers (delta)")

viewer_tabs = st.tabs(["LONG XML", "SHORT XML", "NAMES XML"])

def _xml_viewer(tab, session_key: str, fallback_name: str, title: str):
    with tab:
        xml_path_str = st.session_state.get(session_key)
        if not xml_path_str:
            fallback = OUTPUTS_DEMO / fallback_name
            if fallback.exists():
                xml_path_str = str(fallback)

        if not xml_path_str:
            st.info(f"Aún no hay XML para {title}. Ejecuta su botón de generación.")
            return

        xml_path = Path(xml_path_str)
        xml_text = _read_text(xml_path)

        c_a, c_b, c_c = st.columns([1, 1, 2])
        with c_a:
            head_n = st.number_input(f"Head lines ({title})", min_value=20, max_value=400, value=120, step=20, key=f"head_{title}")
        with c_b:
            filter_pid = st.selectbox(f"Filter Product ID ({title})", options=[""] + all_ids[:500], key=f"pid_{title}")
        with c_c:
            st.download_button(
                f"Download {title} delta XML",
                data=xml_text,
                file_name=xml_path.name,
                mime="application/xml",
                use_container_width=True,
            )

        with st.expander("XML head"):
            st.code(_head_lines(xml_text, int(head_n)), language="xml")

        with st.expander("XML block by Product ID"):
            if filter_pid:
                block = _filter_xml_by_product_id(xml_text, filter_pid)
                if block:
                    st.code(block, language="xml")
                else:
                    st.info("No encontré bloque <Product> para ese ID.")
            else:
                st.info("Selecciona un Product ID para filtrar.")

_xml_viewer(viewer_tabs[0], "last_long_xml_path", "delta_product_long_descriptions.xml", "LONG",)
_xml_viewer(viewer_tabs[1], "last_short_xml_path", "delta_product_short_descriptions.xml", "SHORT",)
_xml_viewer(viewer_tabs[2], "last_name_xml_path", "delta_product_names.xml", "NAMES",)
