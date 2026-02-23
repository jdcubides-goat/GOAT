import streamlit as st
import os
import xml.etree.ElementTree as ET
import glob
import time

# ==============================================================================
# 1. CONFIGURACIÓN
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ajuste de ruta
if os.path.exists(os.path.join(BASE_DIR, "outputs")):
    OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
else:
    OUTPUTS_DIR = os.path.join(BASE_DIR, "..", "outputs")

LOGO_DIR = os.path.join(BASE_DIR, "logos")

st.set_page_config(
    page_title="GOAT AI | Pipeline Simulator",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=None 
)

# ==============================================================================
# 2. ESTILO CORPORATIVO (DARK TEAL & HIGH CONTRAST)
# ==============================================================================
st.markdown("""
    <style>
    /* FONDO GENERAL */
    .stApp { background-color: #F4F6F8; }
    
    /* TIPOGRAFÍA GLOBAL */
    html, body, [class*="css"] {
        font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
        color: #1F2937;
    }
    
    /* ENCABEZADOS */
    h1, h2, h3 { 
        color: #004D40 !important; /* Dark Teal */
        font-weight: 800 !important; 
    }

    /* BOTÓN DE ACCIÓN PRINCIPAL */
    .stButton>button {
        background-color: #00695C; 
        color: white;
        border: none;
        padding: 14px 28px;
        border-radius: 4px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        transition: all 0.2s;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #004D40; 
        box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        color: white;
    }

    /* TARJETAS DE MÉTRICAS (CUSTOM HTML) */
    .metric-container {
        background-color: white;
        border: 1px solid #CFD8DC;
        border-left: 5px solid #004D40; 
        padding: 20px 25px;
        border-radius: 6px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
    }
    .metric-label {
        font-size: 13px;
        font-weight: 700;
        color: #546E7A;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 32px; 
        font-weight: 800;
        color: #004D40;
    }
    .metric-sub {
        font-size: 12px;
        font-weight: 600;
        color: #2E7D32; 
        margin-top: 4px;
    }

    /* TARJETA DE PRODUCTO */
    .goat-card {
        background-color: white;
        border: 1px solid #E0E0E0;
        border-top: 4px solid #004D40; 
        border-radius: 8px;
        padding: 25px;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }

    /* HEADER INTERNO DEL PRODUCTO */
    .product-header {
        display: flex; align-items: center; justify-content: space-between;
        margin-bottom: 20px; border-bottom: 1px solid #ECEFF1; padding-bottom: 12px;
    }
    .pid-badge {
        background-color: #263238; color: #FFF;
        padding: 6px 12px; border-radius: 4px;
        font-family: monospace; font-weight: 700; font-size: 14px;
    }
    .product-label {
        font-weight: 700; color: #455A64; font-size: 14px;
    }

    /* CAJAS DE DESCRIPCIÓN */
    .desc-header {
        font-size: 11px; font-weight: 800; color: #37474F;
        background-color: #ECEFF1;
        padding: 8px 12px;
        border-radius: 4px 4px 0 0;
        border: 1px solid #CFD8DC;
        border-bottom: none;
        text-transform: uppercase;
    }
    .desc-box {
        background-color: #FFF;
        border: 1px solid #CFD8DC;
        border-radius: 0 0 4px 4px;
        padding: 15px;
        color: #212121; 
        font-size: 14px;
        line-height: 1.5;
        min-height: 80px;
    }
    
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 3. LÓGICA DE DATOS
# ==============================================================================

def load_logo(filename, width=None):
    try:
        path = os.path.join(LOGO_DIR, filename)
        if os.path.exists(path):
            if width: st.image(path, width=width)
            else: st.image(path, use_column_width=True)
    except: pass

def get_merged_data():
    merged = {}
    if not os.path.exists(OUTPUTS_DIR):
        return {}

    xml_files = glob.glob(os.path.join(OUTPUTS_DIR, "*.xml"))
    
    for file_path in xml_files:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            for product in root.findall(".//Product"):
                pid = product.get("ID")
                if not pid: continue
                if pid not in merged: merged[pid] = {"short": None, "long": None}
                
                for val in product.findall(".//Value"):
                    aid = val.get("AttributeID")
                    text = "".join(val.itertext()) if val.itertext() else val.text
                    
                    if aid == "THD.PR.WebShortDescription":
                        merged[pid]["short"] = text
                    elif aid == "THD.PR.WebLongDescription":
                        merged[pid]["long"] = text
        except: pass
    return merged

# ==============================================================================
# 4. UI PRINCIPAL
# ==============================================================================

def render_app():
    # --- ESTADO DE LA SESIÓN ---
    if 'simulation_run' not in st.session_state:
        st.session_state.simulation_run = False

    # --- SIDEBAR ---
    with st.sidebar:
        load_logo("goat.png", width=140)
        st.markdown("### CONTROL CENTER")
        st.markdown("**Environment:** Production")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # BOTÓN
        if st.button("RUN SIMULATION"):
            with st.spinner("Processing Pipeline..."):
                time.sleep(1.5) 
            st.session_state.simulation_run = True
            st.rerun()
            
        st.markdown("---")
        if st.session_state.simulation_run:
            st.success("Pipeline Executed")
            if st.button("RESET VIEW"):
                st.session_state.simulation_run = False
                st.rerun()

    # --- MAIN CONTENT ---
    
    # Header: Ajustamos las columnas para dar espacio al logo Stibo más ancho
    c1, c2 = st.columns([3.5, 1.5]) 
    with c1:
        st.title("GOAT AI | Enrichment Platform")
        st.markdown("Automated Content Generation for **Home Depot STEP**")
    with c2:
        st.write("")
        # --- CAMBIO AQUI: AUMENTADO A 200px ---
        load_logo("stibo.png", width=200) 
    
    st.markdown("---")

    # --- PANTALLA DE INICIO ---
    if not st.session_state.simulation_run:
        st.info("System Ready. Initialize the simulation from the sidebar.")
        return

    # --- PANTALLA DE RESULTADOS ---
    data = get_merged_data()
    
    if not data:
        st.error("No output data found. Verify Python scripts execution.")
        return

    # --- MÉTRICAS ---
    m1, m2 = st.columns(2)
    
    with m1:
        st.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">Products Enriched</div>
            <div class="metric-value">{len(data)}</div>
            <div class="metric-sub">+ New Records</div>
        </div>
        """, unsafe_allow_html=True)
        
    with m2:
        st.markdown("""
        <div class="metric-container">
            <div class="metric-label">Status</div>
            <div class="metric-value">Ready</div>
            <div class="metric-sub">Valid for Export</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LOOP DE TARJETAS ---
    for pid, content in data.items():
        
        long_text = content['long'] if content['long'] else "No Long Description Generated."
        short_text = content['short'] if content['short'] else "No Short Description Generated."

        st.markdown(f"""
        <div class="goat-card">
            <div class="product-header">
                <span class="pid-badge">{pid}</span>
                <span class="product-label">STEP Writeback Preview</span>
            </div>
        """, unsafe_allow_html=True)

        # COLUMNAS
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            <div>
                <div class="desc-header">CASE 1: LONG DESCRIPTION</div>
                <div class="desc-box">{long_text}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div>
                <div class="desc-header">CASE 2: SHORT DESCRIPTION</div>
                <div class="desc-box">{short_text}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

# ENTRY POINT
if __name__ == "__main__":
    render_app()