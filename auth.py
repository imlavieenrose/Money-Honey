"""
Modul autentikasi memakai Supabase Auth (email + password).
Berisi fungsi sign up / sign in / sign out, serta form UI login-signup
yang ditampilkan sebelum pengguna bisa mengakses aplikasi utama.
"""

import streamlit as st

from database import get_supabase_client


def sign_up(email: str, password: str) -> tuple[bool, str]:
    client = get_supabase_client()
    try:
        client.auth.sign_up({"email": email, "password": password})
        return True, (
            "Akun berhasil dibuat! Jika konfirmasi email aktif di project Supabase-mu, "
            "cek inbox untuk verifikasi sebelum login. Kalau tidak, langsung saja login."
        )
    except Exception as e:
        return False, f"Gagal mendaftar: {e}"


def sign_in(email: str, password: str) -> tuple[bool, str]:
    client = get_supabase_client()
    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state["access_token"] = result.session.access_token
        st.session_state["refresh_token"] = result.session.refresh_token
        st.session_state["user_id"] = result.user.id
        st.session_state["user_email"] = result.user.email
        return True, "Berhasil login!"
    except Exception as e:
        return False, f"Gagal login: {e}"


def sign_out() -> None:
    client = get_supabase_client()
    try:
        client.auth.sign_out()
    except Exception:
        pass
    for key in (
        "access_token",
        "refresh_token",
        "user_id",
        "user_email",
        "chat_history",
        "supabase_client",
    ):
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_id"))


def render_auth_page() -> None:
    """Menampilkan form login & sign up. Dipanggil dari app.py saat user belum login."""
    st.title("💸 Duitin — Pencatat Expense")
    st.caption("Catat pengeluaranmu cukup dengan mengobrol. Login atau daftar dulu, yuk.")

    tab_login, tab_signup = st.tabs(["Masuk", "Daftar Akun"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Masuk", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.warning("Email dan password wajib diisi.")
                else:
                    with st.spinner("Memeriksa akun..."):
                        ok, message = sign_in(email, password)
                    if ok:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input(
                "Password", type="password", key="signup_password",
                help="Minimal 6 karakter (default aturan Supabase Auth).",
            )
            password_confirm = st.text_input(
                "Konfirmasi Password", type="password", key="signup_password_confirm"
            )
            submitted = st.form_submit_button("Daftar", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.warning("Email dan password wajib diisi.")
                elif password != password_confirm:
                    st.warning("Konfirmasi password tidak sama.")
                else:
                    with st.spinner("Membuat akun..."):
                        ok, message = sign_up(email, password)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)
