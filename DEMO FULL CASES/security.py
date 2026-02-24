from __future__ import annotations

import base64
import time
from typing import Dict
from pathlib import Path

import bcrypt
import streamlit as st


# ============================================================
# FALLBACK USERS
# ============================================================
FALLBACK_USERS: Dict[str, str] = {
    "admin": "$2b$12$LLKUwkg8dwfH7CigVpWOGeJro9buRxeaX1diIGjbo/ZAlaXWCSMnS",
    "goat":  "$2b$12$mSlMDeNAblOO.Ma58YzmEe961CXIRn9YjhNtQ6275HjsDNb1U/UVi",
    "juan":  "$2b$12$yn9tx8eMmRSQCHzsM3tPJ.ATEHQ4L2hhKvbCcJ2pyGPsCpj/sWDZu",
}


# ============================================================
# USERS MAP
# ============================================================
def _get_users_map() -> Dict[str, str]:
    try:
        auth = st.secrets.get("auth", {})
        users = auth.get("users", {})
        if isinstance(users, dict) and users:
            return {str(k): str(v) for k, v in users.items()}
    except Exception:
        pass
    return dict(FALLBACK_USERS)


def _check_password(username: str, password: str) -> bool:
    users = _get_users_map()
    hashed = users.get(username)
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ============================================================
# LOGO → base64
# ============================================================
def _logo_base64(logo_path: Path) -> str | None:
    try:
        data = logo_path.read_bytes()
        b64  = base64.b64encode(data).decode("utf-8")
        ext  = logo_path.suffix.lower().lstrip(".")
        mime = "image/png" if ext == "png" else f"image/{ext}"
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


# ============================================================
# LOGIN CSS
# ============================================================
def _inject_login_css() -> None:
    st.markdown(
        """
<style>
/* ── hide default Streamlit chrome on login page ── */
#MainMenu, footer, header { visibility: hidden; }

.login-wrap {
  max-width: 480px;
  margin: 0 auto;
  padding-top: 48px;
}
.login-logo {
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 22px;
}
.login-logo img {
  width: 180px;
  height: auto;
}
.login-title {
  text-align: center;
  font-weight: 950;
  letter-spacing: .06em;
  color: #003E71;
  font-size: 1.35rem;
  margin-bottom: 6px;
}
.login-sub {
  text-align: center;
  color: #00959C;
  font-weight: 800;
  margin-bottom: 26px;
}
.login-card {
  background: #FFFFFF;
  border: 1px solid rgba(188,202,214,0.9);
  border-radius: 18px;
  padding: 22px 22px 16px 22px;
  box-shadow: 0 10px 30px rgba(2,6,23,0.06);
}
div[data-testid="stTextInput"] input {
  background-color: #F0F2F6 !important;
  color: #003E71 !important;
  border: 1px solid #BCCAD6 !important;
  border-radius: 10px !important;
}
div[data-testid="stButton"] button {
  background-color: #003E71 !important;
  color: #FFFFFF !important;
  border: 0 !important;
  border-radius: 12px !important;
  font-weight: 900 !important;
  padding: 10px 14px !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# LOGIN
# ============================================================
def require_login(app_title: str = "GOAT AI INNOVATION LABS") -> None:

    st.session_state.setdefault("auth_ok",           False)
    st.session_state.setdefault("auth_user",          "")
    st.session_state.setdefault("auth_attempts",      0)
    st.session_state.setdefault("auth_locked_until",  0.0)

    if st.session_state["auth_ok"]:
        return

    _inject_login_css()

    now          = time.time()
    locked_until = float(st.session_state.get("auth_locked_until", 0.0))
    if now < locked_until:
        wait_s = int(locked_until - now)
        st.error(f"Too many attempts. Try again in {wait_s}s.")
        st.stop()

    # ── logo path ──────────────────────────────────────────────────────────────
    BASE_DIR  = Path(__file__).resolve().parent
    logo_path = BASE_DIR / "logos" / "goat.png"
    logo_src  = _logo_base64(logo_path)

    # ── centered wrapper ───────────────────────────────────────────────────────
    logo_html = (
        f'<div class="login-logo"><img src="{logo_src}" alt="GOAT logo"></div>'
        if logo_src else ""
    )

    st.markdown(
        f"""
<div class="login-wrap">
  {logo_html}
  <div class="login-title">{app_title}</div>
  <div class="login-sub">Secure Access Portal</div>
  <div class="login-card">
""",
        unsafe_allow_html=True,
    )

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")
    submit   = st.button("Sign in", use_container_width=True, key="login_submit")

    st.markdown("</div></div>", unsafe_allow_html=True)

    if submit:
        u  = (username or "").strip()
        ok = _check_password(u, password or "")
        if ok:
            st.session_state["auth_ok"]       = True
            st.session_state["auth_user"]     = u
            st.session_state["auth_attempts"] = 0
            st.rerun()
        else:
            st.session_state["auth_attempts"] += 1
            st.error("Invalid credentials.")
            if st.session_state["auth_attempts"] >= 5:
                st.session_state["auth_locked_until"] = time.time() + 60
                st.session_state["auth_attempts"]     = 0

    st.stop()


# ============================================================
# SIDEBAR LOGOUT
# ============================================================
def logout_button_sidebar() -> None:
    with st.sidebar:
        st.markdown("---")
        st.caption(f"Signed in as **{st.session_state.get('auth_user', '')}**")
        if st.button("Logout", use_container_width=True, key="btn_logout_sidebar"):
            st.session_state["auth_ok"]   = False
            st.session_state["auth_user"] = ""
            st.rerun()