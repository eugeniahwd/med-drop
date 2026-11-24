-- Tabel MedDrop di Supabase untuk data dari ESP32.
-- Cara pakai: buka project Supabase > SQL Editor > New query, tempel isi file ini, lalu Run.

-- Status perangkat: satu baris per mesin, last_seen diperbarui setiap heartbeat.
create table if not exists devices (
  device_id  text primary key,
  last_seen  timestamptz not null default now(),
  rssi       int,
  uptime_s   int,
  firmware   text,
  ip         text
);

-- Setiap setoran dari ESP32, diterima maupun ditolak.
create table if not exists device_transactions (
  id             bigint generated always as identity primary key,
  created_at     timestamptz not null default now(),
  device_id      text not null,
  member_token   text,
  barcode        text,
  weight_g       real,
  photo_class    text,
  photo_conf     real,
  decision       text,
  reason_code    text,
  points_awarded int
);

-- RLS aktif tanpa policy: kunci publik (anon) tidak bisa membaca atau menulis.
-- Server memakai secret key, yang memang melewati RLS.
alter table devices enable row level security;
alter table device_transactions enable row level security;
