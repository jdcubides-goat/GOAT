# core/ui_theme.py
import streamlit as st

def inject_theme() -> None:
    st.markdown("""<style>
    /* pega aquí TU CSS completo (el de app.py) */
    </style>""", unsafe_allow_html=True)