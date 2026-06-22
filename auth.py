import streamlit as st
import os

ALLOWED_EMAILS_RAW = os.getenv("ALLOWED_EMAILS") or st.secrets.get("ALLOWED_EMAILS", "")
if isinstance(ALLOWED_EMAILS_RAW, str):
    ALLOWED_EMAILS = [email.strip() for email in ALLOWED_EMAILS_RAW.split(",") if email.strip()]
else:
    ALLOWED_EMAILS = ALLOWED_EMAILS_RAW

def require_login():
    if os.getenv("STAGE") == "DEV":
        return
    
    is_logged_in = False
    
    if hasattr(st.user, "is_logged_in"):
        is_logged_in = st.user.is_logged_in
    elif hasattr(st.user, "is_authenticated"):
        is_logged_in = st.user.is_authenticated
    else:
        is_logged_in = bool(st.user.get("email"))

    if not is_logged_in:
        st.login()
        st.stop()

    user_email = st.user.get("email")
    
    if not user_email or user_email not in ALLOWED_EMAILS:
        st.error("Acesso negado: Seu e-mail não está cadastrado na lista de permissões.")
        try:
            st.logout()
        except AttributeError:
            pass # Ignora caso o método logout também não exista na versão antiga do servidor
        st.stop()