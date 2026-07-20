"""
Modul untuk semua interaksi dengan Supabase: koneksi client & operasi CRUD
pada tabel `expenses`. Autentikasi (sign up / sign in) ada di auth.py.
"""

from datetime import date, datetime
from typing import Optional

import pandas as pd
import streamlit as st
from supabase import Client, create_client

from config import EXPENSES_TABLE


def get_supabase_client() -> Client:
    """
    Mengembalikan Supabase client milik SESI PENGGUNA saat ini.

    PENTING: client disimpan di st.session_state (bukan @st.cache_resource),
    supaya setiap sesi browser punya client & auth token sendiri-sendiri.
    Kalau di-cache global, token login satu user bisa "bocor" dipakai user lain
    saat aplikasi di-deploy dan diakses banyak orang sekaligus.
    """
    if "supabase_client" not in st.session_state:
        st.session_state.supabase_client = create_client(
            st.secrets["SUPABASE_URL"],
            st.secrets["SUPABASE_ANON_KEY"],
        )
    return st.session_state.supabase_client


def restore_session_if_any() -> None:
    """
    Setelah Streamlit rerun, client baru (jika baru dibuat) belum tentu tahu
    bahwa user sudah login. Kalau kita punya token tersimpan di session_state,
    pasang kembali sesi itu ke client.
    """
    if st.session_state.get("access_token") and st.session_state.get("refresh_token"):
        client = get_supabase_client()
        try:
            client.auth.set_session(
                st.session_state["access_token"],
                st.session_state["refresh_token"],
            )
        except Exception:
            # Token kadaluarsa / tidak valid -> anggap user perlu login ulang
            for key in ("access_token", "refresh_token", "user_email", "user_id"):
                st.session_state.pop(key, None)


def insert_expense(
    user_id: str,
    amount: float,
    category: str,
    description: str,
    expense_date: str,
    raw_input: Optional[str] = None,
) -> dict:
    """Menyimpan satu transaksi expense baru ke Supabase."""
    client = get_supabase_client()
    payload = {
        "user_id": user_id,
        "amount": amount,
        "category": category,
        "description": description,
        "expense_date": expense_date,
        "raw_input": raw_input,
    }
    result = client.table(EXPENSES_TABLE).insert(payload).execute()
    return result.data[0] if result.data else {}


def fetch_expenses(
    user_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> pd.DataFrame:
    """Mengambil expense milik user, opsional difilter rentang tanggal."""
    client = get_supabase_client()
    query = client.table(EXPENSES_TABLE).select("*").eq("user_id", user_id)

    if start_date:
        query = query.gte("expense_date", start_date.isoformat())
    if end_date:
        query = query.lte("expense_date", end_date.isoformat())

    result = query.order("expense_date", desc=True).order("created_at", desc=True).execute()
    df = pd.DataFrame(result.data)

    if not df.empty:
        df["expense_date"] = pd.to_datetime(df["expense_date"]).dt.date
        df["amount"] = df["amount"].astype(float)

    return df


def update_expense_category(expense_id: str, new_category: str) -> None:
    """Mengubah kategori sebuah transaksi (dipakai saat user mengoreksi hasil LLM)."""
    client = get_supabase_client()
    client.table(EXPENSES_TABLE).update({"category": new_category}).eq("id", expense_id).execute()


def delete_expense(expense_id: str) -> None:
    """Menghapus satu transaksi."""
    client = get_supabase_client()
    client.table(EXPENSES_TABLE).delete().eq("id", expense_id).execute()


def get_monthly_summary(user_id: str, year: int, month: int) -> dict:
    """
    Mengambil ringkasan pengeluaran untuk satu bulan tertentu:
    total, breakdown per kategori, dan dataframe transaksinya.
    """
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    # end bersifat eksklusif -> mundurkan 1 hari supaya jadi akhir bulan
    end = end.fromordinal(end.toordinal() - 1)

    df = fetch_expenses(user_id, start_date=start, end_date=end)

    if df.empty:
        return {
            "total": 0.0,
            "by_category": pd.DataFrame(columns=["category", "amount"]),
            "transactions": df,
            "start": start,
            "end": end,
        }

    total = df["amount"].sum()
    by_category = (
        df.groupby("category", as_index=False)["amount"]
        .sum()
        .sort_values("amount", ascending=False)
    )

    return {
        "total": total,
        "by_category": by_category,
        "transactions": df,
        "start": start,
        "end": end,
    }
