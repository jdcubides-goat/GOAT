from __future__ import annotations

import time
from typing import Dict, Optional

import bcrypt
import streamlit as st


# ==============================================================================
# USERS (bcrypt)
# 1) goat  -> goat
# 2) admin -> admin
# 3) juan  -> goat
# IMPORTANT:
# - These hashes are the ones you generated.
# - If you generated them in a different order, just swap them accordingly.
# ==============================================================================
USERS: Dict[str, str] = {
    "goat":  "$2b$12$mSlMDeNAblOO.Ma58YzmEe961CXIRn9YjhNtQ6275HjsDNb1U/UVi",
    "admin": "$2b$12$yn9tx8eMmRSQCHzsM3tPJ.ATEHQ4L2hhKvbCcJ2pyGPsCpj/sWDZu",
    "juan":  "$2b$12$4p6L7OEu9hoZFbBRpGjwCeOdyBzAh5vLyqwRQ8P25vS33XkMYcyJe",
}


def _get_user_hash(username: str) -> Optional[str]:
    u = (username or "").strip()
    if not u:
        return None
    return USERS.get(u)


def _check_password(username: str, password: str) -> bool:
    hashed = _get_user_hash(username)
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def require_login(app_title: str = "GOAT") -> None:
    # Session flags
    if "auth_ok" not in st.session_state:
        st.session_state.auth_ok = False
    if "auth_user" not in st.session_state:
        st.session_state.auth_user = ""

    # Throttling / lock
    if "auth_attempts" not in st.session_state:
        st.session_state.auth_attempts = 0
    if "auth_locked_until" not in st.session_state:
        st.session_state.auth_locked_until = 0.0

    # Already logged in -> show logout
    if st.session_state.auth_ok:
        with st.sidebar:
            st.markdown("---")
            st.caption(f"Signed in as **{st.session_state.auth_user}**")
            if st.button("Logout", use_container_width=True, key="btn_logout"):
                st.session_state.auth_ok = False
                st.session_state.auth_user = ""
                st.rerun()
        return

    # Locked?
    now = time.time()
    if now < float(st.session_state.auth_locked_until):
        wait_s = int(st.session_state.auth_locked_until - now)
        st.error(f"Too many attempts. Try again in {wait_s}s.")
        st.stop()

    # Login UI
    st.title("Sign in")
    st.caption(f"{app_title} access requires authentication.")

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    col1, col2 = st.columns([1, 2])
    with col1:
        submit = st.button("Sign in", use_container_width=True, key="login_submit")
    with col2:
        st.caption(" ")

    if submit:
        ok = _check_password(username.strip(), password)
        if ok:
            st.session_state.auth_ok = True
            st.session_state.auth_user = username.strip()
            st.session_state.auth_attempts = 0
            st.session_state.auth_locked_until = 0.0
            st.success("Welcome.")
            st.rerun()
        else:
            st.session_state.auth_attempts += 1
            st.error("Invalid credentials.")

            # lock after 5 failed attempts
            if st.session_state.auth_attempts >= 5:
                st.session_state.auth_locked_until = time.time() + 60  # 60s lock
                st.session_state.auth_attempts = 0

    st.stop()