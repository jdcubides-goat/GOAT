import streamlit as st
from pathlib import Path

from ui_theme import load_logo
from core.dataset_understanding import analyze_dataset


def render():
    BASE_DIR = Path(__file__).resolve().parents[1]
    LOGO_DIR = BASE_DIR / "logos"
    OUTPUTS_DIR = BASE_DIR / "outputs"
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Template onboarding en raíz
    TEMPLATE_PATH = BASE_DIR / "STIBO_AI_Onboarding_Template_[en].xlsx"

    # ==========================================================
    # CSS GOAT UI
    # ==========================================================
    st.markdown(
        """
        <style>

        /* ======================================================
           File uploader container (gris claro)
        ====================================================== */
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

        /* ======================================================
           BOTÓN NEGRO "Browse files" → GRIS GOAT
        ====================================================== */
        [data-testid="stFileUploader"] button {
            background-color: #E6EAF0 !important;
            color: #003E71 !important;
            border: 1px solid #BCCAD6 !important;
            border-radius: 8px !important;
            font-weight: 700 !important;
        }

        [data-testid="stFileUploader"] button:hover {
            background-color: #D8DEE6 !important;
            color: #003E71 !important;
            border: 1px solid #BCCAD6 !important;
        }
        /* ======================================================
   DOWNLOAD TEMPLATE BUTTON → GRIS GOAT
====================================================== */
[data-testid="stDownloadButton"] button {
    background-color: #E6EAF0 !important;
    color: #003E71 !important;
    border: 1px solid #BCCAD6 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    box-shadow: none !important;
}

[data-testid="stDownloadButton"] button:hover {
    background-color: #D8DEE6 !important;
    color: #003E71 !important;
    border: 1px solid #BCCAD6 !important;
}

        /* ======================================================
           Success block GOAT
        ====================================================== */
        .goat-success {
            background-color: rgba(0, 149, 156, 0.12);
            border: 1px solid rgba(0, 149, 156, 0.35);
            border-radius: 8px;
            padding: 12px 16px;
            color: #00959C;
            font-weight: 800;
            font-size: 0.97rem;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

    # ==========================================================
    # HEADER
    # ==========================================================
    c1, c2, c3 = st.columns([4, 1.2, 1])

    with c1:
        st.title("GOAT AI INNOVATION LABS | Enrichment Platform")
        st.markdown("Client-ready demo flow: Upload → Analyze → Run Cases")

    with c2:
        if TEMPLATE_PATH.exists():
            data = TEMPLATE_PATH.read_bytes()
            st.download_button(
                label="Download template",
                data=data,
                file_name=TEMPLATE_PATH.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with c3:
        load_logo(LOGO_DIR, "stibo.png", width=170)

    st.markdown("---")

    # ==========================================================
    # INPUT FILES
    # ==========================================================
    st.subheader("Input Files")

    colA, colB = st.columns(2)

    with colA:
        product_xml = st.file_uploader(
            "Product XML (required)",
            type=["xml"],
            accept_multiple_files=False,
        )

    with colB:
        pph_xml = st.file_uploader(
            "PPH XML (required)",
            type=["xml"],
            accept_multiple_files=False,
        )

    st.markdown("")

    if "product_xml_path" not in st.session_state:
        st.session_state.product_xml_path = ""

    if "pph_xml_path" not in st.session_state:
        st.session_state.pph_xml_path = ""

    # ==========================================================
    # SAVE UPLOAD
    # ==========================================================
    def _save_upload(upload, filename: str) -> Path:
        p = OUTPUTS_DIR / filename
        p.write_bytes(upload.getvalue())
        return p

    btn = st.button("RUN DEMO", use_container_width=True)

    # ==========================================================
    # RUN DEMO
    # ==========================================================
    if btn:

        if product_xml is None:
            st.error("Product XML is required.")
            st.stop()

        prod_path = _save_upload(product_xml, "product.xml")
        st.session_state.product_xml_path = str(prod_path)

        if pph_xml is not None:
            pph_path = _save_upload(pph_xml, "pph.xml")
            st.session_state.pph_xml_path = str(pph_path)
        else:
            st.session_state.pph_xml_path = ""

        try:
            analyze_dataset(
                product_xml_path=str(prod_path),
                pph_xml_path=st.session_state.pph_xml_path or None,
                output_dir=str(OUTPUTS_DIR),
                max_products=4000,
                sample_products=250,
            )

            st.markdown(
                "<div class='goat-success'>✓ Dataset analysis complete.</div>",
                unsafe_allow_html=True,
            )

        except Exception as e:
            st.error(f"Dataset analysis failed: {e}")
            st.stop()

        st.info("Next: open 'Cases GOAT' to generate Long + Short descriptions.")
        st.stop()

    # ==========================================================
    # CURRENT STATE
    # ==========================================================
    if st.session_state.product_xml_path:
        st.markdown(
            f"<div class='goat-success'>✓ Loaded Product XML: {Path(st.session_state.product_xml_path).name}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.info("Upload Product XML and click RUN DEMO.")