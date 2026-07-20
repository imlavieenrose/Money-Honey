"""
honeymoney — Expense Tracker berbasis chatbot.

Cara jalan:
    streamlit run app.py

Struktur:
    - auth.py     -> login / sign up (Supabase Auth)
    - database.py -> CRUD expense ke Supabase
    - llm.py      -> orkestrasi chatbot (Groq, tool calling)
    - config.py   -> kategori, model, system prompt
    - utils.py    -> helper format Rupiah & tanggal
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import is_logged_in, render_auth_page, sign_out
from config import EXPENSE_CATEGORIES
from database import (
    delete_expense,
    fetch_expenses,
    get_monthly_summary,
    restore_session_if_any,
    update_expense_category,
)
from llm import get_chatbot_response
from utils import format_rupiah, month_name_id, now_local

st.set_page_config(page_title="HoneyMoney — Expense Tracker", page_icon="💸", layout="wide")


def check_secrets() -> bool:
    required = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "GROQ_API_KEY"]
    missing = [k for k in required if k not in st.secrets]
    if missing:
        st.error(
            "Konfigurasi belum lengkap. Key berikut belum ada di secrets.toml: "
            + ", ".join(missing)
            + ".\n\nLihat file `.streamlit/secrets.toml.example` di repo untuk contoh."
        )
        return False
    return True


def render_expense_card(row: dict) -> None:
    with st.container(border=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"**{row.get('description', '-')}**")
            st.caption(f"{row.get('category', '-')} • {row.get('expense_date', '-')}")
        with c2:
            st.markdown(f"### {format_rupiah(float(row.get('amount', 0)))}")


def render_report_payload(payload: dict) -> None:
    summary = payload["summary"]
    year, month = payload["year"], payload["month"]

    if summary["total"] == 0:
        st.info(f"Belum ada transaksi tercatat di {month_name_id(month)} {year}.")
        return

    c1, c2 = st.columns(2)
    c1.metric(f"Total {month_name_id(month)} {year}", format_rupiah(summary["total"]))
    c2.metric("Jumlah transaksi", len(summary["transactions"]))

    fig = px.pie(
        summary["by_category"],
        names="category",
        values="amount",
        hole=0.45,
    )
    fig.update_traces(textinfo="percent+label")
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350)
    st.plotly_chart(fig, use_container_width=True, key=f"report_chart_{year}_{month}_{id(payload)}")


def render_ui_payload(payload: dict) -> None:
    if payload["type"] == "expense_recorded":
        render_expense_card(payload["row"])
    elif payload["type"] == "report":
        render_report_payload(payload)


def render_chat_tab(user_id: str) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "Halo! 👋 Aku honeymoney, asisten pencatat pengeluaranmu. "
                    "Coba ceritakan pengeluaranmu, misalnya:\n\n"
                    "> *\"beli kopi 25rb tadi pagi\"*\n\n"
                    "atau minta laporan, misalnya:\n\n"
                    "> *\"rekap pengeluaran bulan ini\"*"
                ),
                "ui": [],
            }
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            for payload in msg.get("ui", []):
                render_ui_payload(payload)

    user_input = st.chat_input("Tulis pengeluaranmu atau minta laporan...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input, "ui": []})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Riwayat percakapan untuk konteks LLM (role+content saja, batasi 20 pesan terakhir)
        history_for_llm = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-20:-1]
        ]

        with st.chat_message("assistant"):
            with st.spinner("honeymoney lagi mikir..."):
                try:
                    reply_text, ui_payloads = get_chatbot_response(user_input, user_id, history_for_llm)
                except Exception as e:
                    reply_text = f"Waduh, ada error saat menghubungi Groq API: {e}"
                    ui_payloads = []
            st.markdown(reply_text)
            for payload in ui_payloads:
                render_ui_payload(payload)

        st.session_state.messages.append({"role": "assistant", "content": reply_text, "ui": ui_payloads})


def render_report_tab(user_id: str) -> None:
    st.subheader("📊 Riwayat & Laporan Bulanan")

    today = now_local().date()
    years = list(range(today.year - 3, today.year + 1))
    c1, c2 = st.columns(2)
    with c1:
        selected_year = st.selectbox("Tahun", years, index=len(years) - 1)
    with c2:
        selected_month = st.selectbox(
            "Bulan", list(range(1, 13)), index=today.month - 1,
            format_func=month_name_id,
        )

    summary = get_monthly_summary(user_id, selected_year, selected_month)

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Pengeluaran", format_rupiah(summary["total"]))
    m2.metric("Jumlah Transaksi", len(summary["transactions"]))
    top_category = (
        summary["by_category"].iloc[0]["category"] if not summary["by_category"].empty else "-"
    )
    m3.metric("Kategori Terbesar", top_category)

    if not summary["by_category"].empty:
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            fig_pie = px.pie(summary["by_category"], names="category", values="amount", hole=0.45)
            fig_pie.update_traces(textinfo="percent+label")
            fig_pie.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350)
            st.plotly_chart(fig_pie, use_container_width=True, key="tab_report_pie")
        with col_chart2:
            fig_bar = px.bar(
                summary["by_category"].sort_values("amount"),
                x="amount", y="category", orientation="h",
            )
            fig_bar.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, yaxis_title="", xaxis_title="Rupiah")
            st.plotly_chart(fig_bar, use_container_width=True, key="tab_report_bar")
    else:
        st.info("Belum ada data untuk periode ini.")

    st.markdown("#### Daftar Transaksi")
    st.caption("Ubah kategori langsung di tabel, centang 'Hapus' untuk transaksi yang mau dibuang, lalu klik Simpan.")

    df = summary["transactions"].copy()
    if df.empty:
        st.write("Belum ada transaksi di periode ini.")
        return

    df["Hapus"] = False
    display_df = df[["id", "expense_date", "description", "category", "amount", "Hapus"]].rename(
        columns={
            "expense_date": "Tanggal",
            "description": "Deskripsi",
            "category": "Kategori",
            "amount": "Nominal",
        }
    )

    edited_df = st.data_editor(
        display_df,
        hide_index=True,
        use_container_width=True,
        disabled=["id", "Tanggal", "Deskripsi", "Nominal"],
        column_config={
            "id": None,  # sembunyikan kolom id dari tampilan
            "Kategori": st.column_config.SelectboxColumn(options=EXPENSE_CATEGORIES, required=True),
            "Nominal": st.column_config.NumberColumn(format="Rp %d"),
        },
        key=f"editor_{selected_year}_{selected_month}",
    )

    if st.button("💾 Simpan Perubahan", type="primary"):
        changes = 0
        deletions = 0
        for _, row in edited_df.iterrows():
            original_row = df[df["id"] == row["id"]].iloc[0]
            if row["Hapus"]:
                delete_expense(row["id"])
                deletions += 1
            elif row["Kategori"] != original_row["category"]:
                update_expense_category(row["id"], row["Kategori"])
                changes += 1
        if changes or deletions:
            st.success(f"Tersimpan: {changes} kategori diubah, {deletions} transaksi dihapus.")
            st.rerun()
        else:
            st.info("Tidak ada perubahan.")

    csv = df.drop(columns=["Hapus"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Unduh CSV",
        data=csv,
        file_name=f"expenses_{selected_year}_{selected_month:02d}.csv",
        mime="text/csv",
    )


def render_sidebar(user_id: str) -> None:
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.get('user_email', '')}**")

        today = now_local().date()
        this_month = get_monthly_summary(user_id, today.year, today.month)
        st.metric(f"Pengeluaran {month_name_id(today.month)} ini", format_rupiah(this_month["total"]))

        st.divider()
        if st.button("🗑️ Bersihkan tampilan chat", use_container_width=True):
            st.session_state.pop("messages", None)
            st.rerun()

        if st.button("Keluar", use_container_width=True):
            sign_out()
            st.rerun()


def main() -> None:
    if not check_secrets():
        st.stop()

    restore_session_if_any()

    if not is_logged_in():
        render_auth_page()
        st.stop()

    user_id = st.session_state["user_id"]
    render_sidebar(user_id)

    st.title("💸 honeymoney")
    tab_chat, tab_report = st.tabs(["💬 Chat", "📊 Riwayat & Laporan"])
    with tab_chat:
        render_chat_tab(user_id)
    with tab_report:
        render_report_tab(user_id)


if __name__ == "__main__":
    main()
