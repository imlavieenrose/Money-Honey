"""
Modul integrasi dengan Groq API.

Pola yang dipakai: LLM diberi dua "tools" (function calling) —
`record_expense` dan `get_monthly_report`. LLM memutuskan sendiri kapan
harus memanggil tool berdasarkan pesan pengguna, sesuai instruksi di
config.SYSTEM_PROMPT. Ini yang membuat aplikasi terasa seperti chatbot,
bukan form biasa.
"""

import json

import streamlit as st
from groq import Groq

from config import EXPENSE_CATEGORIES, GROQ_MODEL, SYSTEM_PROMPT
from database import get_monthly_summary, insert_expense
from utils import format_rupiah, month_name_id, today_str

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "record_expense",
            "description": (
                "Mencatat satu transaksi pengeluaran baru ke database. "
                "Panggil ini setiap kali pengguna menyebutkan sebuah pengeluaran dengan nominal jelas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Nominal pengeluaran dalam Rupiah, angka murni tanpa simbol. Contoh: 25000",
                    },
                    "category": {
                        "type": "string",
                        "enum": EXPENSE_CATEGORIES,
                        "description": "Kategori pengeluaran paling sesuai.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Deskripsi singkat, contoh: 'makan siang nasi goreng di warung'",
                    },
                    "expense_date": {
                        "type": "string",
                        "description": "Tanggal transaksi, format YYYY-MM-DD.",
                    },
                },
                "required": ["amount", "category", "description", "expense_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_monthly_report",
            "description": "Mengambil rekap/ringkasan pengeluaran untuk satu bulan tertentu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "Tahun, contoh 2026"},
                    "month": {"type": "integer", "description": "Bulan, angka 1-12"},
                },
                "required": ["year", "month"],
            },
        },
    },
]


def _get_client() -> Groq:
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


def _execute_record_expense(args: dict, user_id: str, raw_input: str) -> tuple[dict, dict]:
    row = insert_expense(
        user_id=user_id,
        amount=args["amount"],
        category=args["category"],
        description=args["description"],
        expense_date=args["expense_date"],
        raw_input=raw_input,
    )
    tool_result = {
        "status": "success",
        "amount": args["amount"],
        "category": args["category"],
        "description": args["description"],
        "expense_date": args["expense_date"],
    }
    ui_payload = {"type": "expense_recorded", "row": row}
    return tool_result, ui_payload


def _execute_get_monthly_report(args: dict, user_id: str) -> tuple[dict, dict]:
    year, month = int(args["year"]), int(args["month"])
    summary = get_monthly_summary(user_id, year, month)

    by_category_list = summary["by_category"].to_dict("records") if not summary["by_category"].empty else []
    tool_result = {
        "year": year,
        "month": month,
        "month_name": month_name_id(month),
        "total_spent": summary["total"],
        "transaction_count": int(len(summary["transactions"])),
        "by_category": by_category_list,
    }
    ui_payload = {"type": "report", "summary": summary, "year": year, "month": month}
    return tool_result, ui_payload


TOOL_EXECUTORS = {
    "record_expense": _execute_record_expense,
    "get_monthly_report": _execute_get_monthly_report,
}


def get_chatbot_response(user_message: str, user_id: str, chat_history: list[dict]) -> tuple[str, list[dict]]:
    """
    Mengirim pesan pengguna ke Groq, menjalankan tool bila LLM memintanya,
    lalu mengembalikan (teks_balasan_final, daftar_ui_payload_untuk_ditampilkan).

    chat_history: list of {"role": "user"/"assistant", "content": str} — riwayat
    percakapan sebelumnya (tanpa system prompt), dipakai supaya LLM ingat konteks.
    """
    client = _get_client()

    system_message = {
        "role": "system",
        "content": f"{SYSTEM_PROMPT}\n\nTanggal hari ini: {today_str()}.",
    }
    messages = [system_message] + chat_history + [{"role": "user", "content": user_message}]

    first_response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.2,
        max_tokens=1024,
    )
    reply_message = first_response.choices[0].message
    tool_calls = reply_message.tool_calls

    if not tool_calls:
        return reply_message.content or "Maaf, aku tidak paham maksudmu. Bisa diulang?", []

    # Jalankan setiap tool call yang diminta LLM
    messages.append(
        {
            "role": "assistant",
            "content": reply_message.content or "",
            "tool_calls": [tc.model_dump() for tc in tool_calls],
        }
    )

    ui_payloads = []
    for tc in tool_calls:
        fn_name = tc.function.name
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}

        executor = TOOL_EXECUTORS.get(fn_name)
        if executor is None:
            tool_result = {"status": "error", "message": f"Tool {fn_name} tidak dikenal."}
        else:
            try:
                if fn_name == "record_expense":
                    tool_result, ui_payload = executor(args, user_id, user_message)
                else:
                    tool_result, ui_payload = executor(args, user_id)
                ui_payloads.append(ui_payload)
            except Exception as e:
                tool_result = {"status": "error", "message": str(e)}

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "name": fn_name,
                "content": json.dumps(tool_result, default=str),
            }
        )

    # Panggilan kedua: minta LLM merangkai balasan natural berdasarkan hasil tool
    second_response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=512,
    )
    final_text = second_response.choices[0].message.content or "Tercatat!"
    return final_text, ui_payloads
