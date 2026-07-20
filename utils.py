"""Fungsi-fungsi kecil yang dipakai di beberapa tempat."""

from datetime import datetime
from zoneinfo import ZoneInfo

from config import APP_TIMEZONE

MONTH_NAMES_ID = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def format_rupiah(amount: float) -> str:
    """Format angka jadi string Rupiah, contoh: 25000 -> 'Rp25.000'."""
    return f"Rp{amount:,.0f}".replace(",", ".")


def now_local() -> datetime:
    """Waktu sekarang di timezone aplikasi (default Asia/Jakarta)."""
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def today_str() -> str:
    """Tanggal hari ini dalam format YYYY-MM-DD, dipakai sebagai acuan LLM."""
    return now_local().date().isoformat()


def month_name_id(month: int) -> str:
    return MONTH_NAMES_ID[month]
