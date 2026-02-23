import streamlit as st
from pathlib import Path

from core.models import StagingBundle
from stepxml.reader import XmlStream
from stepxml.extract_pph import extract_hierarchy_from_streams
from stepxml.extract_products import extract_products_from_streams
from stepxml.staging import (
    build_category_paths,
    build_product_context_map,
    compute_report,
    persist_staging,
)
from pathlib import Path
from dotenv import load_dotenv
import os

# Cargar .env desde DEMO/.env (porque ya lo pusiste ahí)
DEMO_DIR = Path(__file__).resolve().parent
load_dotenv(DEMO_DIR / ".env", override=True)

DEMO_DIR = Path(__file__).resolve().parent
OUTPUTS_DEMO = DEMO_DIR / "outputs_demo"

st.set_page_config(page_title="GOAT | DEMO STEP Simulator", layout="wide")


def file_to_stream(uploaded) -> XmlStream:
    # uploaded is a Streamlit UploadedFile (file-like)
    return XmlStream(filename=uploaded.name, fileobj=uploaded)


st.title("GOAT DEMO | STEP Simulator (Upload → Parse → Preview)")
st.markdown("Upload **PPH** XML(s) and **ProductSampleData** XML(s). Then click **Parse & Preview**.")

left, right = st.columns(2)

with left:
    st.subheader("Slot 1 — PPH XML(s)")
    pph_files = st.file_uploader(
        "Upload one or more PPH XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="pph_upload",
    )

with right:
    st.subheader("Slot 2 — ProductSampleData XML(s)")
    prod_files = st.file_uploader(
        "Upload one or more ProductSampleData XML files",
        type=["xml"],
        accept_multiple_files=True,
        key="prod_upload",
    )

parse_clicked = st.button("Parse & Preview", use_container_width=True)

if "staging" not in st.session_state:
    st.session_state["staging"] = None

if parse_clicked:
    if not pph_files:
        st.error("Please upload at least one PPH XML.")
        st.stop()
    if not prod_files:
        st.error("Please upload at least one ProductSampleData XML.")
        st.stop()

    pph_streams = [file_to_stream(f) for f in pph_files]
    prod_streams = [file_to_stream(f) for f in prod_files]

    with st.spinner("Parsing PPH..."):
        hierarchy = extract_hierarchy_from_streams(pph_streams)

    with st.spinner("Parsing ProductSampleData..."):
        # Allowed types can be refined later; for now parse all Product nodes
        products = extract_products_from_streams(prod_streams, allowed_user_type_ids=None)

    category_paths = build_category_paths(hierarchy)
    product_ctx, without_parent, unmatched = build_product_context_map(products, category_paths)

    report = compute_report(hierarchy, products)
    report.pph_files = [s.filename for s in pph_streams]
    report.product_files = [s.filename for s in prod_streams]
    report.products_without_parent = without_parent
    report.products_unmatched_category = unmatched

    bundle = StagingBundle(
        hierarchy_index=hierarchy,
        products_index=products,
        category_path_index=category_paths,
        product_context_map=product_ctx,
        report=report,
    )

    st.session_state["staging"] = bundle

    persist_staging(bundle, OUTPUTS_DEMO)

    st.success("Parse complete. Staging saved in session_state and outputs_demo/.")


bundle: StagingBundle | None = st.session_state.get("staging")
if bundle is None:
    st.info("Upload files and click Parse & Preview.")
    st.stop()

st.markdown("---")
st.subheader("Parse Report")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Hierarchy nodes", bundle.report.hierarchy_nodes)
c2.metric("Attribute links", bundle.report.attribute_links)
c3.metric("Products", bundle.report.products)
c4.metric("Avg attributes/product", f"{bundle.report.avg_attributes_per_product:.1f}")

c5, c6 = st.columns(2)
c5.metric("Products w/o ParentID", bundle.report.products_without_parent)
c6.metric("Products unmatched category", bundle.report.products_unmatched_category)

with st.expander("Files"):
    st.write({"PPH": bundle.report.pph_files, "ProductSampleData": bundle.report.product_files})

st.markdown("---")
st.subheader("Preview (Products)")

# Build a light preview table
rows = []
for pid, p in list(bundle.products_index.items())[:200]:
    ctx = bundle.product_context_map.get(pid, {})
    brand = p.values.get("THD.PR.BrandID").text if p.values.get("THD.PR.BrandID") else ""
    model = p.values.get("THD.PR.Model").text if p.values.get("THD.PR.Model") else ""
    rows.append({
        "product_id": pid,
        "parent_id": p.parent_id or "",
        "category_path": ctx.get("category_path", ""),
        "name": p.name,
        "brand": brand,
        "model": model,
        "attributes_count": len(p.values),
    })

st.dataframe(rows, use_container_width=True, height=420)

st.markdown("**Staging outputs:**")
st.code(str(OUTPUTS_DEMO), language="text")
