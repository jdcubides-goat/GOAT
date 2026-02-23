# pages/category_descriptions.py

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

from core.step_extract import iter_products_from_step_xml

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# ==============================================================================
# CSS
# ==============================================================================
def inject_category_css():
    st.markdown(
        """
<style>
/* ── Metrics ──────────────────────────────────────────────────────────── */
div[data-testid="stMetricValue"]{ color: rgba(15,23,42,0.95) !important; font-weight: 950 !important; }
div[data-testid="stMetricLabel"]{ color: rgba(0,62,113,0.80) !important; font-weight: 850 !important; }

/* ── Expander ─────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] details summary{
  background: #F0F2F6 !important; border: 1px solid #BCCAD6 !important;
  border-radius: 12px !important; padding: 10px 12px !important;
}
div[data-testid="stExpander"] details summary *{ color: #003E71 !important; font-weight: 900 !important; }
div[data-testid="stExpander"] details{ border: 0 !important; }

/* ── Text / Number inputs ─────────────────────────────────────────────── */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {
  background-color: #F0F2F6 !important; color: #003E71 !important;
  border: 1px solid #BCCAD6 !important; border-radius: 10px !important;
}
div[data-testid="stTextInput"] input::placeholder{ color: rgba(0,62,113,0.55) !important; }
div[data-testid="stNumberInput"] div[data-baseweb="input"]{
  background-color: #F0F2F6 !important; border: 1px solid #BCCAD6 !important; border-radius: 12px !important;
}

/* ── Selectbox ────────────────────────────────────────────────────────── */
div[data-testid="stSelectbox"] > div > div{
  background-color: #F0F2F6 !important; border: 1px solid #BCCAD6 !important; border-radius: 10px !important;
}
div[data-testid="stSelectbox"] *{ color:#003E71 !important; background-color: transparent !important; }
div[data-testid="stSelectbox"] svg{ fill:#003E71 !important; }
div[data-baseweb="popover"] ul, div[data-baseweb="menu"] ul{ background-color:#FFFFFF !important; }
div[data-baseweb="popover"] li, div[data-baseweb="menu"] li{ color:#003E71 !important; background-color:#FFFFFF !important; }
div[data-baseweb="popover"] li:hover, div[data-baseweb="menu"] li:hover{ background-color: rgba(0,149,156,0.10) !important; }

/* ── MultiSelect — kill every layer of dark background ───────────────── */
div[data-testid="stMultiSelect"],
div[data-testid="stMultiSelect"] > div,
div[data-testid="stMultiSelect"] > div > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"],
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div > div > div {
  background-color: #F0F2F6 !important;
  border-color: #BCCAD6 !important;
  border-radius: 12px !important;
}
/* All text inside multiselect → navy */
div[data-testid="stMultiSelect"] * {
  color: #003E71 !important;
}
/* Pills/tags: soft navy background */
div[data-testid="stMultiSelect"] span[data-baseweb="tag"],
div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
  background-color: rgba(0,62,113,0.10) !important;
  border: 1px solid rgba(0,62,113,0.22) !important;
  border-radius: 999px !important;
  color: #003E71 !important;
  font-weight: 850 !important;
}
div[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg,
div[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
  fill: #003E71 !important;
}
/* Dropdown list that opens */
div[data-testid="stMultiSelect"] ul,
div[data-testid="stMultiSelect"] [role="listbox"] {
  background-color: #FFFFFF !important;
}
div[data-testid="stMultiSelect"] li {
  color: #003E71 !important;
  background-color: #FFFFFF !important;
}
div[data-testid="stMultiSelect"] li:hover {
  background-color: rgba(0,149,156,0.10) !important;
}

/* ── Dataframe ────────────────────────────────────────────────────────── */
div[data-testid="stDataFrame"]{
  border: 1px solid rgba(188,202,214,0.95) !important;
  border-radius: 14px !important; overflow: hidden !important;
}

/* ── Download button ──────────────────────────────────────────────────── */
div[data-testid="stDownloadButton"] button{
  background-color: transparent !important; color: #00959C !important;
  border: 1.5px solid #00959C !important; border-radius: 10px !important; font-weight: 900 !important;
}
div[data-testid="stDownloadButton"] button:hover{
  background-color: #00959C !important; color: #FFFFFF !important;
}

/* ── Teal success ─────────────────────────────────────────────────────── */
.goat-success{
  background-color: rgba(0,149,156,0.10); border: 1px solid rgba(0,149,156,0.30);
  border-radius: 12px; padding: 10px 14px; color: #00959C; font-weight: 950; margin: 8px 0;
}
.small-muted{ color: rgba(0,62,113,0.75); font-size: 0.92rem; line-height: 1.35rem; }
.viewer-title{ color:#003E71; font-weight: 950; font-size: 1.05rem; margin: 10px 0 6px 0; }
</style>
""",
        unsafe_allow_html=True,
    )


