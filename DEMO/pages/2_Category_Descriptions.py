import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st

from core.category_context import build_category_context
from core.category_enricher import generate_category_descriptions
from core.models import StagingBundle
from core.ui_theme import inject_theme
inject_theme()
# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------
DEMO_DIR = Path(__file__).resolve().parents[1]          # .../DEMO
OUTPUTS_DEMO = DEMO_DIR / "outputs_demo"

CATEGORY_JSONL = OUTPUTS_DEMO / "category_descriptions.jsonl"
CATEGORY_XML = OUTPUTS_DEMO / "delta_category_descriptions.xml"
CATEGORY_REPORT = OUTPUTS_DEMO / "category_generation_report.json"

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="GOAT | Category Descriptions", layout="wide")
st.title("Category Descriptions")
st.markdown(
    "Browse categories from **PPH** + signals from **ProductSampleData**. "
    "Generate descriptions and export delta XML."
)

# -----------------------------------------------------------------------------
# Session state keys
# -----------------------------------------------------------------------------
SS_LAST_XML_TEXT = "cat_last_xml_text"
SS_LAST_EXECUTED_KEYS = "cat_last_executed_keys"
SS_LAST_XML_PATH = "cat_last_xml_path"
SS_LAST_JSONL_PATH = "cat_last_jsonl_path"
SS_LAST_REPORT_PATH = "cat_last_report_path"

def reset_category_run(clear_files: bool = True) -> None:
    # Clear session state for this page
    for k in [SS_LAST_XML_TEXT, SS_LAST_EXECUTED_KEYS, SS_LAST_XML_PATH, SS_LAST_JSONL_PATH, SS_LAST_REPORT_PATH]:
        if k in st.session_state:
            del st.session_state[k]

    # Optionally remove last outputs from disk so the viewer starts "from zero"
    if clear_files:
        for p in [CATEGORY_JSONL, CATEGORY_XML, CATEGORY_REPORT]:
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                # If the file is locked or permission issue, we still reset session.
                pass


