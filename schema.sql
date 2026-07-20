-- Jalankan seluruh script ini sekali di Supabase Dashboard -> SQL Editor -> New query

-- Ekstensi untuk generate UUID
create extension if not exists "pgcrypto";

-- Tabel utama expenses
create table if not exists public.expenses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    amount numeric(14, 2) not null check (amount > 0),
    category text not null,
    description text,
    expense_date date not null default current_date,
    raw_input text,
    created_at timestamptz not null default now()
);

create index if not exists expenses_user_id_idx on public.expenses (user_id);
create index if not exists expenses_date_idx on public.expenses (expense_date);

-- Aktifkan Row Level Security supaya user hanya bisa akses data miliknya sendiri
alter table public.expenses enable row level security;

drop policy if exists "Users can view own expenses" on public.expenses;
create policy "Users can view own expenses"
    on public.expenses for select
    using (auth.uid() = user_id);

drop policy if exists "Users can insert own expenses" on public.expenses;
create policy "Users can insert own expenses"
    on public.expenses for insert
    with check (auth.uid() = user_id);

drop policy if exists "Users can update own expenses" on public.expenses;
create policy "Users can update own expenses"
    on public.expenses for update
    using (auth.uid() = user_id);

drop policy if exists "Users can delete own expenses" on public.expenses;
create policy "Users can delete own expenses"
    on public.expenses for delete
    using (auth.uid() = user_id);
