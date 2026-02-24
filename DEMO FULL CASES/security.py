import streamlit as st
import bcrypt

# ============================================================
# USERS DATABASE (PRO MODE)
# ============================================================

USERS = {
    "admin": "$2b$12$LLKUwkg8dwfH7CigVpWOGeJro9buRxeaX1diIGjbo/ZAlaXWCSMnS"
}


# ============================================================
# VERIFY PASSWORD
# ============================================================

def verify_password(username: str, password: str) -> bool:
    if username not in USERS:
        return False

    stored_hash = USERS[username].encode()
    return bcrypt.checkpw(password.encode(), stored_hash)


# ============================================================
# LOGIN SCREEN (GOAT STYLE)
# ============================================================

def render_login():

    st.markdown(
        """
        <div style='text-align:center;margin-top:120px'>
            <h1 style='color:#003E71'>GOAT AI INNOVATION LABS</h1>
            <p style='color:#00959C;font-weight:700'>Secure Access Portal</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1,2,1])

    with col2:
        user = st.text_input("Username")
        pwd  = st.text_input("Password", type="password")

        if st.button("LOGIN", use_container_width=True):
            if verify_password(user, pwd):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid credentials")