# ==============================================================================
# Core helpers
# ==============================================================================
load_dotenv()
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def clamp_chars(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    return cut.rstrip(" ,;:-") + "."


def pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        s = str(v[0]).strip()
        return s or None
    s = str(v).strip()
    return s or None


def build_category_path(labels: Dict[str, str]) -> str:
    parts = [labels.get(k) or "" for k in ("web_department", "web_category", "web_subcategory")]
    parts = [p for p in parts if p]
    return " > ".join(parts) if parts else "-"


def category_levels_from_path(path: str) -> int:
    if not path or path.strip() == "-":
        return 0
    return len([p.strip() for p in path.split(">") if p.strip()])


def call_llm(prompt: str, max_output_tokens: int = 450) -> str:
    if OpenAI is None:
        raise RuntimeError("Missing openai package.")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY.")
    client = OpenAI(api_key=api_key)
    resp = client.responses.create(
        model=MODEL_NAME,
        input=[
            {"role": "system", "content": "Be precise. Do not invent specs. Return only the final text requested."},
            {"role": "user", "content": prompt},
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


def build_category_prompt(
    category_path: str,
    category_name_hint: str,
    top_attrs: List[str],
    keywords: List[str],
    products_count: int,
    max_chars: int,
    output_language: str,
) -> str:
    return f"""
Write ONE eCommerce category description.
LANGUAGE: {output_language}

RULES:
- Single paragraph (no bullets).
- Max {max_chars} characters.
- Do NOT mention price, promos, shipping, warranty, availability.
- Do NOT invent certifications or specs.

CONTEXT:
- Category path: {category_path}
- Category name hint: {category_name_hint or 'N/A'}
- Products in this category (count): {products_count}
- Top attribute IDs (signals): {", ".join(top_attrs) if top_attrs else "N/A"}
- Keywords (signals): {", ".join(keywords) if keywords else "N/A"}

OUTPUT: Return ONLY the final category description text.
""".strip()


def build_delta_xml(category_rows: List[Dict[str, Any]], attribute_id: str) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<STEP-ProductInformation>", "  <Products>"]
    for r in category_rows:
        cid = r.get("category_key")
        txt = r.get("category_description")
        if not cid or not txt:
            continue
        parts += [
            f'    <Product ID="{xml_escape(str(cid))}">',
            "      <Values>",
            f'        <Value AttributeID="{xml_escape(attribute_id)}">{xml_escape(str(txt))}</Value>',
            "      </Values>",
            "    </Product>",
        ]
    parts += ["  </Products>", "</STEP-ProductInformation>"]
    return "\n".join(parts) + "\n"


def safe_write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def validate_step_schema_lite(xml_text: str) -> Tuple[bool, str]:
    required = ["<STEP-ProductInformation", "<Products", "<Product", "<Values", "<Value", "AttributeID="]
    missing = [t for t in required if t not in (xml_text or "")]
    if missing:
        return False, "STEP structural validation failed (missing: " + ", ".join(missing) + ")"
    return True, "STEP structural validation passed."


# ==============================================================================
# XML Viewer helpers
# ==============================================================================
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
    return "\n".join(lines[:n_lines]) if lines else ""


def extract_products_section(xml_text: str, max_products: int = 3) -> str:
    if not xml_text:
        return ""
    lines = xml_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if "<Products>" in line:
            start = i
            break
    if start is None:
        return ""
    product_count = 0
    end = None
    for j in range(start, len(lines)):
        if "<Product " in lines[j]:
            product_count += 1
        if product_count >= max_products and "</Product>" in lines[j]:
            end = j
            break
    if end is None:
        end = min(start + 200, len(lines) - 1)
    return "\n".join(lines[start : end + 1])


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


# ==============================================================================
# Inventory build (scan ALL products) — cached
# ==============================================================================
@st.cache_data(show_spinner=False)
def build_inventory_all_products(product_xml_path_str: str) -> Tuple[List[Dict[str, Any]], int, int]:
    p = Path(product_xml_path_str)
    buckets: Dict[str, Dict[str, Any]] = {}
    total_scanned = 0
    max_levels = 0

    for rec in iter_products_from_step_xml(p, limit=None):
        total_scanned += 1
        parent_id = (rec.parent_id or "").strip()
        if not parent_id:
            continue
        labels = rec.labels or {}
        attrs = rec.attributes or {}
        cat_path = build_category_path(labels)
        lvl = category_levels_from_path(cat_path)
        if lvl > max_levels:
            max_levels = lvl
        b = buckets.setdefault(
            parent_id,
            {
                "category_key": parent_id,
                "category_path": cat_path,
                "category_name_hint": labels.get("web_subcategory")
                or labels.get("web_category")
                or labels.get("web_department")
                or "",
                "products_count": 0,
                "top_attribute_ids": {},
                "keywords": {},
            },
        )
        b["products_count"] += 1
        for k, v in (attrs or {}).items():
            if v is None:
                continue
            b["top_attribute_ids"][k] = b["top_attribute_ids"].get(k, 0) + 1
        name_seed = (rec.web_name or "").lower()
        toks = re.findall(r"[a-záéíóúüñ0-9]{4,}", name_seed)
        for t in toks[:12]:
            b["keywords"][t] = b["keywords"].get(t, 0) + 1

    rows = list(buckets.values())
    rows.sort(key=lambda x: x["products_count"], reverse=True)
    return rows, total_scanned, max_levels


# ==============================================================================
# Page
# ==============================================================================
def render():
    inject_category_css()

    BASE_DIR = Path(__file__).resolve().parents[1]
    OUTPUTS_DIR = BASE_DIR / "outputs"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    OUT_JSONL  = OUTPUTS_DIR / "category_descriptions.jsonl"
    OUT_XML    = OUTPUTS_DIR / "delta_category_descriptions.xml"
    OUT_REPORT = OUTPUTS_DIR / "category_generation_report.json"

    SS_LAST_EXECUTED_KEYS = "cat_last_executed_keys"
    SS_LAST_XML_TEXT      = "cat_last_xml_text"
    SS_LAST_XML_PATH      = "cat_last_xml_path"

    st.title("Category Descriptions")
    st.markdown(
        "Generate category descriptions from **Product XML** signals (labels + attributes). "
        "Export a **delta XML** ready for STEP."
    )
    st.markdown("---")

    if "product_xml_path" not in st.session_state or not st.session_state.product_xml_path:
        st.error("No Product XML loaded. Go to Dataset Overview and upload Product XML first.")
        st.stop()

    product_xml_path = Path(st.session_state.product_xml_path)

    # ── Inventory ──────────────────────────────────────────────────────────────
    st.subheader("Category Inventory")
    inv_cols = st.columns([2, 1])
    with inv_cols[0]:
        st.markdown("<div class='small-muted'>Inventory scans <b>all products</b> (cached). If you update the XML, clear cache to rebuild.</div>", unsafe_allow_html=True)
    with inv_cols[1]:
        if st.button("Rebuild inventory (clear cache)", use_container_width=True, key="cat_rebuild_inv"):
            st.cache_data.clear()
            st.rerun()

    with st.spinner("Building category inventory (all products)..."):
        rows, total_scanned, max_levels = build_inventory_all_products(str(product_xml_path))

    m1, m2, m3, m4 = st.columns([1, 1, 1, 2])
    m1.metric("Categories", len(rows))
    m2.metric("Products scanned", total_scanned)
    m3.metric("Max levels", max_levels)
    m4.markdown("<div class='small-muted'>Categories are grouped by <b>parent_id</b> (Category Key).</div>", unsafe_allow_html=True)

    preview_rows: List[Dict[str, Any]] = []
    for r in rows[:500]:
        top_attrs = sorted(r["top_attribute_ids"].items(), key=lambda kv: kv[1], reverse=True)
        top_kws   = sorted(r["keywords"].items(),          key=lambda kv: kv[1], reverse=True)
        preview_rows.append({
            "Category Key":  r["category_key"],
            "Category Path": r["category_path"],
            "Products":      r["products_count"],
            "Top attrs":     ", ".join([k for (k, _n) in top_attrs[:8]]),
            "Keywords":      ", ".join([k for (k, _n) in top_kws[:10]]),
        })
    st.dataframe(preview_rows, use_container_width=True, height=420)

    # ── Generate ───────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Generate")

    left, right = st.columns([2, 1])

    with left:
        default_keys  = [r["category_key"] for r in rows[:25]]
        selected_keys = st.multiselect(
            "Select categories to generate (default: top 25 by product count)",
            options=[r["category_key"] for r in rows],
            default=default_keys,
            key="cat_sel_keys_v1",
        )

    with right:
        output_language = st.selectbox(
            "Output language",
            options=["English", "Spanish", "Portuguese", "French", "German", "Italian"],
            index=0,
            key="cat_lang_v1",
        )
        attribute_id_for_delta = st.text_input(
            "Category Description AttributeID",
            value="TBD.CATEGORY.WebDescription",
            help="Replace with the real STEP AttributeID once confirmed.",
            key="cat_attr_id_v1",
        )
        max_chars = st.number_input(
            "Max chars",
            min_value=200,
            max_value=1200,
            value=600,
            step=50,
            key="cat_max_chars_v1",
        )
        gen_clicked = st.button("Generate descriptions", use_container_width=True, key="cat_btn_gen_v1")

    if gen_clicked:
        if OpenAI is None:
            st.error("Missing openai package. Install: pip install openai")
            st.stop()
        if not os.getenv("OPENAI_API_KEY", "").strip():
            st.error("Missing OPENAI_API_KEY in your environment (.env).")
            st.stop()
        if not selected_keys:
            st.error("Select at least one category.")
            st.stop()

        selected_set  = set(selected_keys)
        selected_rows = [r for r in rows if r["category_key"] in selected_set]

        progress = st.progress(0)
        status   = st.empty()
        out_rows: List[Dict[str, Any]] = []
        t0 = time.perf_counter()

        for i, r in enumerate(selected_rows, start=1):
            top_attrs = sorted(r["top_attribute_ids"].items(), key=lambda kv: kv[1], reverse=True)
            top_kws   = sorted(r["keywords"].items(),          key=lambda kv: kv[1], reverse=True)

            prompt = build_category_prompt(
                category_path       = r["category_path"],
                category_name_hint  = r["category_name_hint"],
                top_attrs           = [k for (k, _n) in top_attrs[:12]],
                keywords            = [k for (k, _n) in top_kws[:16]],
                products_count      = int(r["products_count"]),
                max_chars           = int(max_chars),
                output_language     = output_language,
            )

            status.markdown(
                f"<div class='goat-success'>Generating {i}/{len(selected_rows)} — <b>{html_escape(r['category_key'])}</b></div>",
                unsafe_allow_html=True,
            )

            txt = call_llm(prompt, max_output_tokens=420)
            txt = clamp_chars(txt, int(max_chars))

            out_rows.append({
                "category_key":          r["category_key"],
                "category_path":         r["category_path"],
                "products_count":        r["products_count"],
                "attribute_id":          attribute_id_for_delta.strip(),
                "max_chars":             int(max_chars),
                "output_language":       output_language,
                "category_description":  txt,
                "model":                 MODEL_NAME,
            })

            progress.progress(i / len(selected_rows))

        xml_text = build_delta_xml(out_rows, attribute_id_for_delta.strip())
        safe_write_jsonl(OUT_JSONL, out_rows)
        OUT_XML.write_text(xml_text, encoding="utf-8")
        OUT_REPORT.write_text(
            json.dumps({
                "generated":               len(out_rows),
                "seconds":                 round(time.perf_counter() - t0, 3),
                "model":                   MODEL_NAME,
                "attribute_id_for_delta":  attribute_id_for_delta.strip(),
                "output_language":         output_language,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        st.session_state[SS_LAST_EXECUTED_KEYS] = [r["category_key"] for r in selected_rows]
        st.session_state[SS_LAST_XML_TEXT]      = xml_text
        st.session_state[SS_LAST_XML_PATH]      = str(OUT_XML)

        st.markdown("<div class='goat-success'>Done. Delta XML generated.</div>", unsafe_allow_html=True)
        st.download_button(
            "Download delta_category_descriptions.xml",
            data=xml_text,
            file_name="delta_category_descriptions.xml",
            mime="application/xml",
            use_container_width=True,
            key="cat_dl_xml_v1",
        )

    # ── XML Viewer ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("<div class='viewer-title'>XML Viewer</div>", unsafe_allow_html=True)

    executed_keys: List[str] = st.session_state.get(SS_LAST_EXECUTED_KEYS, []) or []
    xml_text: str            = st.session_state.get(SS_LAST_XML_TEXT, "")       or ""

    if not executed_keys:
        st.info("No active run. Select categories and generate to preview the XML here.")
        return

    if not xml_text.strip():
        p = Path(st.session_state.get(SS_LAST_XML_PATH, str(OUT_XML)))
        xml_text = _read_text_safe(p)
        st.session_state[SS_LAST_XML_TEXT] = xml_text

    if not xml_text.strip():
        st.warning("No XML found. Generate again.")
        return

    ok, msg = validate_step_schema_lite(xml_text)
    if ok:
        st.markdown(f"<div class='goat-success'>{html_escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.error(msg)

    h1, h2 = st.columns([2, 1])
    with h1:
        n_lines = st.number_input("XML head (lines)", min_value=40, max_value=800, value=140, step=10, key="cat_xml_head_n")
    with h2:
        if st.button("Refresh XML", use_container_width=True, key="cat_refresh_xml"):
            p = Path(st.session_state.get(SS_LAST_XML_PATH, str(OUT_XML)))
            st.session_state[SS_LAST_XML_TEXT] = _read_text_safe(p)
            st.rerun()

    with st.expander("1) XML head", expanded=True):
        st.code(xml_head(xml_text, int(n_lines)), language="xml")

    with st.expander("2) Sanity check: <Products> snippet", expanded=False):
        st.code(extract_products_section(xml_text, max_products=3), language="xml")

    with st.expander("3) Filter by Category Key (<Product ID=...>)", expanded=True):
        ids_in_xml = list_product_ids_from_delta(xml_text)
        allowed    = [k for k in executed_keys if k in set(ids_in_xml)]

        if not allowed:
            st.warning(
                "No Product IDs in XML match the executed category keys. "
                "Check AttributeID and the delta writer output in the XML head."
            )
        else:
            search   = st.text_input("Search Category Keys (optional)", value="", key="cat_xml_search")
            filtered = [i for i in allowed if search.strip().lower() in i.lower()] if search.strip() else allowed
            sel      = st.selectbox("Select Category Key", options=filtered, index=0, key="cat_xml_sel")
            block    = extract_product_block(xml_text, sel)
            st.code(block or "No <Product> block found for this ID.", language="xml")


if __name__ == "__main__":
    render()