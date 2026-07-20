# 💸 Duitin — Expense Tracker Berbasis Chatbot

Aplikasi Streamlit untuk mencatat, mengelompokkan, dan membuat laporan bulanan
pengeluaran — cukup lewat obrolan santai. Ekstraksi nominal & kategori otomatis
memakai LLM (Groq), penyimpanan data & autentikasi memakai Supabase.

## Fitur

- 🔐 Login / sign up (Supabase Auth, email + password)
- 💬 Catat pengeluaran lewat chat, contoh: *"beli kopi 25rb tadi pagi"*
- 🏷️ Kategorisasi otomatis oleh LLM (bisa dikoreksi manual di tab Riwayat)
- 📊 Laporan bulanan: total, breakdown per kategori (pie & bar chart), bisa
  diminta langsung lewat chat ("rekap bulan ini") atau lihat di tab terpisah
- ✏️ Edit kategori & hapus transaksi lewat tabel interaktif
- ⬇️ Export CSV per bulan

## Struktur Proyek

```
expense-tracker/
├── app.py                          # Entry point Streamlit
├── auth.py                         # Login / sign up
├── database.py                     # CRUD ke Supabase
├── llm.py                          # Orkestrasi chatbot (Groq tool calling)
├── config.py                       # Kategori, model, system prompt
├── utils.py                        # Helper format Rupiah & tanggal
├── schema.sql                      # SQL untuk setup tabel di Supabase
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example        # Contoh kredensial (copy -> secrets.toml)
```

## 1. Setup Supabase

1. Buat project baru di [supabase.com](https://supabase.com).
2. Buka **SQL Editor**, jalankan seluruh isi file `schema.sql` di repo ini.
   Ini akan membuat tabel `expenses` beserta Row Level Security (RLS) supaya
   tiap user hanya bisa melihat/mengubah datanya sendiri.
3. Buka **Authentication -> Providers**, pastikan **Email** provider aktif.
4. (Opsional, biar testing lebih cepat) Di **Authentication -> Settings**,
   matikan "Confirm email" kalau tidak mau proses verifikasi email dulu saat
   sign up. Untuk production, sebaiknya biarkan aktif.
5. Ambil kredensial di **Project Settings -> API**:
   - `Project URL` -> jadi `SUPABASE_URL`
   - `anon public` key -> jadi `SUPABASE_ANON_KEY`

## 2. Setup Groq API

1. Buat API key di [console.groq.com](https://console.groq.com).
2. Simpan sebagai `GROQ_API_KEY`.
3. Model default di `config.py` adalah `llama-3.3-70b-versatile` (mendukung
   tool calling & JSON mode). Kalau mau lebih hemat/cepat, ganti ke model
   lain yang mendukung tool use — cek daftar terbaru di
   [console.groq.com/docs/models](https://console.groq.com/docs/models).

## 3. Menjalankan secara lokal

```bash
git clone <repo-kamu>
cd expense-tracker
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# lalu edit .streamlit/secrets.toml, isi 3 kredensial di atas

streamlit run app.py
```

## 4. Deploy ke GitHub + Streamlit Community Cloud

1. Push seluruh folder ini ke repository GitHub (file `secrets.toml` asli
   TIDAK akan ikut ter-commit karena sudah ada di `.gitignore` — memang harus
   begitu, jangan commit kredensial).
2. Buka [share.streamlit.io](https://share.streamlit.io), pilih **New app**,
   arahkan ke repo & file `app.py`.
3. Sebelum/ setelah deploy, buka **App settings -> Secrets**, isi dengan
   format TOML yang sama seperti `secrets.toml.example`:

   ```toml
   SUPABASE_URL = "https://xxxxxxxxxxxx.supabase.co"
   SUPABASE_ANON_KEY = "..."
   GROQ_API_KEY = "..."
   ```
4. Deploy. Aplikasi siap dipakai.

## Catatan Desain & Keterbatasan

- **Sesi login**: status login disimpan di `st.session_state`, jadi berlaku
  selama tab browser terbuka. Kalau tab di-refresh atau ditutup, user perlu
  login ulang. Untuk sesi yang bertahan lebih lama (mis. lewat cookie
  browser), bisa ditambahkan library seperti `streamlit-cookies-controller`
  sebagai pengembangan lanjutan.
- **Keamanan multi-user**: client Supabase sengaja disimpan per sesi
  (`st.session_state`), bukan di-cache global, supaya token login satu
  pengguna tidak pernah tercampur dengan pengguna lain saat aplikasi diakses
  banyak orang sekaligus.
- **Kategori**: daftar kategori didefinisikan di `config.py`
  (`EXPENSE_CATEGORIES`). Ubah sesuai kebutuhan — LLM otomatis mengikuti
  daftar yang ada di sana.
- **Biaya API**: setiap pesan chat memicu 1-2 panggilan ke Groq API. Groq
  punya free tier dengan rate limit; cek dashboard Groq kalau butuh kuota
  lebih besar.
