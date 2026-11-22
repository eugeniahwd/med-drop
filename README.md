# MedDrop

Kotak setor mandiri untuk obat sisa/kedaluwarsa, ditempatkan di apotek, klinik, kampus, atau lobi tanpa petugas yang berjaga. Setiap setoran diverifikasi dengan foto (classifier), QR kemasan, dan berat. Setoran yang valid mendapat poin belanja apotek bernilai kecil, dengan batas harian.

Proyek ini adalah studi kasus seleksi internship Kalbe (Case 1: Healthcare & Human Wellbeing). Prototipenya berupa **simulasi software-in-the-loop**: logika keputusan, model CV, backend, database, dan dashboard berjalan sungguhan, sedangkan sensor dan aktuator (kamera, load cell, pintu, kunci) disimulasikan lewat input terkontrol di browser.

> **Disclaimer.** MedDrop adalah prototipe simulasi untuk keperluan studi kasus. Ini **bukan alat medis dan bukan produk jadi**. Semua nama produk, anggota, payload QR, dan berat adalah data dummy berlabel jelas, bukan data nyata.

## Status milestone

| Milestone | Isi | Status |
|---|---|---|
| M0 | Scaffold, konfigurasi, `/api/config` | selesai |
| M1 | Data layer (SQLite, seed, gambar QR) | belum |
| M2 | Engine keputusan, MockClassifier, tes | belum |
| M3 | API lengkap | belum |
| M4 | Web 3D + layar kios | belum |
| M5 | Model asli (MobileNetV2) + evaluasi | belum |
| M6 | Dashboard admin | belum |
| M7 | Dokumentasi dan bahan laporan | belum |

## Cara menjalankan

Butuh Python 3.12 (versi yang diuji). Semua perintah dijalankan dari root proyek.

**Windows (PowerShell)**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m backend.main
```

**macOS / Linux**

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m backend.main
```

Lalu buka:

- http://127.0.0.1:8000 (halaman mesin dan kios; saat ini masih halaman sementara)
- http://127.0.0.1:8000/api/config (konfigurasi aktif)
- http://127.0.0.1:8000/docs (dokumentasi API otomatis)

Menjalankan tes:

```bash
.venv/bin/python -m pytest          # Windows: .\.venv\Scripts\python.exe -m pytest
```

## Konfigurasi (`config.yaml`)

| Kunci | Arti |
|---|---|
| `classifier.backend` | `mock` (sementara, bukan model sungguhan, UI menampilkan banner) atau `keras` (model asli) |
| `classifier.threshold_with_qr` | keyakinan foto minimum bila ada QR valid |
| `classifier.threshold_photo_only` | keyakinan foto minimum bila tanpa QR (lebih ketat) |
| `classifier.min_confidence_floor` | di bawah nilai ini barang dianggap tidak teridentifikasi |
| `weight.tolerance_pct` | toleransi (%) di luar kisaran berat produk |
| `points.per_valid_deposit` | poin per setoran yang diterima |
| `points.daily_limit_deposits` | maksimum setoran valid per anggota per hari |
| `bin.capacity_g` | kapasitas tempat penampungan (gram) |
| `bin.alert_fill_pct` | ambang kepenuhan (%) untuk alert `BIN_FULL` |

Server menolak start bila konfigurasi tidak valid (misalnya threshold di luar 0..1).

## Dataset foto

Foto asli disimpan di `dataset/raw/<class_id>/`, dan nama folder harus sama dengan `class_id`. Folder `train/`, `val/`, dan `test/` dibuat oleh skrip, jadi jangan diisi manual. Setelah menambah atau menghapus foto di `raw/`, jalankan:

```bash
.venv/bin/python scripts/split_dataset.py      # Windows: .\.venv\Scripts\python.exe scripts\split_dataset.py
```

| Split | Fungsi |
|---|---|
| `train` | foto yang dipelajari model |
| `val` | dipakai selama pelatihan untuk memantau kemajuan dan memilih pengaturan |
| `test` | disimpan sampai akhir untuk evaluasi, sekaligus sumber foto kartu item di web |

Skrip membagi foto per kelas dengan rasio sekitar 60/20/20 dan seed tetap, sehingga hasilnya selalu sama. Pembagiannya dicatat di `dataset/split.json`. Kelas `out_of_dataset` (kemasan obat di luar lima produk) hanya masuk ke `test`. Skrip menolak berjalan bila menemukan foto kembar, foto yang tidak terbaca, atau format selain JPG/PNG. Kalau skrip dijalankan ulang setelah model dilatih, isi `test` bisa berubah, jadi model perlu dilatih dan dievaluasi ulang.

## Struktur folder

```
backend/    FastAPI: route, engine keputusan, classifier, akses DB
data/       definisi kelas, seed produk/anggota, kartu item uji
dataset/    foto asli di raw/<class_id>/, dibagi skrip ke train/val/test
model/      hasil pelatihan model + labels.json
scripts/    seed DB, pembuatan gambar QR, sampel terdegradasi, train, evaluate
frontend/   mesin 3D + kios (index.html) dan dashboard admin (admin.html)
tests/      tes engine keputusan dan API
docs/       diagram, hasil evaluasi, tangkapan layar
```

## Batasan

- Prototipe tidak diuji dengan sensor, kamera, atau mekanik fisik. Akurasi load cell, getaran, dan pencahayaan nyata belum teruji.
- Cakupan produk terbatas pada dataset. Tanggal kedaluwarsa tidak dibaca. Obat lepas tanpa kemasan ditolak.
- Dataset kecil (sekitar 10 foto per produk, sehingga test hanya 2 foto per produk). Angka akurasi bersifat indikatif dan kasar.
- QR bersifat dummy (format `MDP|<product_id>|v1`) dan bukan 2D barcode BPOM. Integrasi master data produsen adalah pekerjaan lanjutan.
- Penerapan nyata membutuhkan vendor pengelola limbah B3 berizin, pengaturan kategori yang boleh diterima (misalnya narkotika/psikotropika dan benda tajam ditolak), dan persetujuan regulator.
- Privasi: anggota memakai token anonim. UU PDP perlu dipertimbangkan bila data dipakai untuk riset.
