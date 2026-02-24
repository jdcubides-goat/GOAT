import importlib
import streamlit as st
from pathlib import Path

from ui_theme import apply_goat_theme, load_logo
from security import require_login, logout_button_sidebar

# ==============================================================================
# Config
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent
LOGO_DIR = BASE_DIR / "logos"

st.set_page_config(
    page_title="GOAT AI INNOVATION LABS | Enrichment Platform",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon=None,
)

apply_goat_theme()

# Ocultar navegación default de Streamlit (la lista de páginas automática)
st.markdown(
    """
<style>
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"]{ display:none; }
</style>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# LOGIN GATE (SIMPLE Y ESTABLE)
# ==============================================================================
require_login(app_title="GOAT AI INNOVATION LABS")

# ==============================================================================
# Router (pages)
# ==============================================================================
PAGES = {
    "Dataset Overview": "pages.dataset_overview",
    "Category Descriptions": "pages.category_descriptions",
    "Cases GOAT": "pages.cases_goat",
}

DEFAULT_PAGE = "Dataset Overview"

if "page" not in st.session_state:
    st.session_state.page = DEFAULT_PAGE


def go(page_name: str) -> None:
    st.session_state.page = page_name
    st.rerun()


# ==============================================================================
# Sidebar (logo arriba + menu debajo)
# ==============================================================================
with st.sidebar:
    load_logo(LOGO_DIR, "goat.png", width=160)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-weight:900; letter-spacing:.06em; color: var(--goat-navy); "
        "text-transform: uppercase; font-size:.85rem;'>Navigation</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    for name in PAGES.keys():
        is_active = (st.session_state.page == name)
        label = f"• {name}" if is_active else name
        clicked = st.button(label, use_container_width=True, key=f"nav_{name}")
        if clicked:
            go(name)

    logout_button_sidebar()

# ==============================================================================
# Render page
# ==============================================================================
module_name = PAGES.get(st.session_state.page, PAGES[DEFAULT_PAGE])

try:
    page_mod = importlib.import_module(module_name)
except Exception as e:
    st.error(f"Could not import page module '{module_name}'. Error: {e}")
    st.stop()

if not hasattr(page_mod, "render"):
    st.error(f"Page module '{module_name}' has no render() function.")
    st.stop()

page_mod.render()