# -----------------------------------------------------------------------------
# XML Viewer helpers (only for delta XML)
# -----------------------------------------------------------------------------
def _read_text_safe(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        try:
            return p.read_text(encoding="latin-1")
        except Exception:
            return ""

def xml_head(xml_text: str, n_lines: int = 120) -> str:
    lines = (xml_text or "").splitlines()
    if not lines:
        return ""
    return "\n".join(lines[:n_lines])

def extract_products_section(xml_text: str, max_products: int = 3) -> str:
    if not xml_text:
        return ""
    lines = xml_text.splitlines()

    s = None
    for i, line in enumerate(lines):
        if "<Products>" in line:
            s = i
            break
    if s is None:
        return ""

    product_count = 0
    e = None
    for j in range(s, len(lines)):
        if "<Product " in lines[j]:
            product_count += 1
        if product_count >= max_products and "</Product>" in lines[j]:
            e = j
            break

    if e is None:
        e = min(s + 200, len(lines) - 1)

    return "\n".join(lines[s : e + 1])

def list_product_ids_from_delta(xml_text: str) -> List[str]:
    ids = re.findall(r'<Product\s+ID="([^"]+)"', xml_text or "")
    seen = set()
    out: List[str] = []
    for x in ids:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

def extract_product_block(xml_text: str, product_id: str) -> str:
    if not xml_text or not product_id:
        return ""

    lines = xml_text.splitlines()
    start_pat = f'<Product ID="{product_id}"'
    start_idx = None

    for i, line in enumerate(lines):
        if start_pat in line:
            start_idx = i
            break

    if start_idx is None:
        return ""

    end_idx = None
    for j in range(start_idx, len(lines)):
        if "</Product>" in lines[j]:
            end_idx = j
            break

    if end_idx is None:
        return "\n".join(lines[start_idx:])

    return "\n".join(lines[start_idx : end_idx + 1])


# -----------------------------------------------------------------------------
# Require staging
# -----------------------------------------------------------------------------
bundle: Optional[StagingBundle] = st.session_state.get("staging")
if bundle is None:
    st.warning("No staging found in session. Go to the STEP Simulator (Home) page and run Parse & Preview first.")
    st.stop()

# -----------------------------------------------------------------------------
# Build context rows (fast)
# -----------------------------------------------------------------------------
rows = build_category_context(bundle)

st.subheader("Category Inventory")
c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
c1.metric("Categories (nodes)", len(rows))
c2.metric("Total products", bundle.report.products)
c3.metric("Unmatched products", bundle.report.products_unmatched_category)

with c4:
    if st.button("Reset / Clear run", use_container_width=True):
        reset_category_run(clear_files=True)
        st.rerun()

# Show table
preview_rows: List[Dict[str, str]] = []
for r in rows[:500]:
    preview_rows.append(
        {
            "category_key": r["category_key"],
            "category_path": r["category_path"] or r["category_name"],
            "products_count": r["products_count"],
            "pph_links": len(r["pph_attribute_links"]),
            "top_attrs": ", ".join((r["top_attribute_ids"] or [])[:8]),
            "keywords": ", ".join((r["keywords"] or [])[:8]),
        }
    )

st.dataframe(preview_rows, use_container_width=True, height=420)

# -----------------------------------------------------------------------------
# Generate section (same as your previous code)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("Generate")

left, right = st.columns([2, 1])

with left:
    default_keys = [r["category_key"] for r in rows[:25]]
    selected_keys = st.multiselect(
        "Select categories to generate (default: top 25 by product count)",
        options=[r["category_key"] for r in rows],
        default=default_keys,
    )

with right:
    attribute_id_for_delta = st.text_input(
        "Category Description AttributeID (configurable)",
        value="TBD.CATEGORY.WebDescription",
        help="When the client confirms the real STEP AttributeID, replace this value.",
    )
    max_chars = st.number_input("Max chars", min_value=200, max_value=1200, value=600, step=50)
    gen_clicked = st.button("Generate descriptions", use_container_width=True)

with st.expander("Compliance (optional)", expanded=False):
    forbidden_terms = st.text_area("Forbidden terms (one per line)", value="")
    required_terms = st.text_area("Required terms (one per line)", value="")

    forbidden_terms = [t.strip() for t in forbidden_terms.splitlines() if t.strip()]
    required_terms = [t.strip() for t in required_terms.splitlines() if t.strip()]

# -----------------------------------------------------------------------------
# Run generation (write outputs, store executed keys, load XML into session)
# -----------------------------------------------------------------------------
if gen_clicked:
    if not selected_keys:
        st.error("Select at least one category.")
        st.stop()

    # Start from zero for every run:
    # clean previous generated outputs + session state and write new ones
    reset_category_run(clear_files=True)

    selected_set = set(selected_keys)
    selected_rows = [r for r in rows if r["category_key"] in selected_set]

    with st.spinner("Generating category descriptions..."):
        jsonl_path, xml_path, rep_path = generate_category_descriptions(
            category_rows=selected_rows,
            outputs_dir=OUTPUTS_DEMO,
            attribute_id_for_delta=attribute_id_for_delta.strip(),
            max_chars=int(max_chars),
            forbidden_terms=forbidden_terms,
            required_terms=required_terms,
        )

    # Persist run metadata for viewer
    st.session_state[SS_LAST_EXECUTED_KEYS] = [r["category_key"] for r in selected_rows]
    st.session_state[SS_LAST_XML_PATH] = str(xml_path)
    st.session_state[SS_LAST_JSONL_PATH] = str(jsonl_path)
    st.session_state[SS_LAST_REPORT_PATH] = str(rep_path)

    xml_text = _read_text_safe(xml_path)
    st.session_state[SS_LAST_XML_TEXT] = xml_text

    st.success("Done. Delta XML generated and ready for preview.")

    # Downloads (keep minimal; XML only as requested)
    st.download_button(
        "Download delta_category_descriptions.xml",
        data=xml_text,
        file_name="delta_category_descriptions.xml",
        mime="application/xml",
        use_container_width=True,
    )

# -----------------------------------------------------------------------------
# XML Viewer (ONLY BELOW Generate, and ONLY for last run)
# -----------------------------------------------------------------------------
st.markdown("---")
st.subheader("XML Viewer")

executed_keys: List[str] = st.session_state.get(SS_LAST_EXECUTED_KEYS, []) or []
xml_text: str = st.session_state.get(SS_LAST_XML_TEXT, "") or ""

viewer_cols = st.columns([2, 1])
with viewer_cols[0]:
    st.caption(
        "Preview del **delta_category_descriptions.xml** generado en esta ejecución. "
        "El viewer se resetea cada vez que vuelves a generar."
    )

with viewer_cols[1]:
    refresh = st.button("Refresh XML", use_container_width=True)
    if refresh:
        # Reload from last known path, else default path
        p = Path(st.session_state.get(SS_LAST_XML_PATH, str(CATEGORY_XML)))
        xml_text = _read_text_safe(p)
        st.session_state[SS_LAST_XML_TEXT] = xml_text
        st.rerun()

if not executed_keys:
    st.info("No hay ejecución activa en sesión. Selecciona categorías y genera para ver el XML aquí.")
    st.stop()

if not xml_text.strip():
    st.warning("No se encontró XML en sesión. Genera nuevamente o presiona Refresh XML.")
    st.stop()

# Head controls
h1, h2 = st.columns([2, 1])
with h1:
    n_lines = st.number_input("XML head (líneas a mostrar)", min_value=40, max_value=500, value=120, step=10)
with h2:
    st.download_button(
        "Download XML (again)",
        data=xml_text,
        file_name="delta_category_descriptions.xml",
        mime="application/xml",
        use_container_width=True,
    )

with st.expander("1) XML completo (head)", expanded=True):
    st.code(xml_head(xml_text, int(n_lines)), language="xml")

with st.expander("2) Extra: snippet de la sección <Products> (sanity check)", expanded=False):
    st.code(extract_products_section(xml_text, max_products=3), language="xml")

with st.expander("3) XML filtrado por Category Key (bloque <Product ID=...>)", expanded=True):
    ids_in_xml = list_product_ids_from_delta(xml_text)

    # Restrict filter to executed keys only (this run)
    allowed = [k for k in executed_keys if k in set(ids_in_xml)]

    if not allowed:
        st.warning(
            "No se encontraron IDs en el XML que coincidan con las categorías ejecutadas. "
            "Si el AttributeID o el writer cambió, revisa el contenido del XML en el head."
        )
    else:
        search = st.text_input("Filtrar Category Keys (opcional)", value="")
        filtered = [i for i in allowed if search.strip().lower() in i.lower()] if search.strip() else allowed

        sel = st.selectbox("Selecciona Category Key", options=filtered, index=0)
        block = extract_product_block(xml_text, sel)

        if not block:
            st.warning("No se encontró el bloque <Product> para ese ID.")
        else:
            st.code(block, language="xml")
