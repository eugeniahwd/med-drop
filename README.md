# MedDrop

MedDrop merupakan mesin pengumpulan obat sisa atau kedaluwarsa secara mandiri (*self-service medicine collection machine*). Mesin ini dirancang untuk ditempatkan di apotek, klinik, kampus, atau area publik seperti lobi gedung, tanpa memerlukan petugas yang berjaga secara langsung.

Setiap obat yang disetorkan akan melalui proses verifikasi berdasarkan foto kemasan menggunakan *image classifier*, barcode, dan berat obat. Setoran yang memenuhi kriteria akan mendapatkan poin belanja apotek dengan nilai tertentu, disertai batas maksimal setoran harian untuk setiap anggota.

Proyek ini dikembangkan sebagai bagian dari studi kasus seleksi internship Kalbe (Case 1: Healthcare & Human Wellbeing).

**Status prototipe:** MedDrop dikembangkan menggunakan pendekatan **Software-in-the-Loop Simulation**. Komponen software, termasuk logika pengambilan keputusan, model Computer Vision (CV), backend, database, dan tampilan simulasi, telah diimplementasikan. Sementara itu, komponen fisik seperti kamera, load cell, pintu, dan sistem pengunci masih disimulasikan menggunakan input yang dapat dikendalikan melalui browser.

> **Disclaimer:** MedDrop merupakan prototipe simulasi yang dikembangkan untuk keperluan studi kasus. Sistem ini bukan alat medis maupun produk yang siap digunakan secara langsung. Seluruh data anggota, barcode, dan berat yang digunakan merupakan data dummy yang telah ditandai sebagai data simulasi, bukan data pengguna atau produk sebenarnya.

---

## Status Pengembangan

Berikut merupakan status setiap milestone pengembangan MedDrop.

| Milestone | Deskripsi | Status |
|---|---|---|
| M0 | Inisialisasi proyek, konfigurasi, dan endpoint `/api/config` | Selesai |
| M1 | Data layer: SQLite, seed database, dan pembuatan gambar barcode | Selesai |
| M2 | Decision engine, MockClassifier, dan unit test | Selesai |
| M3 | Implementasi API | Selesai |
| M4 | Simulasi mesin 3D dan tampilan kios | Selesai |
| M5 | Integrasi model asli (MobileNetV2) dan evaluasi | Selesai |
| M6 | Dashboard admin | Belum |
| M7 | Dokumentasi dan penyusunan laporan | Belum |

---

## Cara Menjalankan Aplikasi

### Persyaratan

- Python 3.12 (versi yang digunakan dalam pengujian).
- Semua perintah dijalankan dari direktori utama (*root directory*) proyek.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\seed_db.py
.\.venv\Scripts\python.exe -m backend.main
```

### macOS / Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/seed_db.py
.venv/bin/python -m backend.main
```

Setelah server berhasil dijalankan, buka alamat berikut melalui browser:

| Alamat | Fungsi |
|---|---|
| http://127.0.0.1:8000 | Halaman utama mesin dan kios (saat ini masih berupa halaman sementara) |
| http://127.0.0.1:8000/api/config | Melihat konfigurasi sistem yang sedang digunakan |
| http://127.0.0.1:8000/docs | Dokumentasi API interaktif |

### Menjalankan Test

Untuk menjalankan seluruh pengujian menggunakan `pytest`:

```bash
.venv/bin/python -m pytest
```

Khusus Windows:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

---

## Panduan Menggunakan Simulasi

Tampilan website saat ini menggunakan bahasa Inggris.

1. Pada layar kios di sebelah kiri, masukkan nomor member atau pilih salah satu akun demo yang tersedia. Perlu diperhatikan bahwa kuota setoran harian untuk member `MBR-0003` telah habis.
2. Setelah member dikenali, pintu depan mesin akan terbuka. Pilih obat yang ingin disetorkan melalui panel di sebelah kanan (*Choose a medicine*). Berat obat dapat disesuaikan menggunakan slider.
3. Klik tombol **Insert into machine** untuk memasukkan obat ke dalam mesin. Pintu akan tertutup dan terkunci, lampu indikator berubah menjadi kuning, kemudian sistem menjalankan proses pemeriksaan.
4. Jika obat memenuhi kriteria, *trap door* akan miring ke arah belakang sehingga obat masuk ke tempat penampungan (*bin*). Jika ditolak, obat akan diarahkan ke pintu pengembalian. Tekan **Take your item** untuk mengambil kembali barang.

### Panel Check Details

Panel **Check details** menampilkan informasi mengenai hasil pemeriksaan dan alasan keputusan sistem. Informasi yang ditampilkan meliputi:

- Aturan pemeriksaan yang berhasil atau gagal dipenuhi.
- Tingkat keyakinan (*confidence score*) hasil klasifikasi foto dibandingkan dengan batas minimum penerimaan.
- Hasil pembacaan dan validasi barcode.
- Posisi berat terukur terhadap batas minimum dan maksimum yang telah ditentukan.

Jika hasil pemeriksaan berbeda dari skenario yang diharapkan, sistem akan memberikan penanda agar perbedaannya lebih mudah dikenali.

### Fitur Visualisasi Mesin

Tombol **Show interior** digunakan untuk membuat panel mesin menjadi transparan sehingga bagian dalam mesin dapat dilihat.

Kontrol visualisasi:
- Seret (*drag*) untuk memutar tampilan mesin.
- Gulir (*scroll*) untuk memperbesar atau memperkecil tampilan.
- Arahkan kursor ke bagian tertentu untuk melihat nama komponennya.

Seluruh library yang digunakan, termasuk Three.js 0.170.0 dan font Atkinson Hyperlegible, disimpan secara lokal di direktori `frontend/vendor/`. Dengan demikian, aplikasi tidak bergantung pada CDN (*Content Delivery Network*).

---

## API Documentation

Dokumentasi API interaktif dapat diakses melalui:

http://127.0.0.1:8000/docs

Alamat tersebut dapat dibuka setelah server berjalan.

### Daftar Endpoint

| Endpoint | Fungsi |
|---|---|
| `GET /api/config` | Mengambil konfigurasi sistem, termasuk threshold, backend classifier aktif (`is_mock`), ID bin mesin, data member contoh, dan nama kelas model. |
| `GET /api/items` | Mengambil daftar item uji beserta URL foto dan gambar barcode. |
| `GET /api/members/{token}` | Mengambil informasi poin, jumlah setoran hari ini, dan sisa kuota member. Mengembalikan `404` jika member tidak ditemukan. |
| `GET /api/bins/{id}` | Mengambil informasi kapasitas bin dan status penerimaan setoran. |
| `POST /api/verify` | Menjalankan proses verifikasi setoran. Menerima data multipart berupa `member_token`, `bin_id`, `weight_g`, `photo`, `barcode_image?`, dan `barcode_text?`. |
| `GET /api/admin/transactions` | Mengambil riwayat transaksi dengan filter berdasarkan `decision` dan `reason_code`. |
| `GET /api/admin/stats` | Mengambil statistik setoran per produk, penolakan berdasarkan alasan, total poin, dan kapasitas bin. |
| `GET /api/admin/alerts` | Mengambil informasi peringatan, termasuk bin penuh dan indikasi pembongkaran paksa. |
| `POST /api/admin/bins/{id}/empty` | Mengosongkan bin sebagai simulasi proses pengambilan obat. |
| `POST /api/admin/bins/{id}/tamper` | Memicu peringatan pembongkaran paksa sebagai bagian dari simulasi. |

### Pencatatan Transaksi

Endpoint `/api/verify` mencatat setiap percobaan setoran sebagai transaksi, baik setoran yang diterima maupun yang ditolak.

Terdapat dua kondisi yang diperiksa sebelum pintu mesin dibuka:

- **Member tidak dikenal:** sistem mengembalikan status `404`.
- **Bin sudah mencapai kapasitas 100%:** sistem mengembalikan status `409`.

Kedua kondisi tersebut tidak menghasilkan transaksi karena pengguna belum memasukkan barang ke dalam mesin.

Foto dari setiap percobaan setoran disimpan di direktori `uploads/` untuk keperluan audit.

Perlu diketahui bahwa endpoint admin belum menggunakan autentikasi karena aplikasi ini masih berjalan dalam lingkungan simulasi lokal.

---

## Konfigurasi Sistem (`config.yaml`)

Parameter sistem dapat disesuaikan melalui file `config.yaml`.

| Parameter | Keterangan |
|---|---|
| `classifier.backend` | Menentukan backend classifier yang digunakan. `keras` menggunakan model asli (default), sedangkan `mock` menggunakan classifier pengganti untuk pengujian API. |
| `classifier.threshold_with_barcode` | Nilai minimum confidence hasil klasifikasi foto ketika barcode valid tersedia. |
| `classifier.threshold_photo_only` | Nilai minimum confidence ketika pemeriksaan hanya menggunakan foto tanpa barcode. Threshold ini dibuat lebih ketat. |
| `classifier.min_confidence_floor` | Batas minimum confidence. Jika nilainya berada di bawah batas ini, barang dianggap tidak teridentifikasi. |
| `weight.empty_margin_g` | Toleransi derau timbangan dalam satuan gram untuk menentukan batas kemasan kosong. |
| `weight.empty_margin_pct` | Toleransi variasi berat kemasan kosong dalam persentase dari nilai tare. |
| `weight.gross_tolerance_pct` | Toleransi persentase di atas berat bruto sebelum barang dinyatakan terlalu berat. |
| `points.per_valid_deposit` | Jumlah poin yang diberikan untuk setiap setoran yang diterima. |
| `points.daily_limit_deposits` | Jumlah maksimal setoran valid per member dalam satu hari. |
| `bin.capacity_g` | Kapasitas maksimum tempat penampungan dalam satuan gram. |
| `bin.alert_fill_pct` | Ambang persentase kepenuhan bin untuk memicu alert `BIN_FULL`. |

Server akan menolak proses startup apabila konfigurasi tidak valid. Salah satu contohnya adalah nilai threshold yang berada di luar rentang 0 sampai 1.

---

## Database dan Data Dummy

MedDrop menggunakan SQLite sebagai database lokal yang tersimpan di:

`data/meddrop.db`

Database akan diisi menggunakan script `scripts/seed_db.py`.

### Sumber Data

| Data | Sumber | Keterangan |
|---|---|---|
| Kelas model | `data/classes.json` | Terdiri dari lima produk obat, yaitu Entrostop, Fatigon, Kalpanax, Promag, dan Woods', serta dua kelas tambahan: `non_drug` dan `aerosol_inhaler`. |
| Produk | `data/products.seed.json` | Berisi ID produk `P-A` sampai `P-E`, termasuk informasi berat kemasan kosong (`tare_g`) dan berat bruto (`gross_g`). Barcode dan berat merupakan data dummy. Nilai berat masih berupa estimasi awal yang perlu diverifikasi melalui penimbangan aktual. |
| Member | `data/members.seed.json` | Berisi tiga member fiktif yang menggunakan token anonim. |
| Bin | `scripts/seed_db.py` | Menginisialisasi bin `BIN-001` dengan lokasi simulasi dan kapasitas yang ditentukan melalui `config.yaml`. |

### Data Demo dan Reset Database

Untuk mendemonstrasikan penolakan akibat kuota harian yang telah habis, member `MBR-0003` telah diberikan sejumlah transaksi contoh hingga mencapai batas setoran hariannya.

Data tersebut merupakan data demo dan dapat dikenali melalui kolom `photo_path` dan `photo_conf` yang bernilai kosong.

Perhitungan kuota menggunakan hari kalender berdasarkan zona waktu WIB. Oleh karena itu, jalankan kembali `seed_db.py` pada hari pelaksanaan demo agar data setoran contoh sesuai dengan tanggal saat itu.

Jika ingin menghapus seluruh transaksi dan mengembalikan database ke kondisi awal, jalankan:

```bash
python scripts/seed_db.py --reset
```

### Simulasi Barcode

Barcode pada kemasan disimulasikan menggunakan format barcode garis EAN-13, yaitu format yang umum ditemukan pada kemasan produk.

Seluruh kode yang digunakan merupakan kode dummy dengan digit awal `2`, contohnya:

`2000000000015`

Rentang awalan 20 sampai 29 dialokasikan oleh GS1 untuk penggunaan internal. Dengan demikian, kode simulasi ini tidak dimaksudkan sebagai identitas produk asli. Sebagai pembanding, produk yang beredar di Indonesia umumnya menggunakan awalan 899.

Gambar barcode untuk setiap produk disimpan di direktori `data/barcodes/`. Selain itu, tersedia barcode `2000000000992` yang secara format valid, tetapi tidak terdaftar di database. Barcode tersebut digunakan untuk menguji skenario penolakan.

Untuk membuat ulang seluruh gambar barcode, jalankan:

```bash
python scripts/make_barcode_images.py
```

Script ini juga melakukan pemeriksaan menggunakan OpenCV untuk memastikan setiap gambar barcode dapat dibaca kembali.

---

## Aturan Pemeriksaan Berat

Setiap produk memiliki dua parameter berat:

- **Tare weight:** berat kemasan produk dalam kondisi kosong.
- **Gross weight:** berat keseluruhan produk dalam kemasan saat masih utuh.

Mesin membandingkan berat hasil pengukuran dengan kedua parameter tersebut untuk mendeteksi kemungkinan kemasan kosong atau isi yang tidak sesuai.

| Berat Terukur | Keputusan |
|---|---|
| ≤ `tare + 0,5 g + (3% × tare)` | Ditolak dengan kode `WEIGHT_EMPTY`, karena kemasan terindikasi kosong atau isinya tidak lengkap. |
| Di antara batas kosong dan batas maksimum | Lolos pemeriksaan berat. |
| > `gross × 1,05` | Ditolak dengan kode `WEIGHT_OVER`, karena berat melebihi batas toleransi yang ditentukan. |

Margin untuk mendeteksi kemasan kosong tidak dibuat terlalu kecil karena pengukuran menggunakan load cell dapat dipengaruhi oleh derau (*measurement noise*), yang secara umum dapat berada pada kisaran ±0,2 sampai 0,5 gram. Selain itu, berat kemasan kosong juga dapat sedikit berbeda antarproduksi.

Jika margin terlalu kecil, kemasan kosong yang memiliki berat sedikit lebih besar dari nilai referensi berpotensi dianggap masih berisi obat.

Kemasan obat yang hanya berupa strip tanpa dus juga berpotensi memiliki berat di bawah nilai tare yang ditentukan. Dalam kondisi tersebut, sistem akan menolaknya dan meminta pengguna menyetorkan obat bersama kemasan jualnya.

Perlu diperhatikan bahwa seluruh nilai toleransi ini merupakan parameter awal untuk simulasi dan belum divalidasi melalui pengujian timbangan fisik.

---

## Model Computer Vision

Sistem klasifikasi foto menggunakan **MobileNetV2** dengan bobot awal dari ImageNet dan lapisan klasifikasi tambahan untuk mengenali tujuh kelas.

Pada tahap awal pelatihan, base model dibekukan (*frozen*). Selanjutnya, 20 lapisan terakhir dilatih kembali melalui proses *fine-tuning* untuk menyesuaikan model dengan dataset MedDrop.

Model hasil pelatihan disimpan di direktori `model/` dan sudah disertakan dalam repository. Oleh karena itu, model tidak perlu dilatih ulang untuk menjalankan demo.

### Melatih dan Mengevaluasi Model

Untuk melatih ulang model menggunakan fine-tuning:

```bash
.venv/bin/python scripts/train.py --fine-tune
```

Proses pelatihan membutuhkan waktu sekitar satu menit menggunakan CPU.

Untuk menjalankan evaluasi:

```bash
.venv/bin/python scripts/evaluate.py
```

Hasil evaluasi akan disimpan di direktori `docs/eval/`.

### Hasil Evaluasi Model

Evaluasi dilakukan menggunakan test split yang terdiri dari 22 foto. Detail hasil pengujian dapat dilihat pada `docs/eval/report.md` dan `docs/eval/confusion_matrix.png`.

| Metrik | Hasil |
|---|---|
| Akurasi klasifikasi tujuh kelas | 93% (13 dari 14) |
| False Accept Rate (barang yang seharusnya ditolak tetapi justru diterima), hanya menggunakan foto | 0% dari 12 pengujian |
| False Accept Rate, dengan barcode produk yang sesuai | 0% dari 12 pengujian |
| Produk asli yang ditolak meskipun barcode dan berat sesuai | 0% dari 10 pengujian |

### Catatan Hasil Pengujian

Model masih memiliki keterbatasan dalam mengenali produk yang tidak termasuk dalam dataset. Sebagai contoh, obat merek lain seperti Jardiance dapat diklasifikasikan sebagai salah satu kelas yang dikenal, misalnya Kalpanax.

Namun, tingkat confidence hasil klasifikasi tersebut masih berada di bawah threshold penerimaan sehingga sistem akan menolak setoran.

Contoh lainnya dapat dilihat pada kartu simulasi **Fatigon, no barcode**. Setoran tersebut tetap ditolak karena confidence sebesar 75% belum memenuhi threshold minimum untuk pemeriksaan berbasis foto saja, yaitu 85%.

Kegagalan klasifikasi seperti ini tetap ditampilkan dalam simulasi agar keterbatasan model dapat diamati secara langsung, bukan disembunyikan.

### Menguji Foto Sendiri

Panel sebelah kanan menyediakan pilihan **Your own photo** untuk menguji gambar di luar kartu item yang telah disediakan.

Langkah pengujian:

1. Unggah foto atau ambil gambar menggunakan kamera HP.
2. Pilih barcode yang tertera pada kemasan, atau lanjutkan tanpa barcode.
3. Atur berat barang menggunakan slider.
4. Masukkan barang ke mesin melalui simulasi seperti pada kartu item lainnya.

---

## Dataset Foto

Foto yang digunakan untuk pelatihan model disimpan di direktori:

`dataset/raw/<class_id>/`

Nama folder harus sesuai dengan `class_id` yang telah didefinisikan.

Foto untuk lima produk obat dikumpulkan oleh pemilik proyek. Sementara itu, foto untuk kelas bukan obat (`non_drug`), aerosol/inhaler, dan obat dari merek lain (`out_of_dataset`) diperoleh dari Wikimedia Commons dengan lisensi terbuka.

Informasi mengenai sumber gambar, pembuat, dan lisensi dapat ditemukan di:

`dataset/raw/SOURCES.md`

Folder `train/`, `val/`, dan `test/` dibuat secara otomatis menggunakan script. Oleh karena itu, folder tersebut tidak perlu diisi secara manual.

Setelah menambahkan atau menghapus foto di folder `raw/`, jalankan:

```bash
.venv/bin/python scripts/split_dataset.py
```

Khusus Windows:

```powershell
.\.venv\Scripts\python.exe scripts\split_dataset.py
```

### Pembagian Dataset

| Dataset Split | Fungsi |
|---|---|
| `train` | Foto yang digunakan model untuk mempelajari pola dan karakteristik setiap kelas. |
| `val` | Digunakan selama proses pelatihan untuk memantau performa model dan membantu menentukan pengaturan pelatihan. |
| `test` | Disimpan untuk evaluasi akhir model dan juga digunakan sebagai sumber foto kartu item pada website. |

Script membagi foto setiap kelas dengan rasio sekitar 60:20:20 menggunakan seed tetap. Dengan demikian, hasil pembagian dataset akan konsisten setiap kali script dijalankan.

Informasi pembagian dataset disimpan di:

`dataset/split.json`

Kelas `out_of_dataset` (kemasan obat di luar lima produk yang dikenali) hanya dimasukkan ke dalam `test`.

Gunakan format JPG atau PNG dan pastikan tidak ada foto duplikat.

**Catatan:** Jika script dijalankan ulang setelah model dilatih, isi dataset `test` dapat berubah. Oleh karena itu, model perlu dilatih dan dievaluasi kembali agar hasil pengujian tetap sesuai dengan dataset terbaru.

### Foto dengan Kondisi Terdegradasi

Untuk menguji ketahanan model terhadap kualitas foto yang kurang baik, disediakan variasi foto buram dan gelap yang dibuat dari foto pertama setiap produk pada test split.

Variasi tersebut terdiri dari tiga tingkat keburaman dan tiga tingkat pencahayaan, kemudian disimpan di:

`dataset/test_degraded/`

Jalankan script berikut setelah `split_dataset.py`:

```bash
.venv/bin/python scripts/make_degraded_samples.py
```

Khusus Windows:

```powershell
.\.venv\Scripts\python.exe scripts\make_degraded_samples.py
```

### MockClassifier

Jika parameter `classifier.backend` diubah menjadi `mock`, sistem akan menggunakan MockClassifier. Mode ini digunakan dalam pengujian API.

MockClassifier mengenali foto berdasarkan folder asalnya di `dataset/test/`, bukan berdasarkan isi gambar. Nilai confidence yang dihasilkan bersifat simulasi.

Untuk foto yang berada di `test_degraded/`, nilai confidence akan dikurangi sesuai tingkat degradasi yang tercantum pada nama file, yaitu ringan, sedang, atau berat.

Foto yang tidak dikenali oleh MockClassifier akan selalu ditolak.

**MockClassifier bukan model Computer Vision yang sebenarnya.** Komponen ini merupakan pengganti sementara untuk kebutuhan pengujian API dan telah digantikan oleh model MobileNetV2 pada milestone M5.

---

## Struktur Direktori

Berikut merupakan gambaran struktur folder utama proyek MedDrop.

```text
backend/    FastAPI: route, decision engine, classifier, dan akses database
data/       Definisi kelas, seed produk dan member, serta kartu item uji
dataset/    Foto asli di raw/<class_id>/ dan hasil pembagian train/val/test
model/      Model hasil pelatihan dan labels.json
scripts/    Script untuk seed database, membuat barcode, membuat sampel terdegradasi,
            melatih model, dan menjalankan evaluasi
frontend/   Simulasi mesin 3D, tampilan kios (index.html), dan dashboard admin (admin.html)
tests/      Pengujian decision engine dan API
docs/       Diagram, hasil evaluasi, dan dokumentasi tangkapan layar
```

---

## Batasan Prototipe

MedDrop masih berada pada tahap prototipe simulasi. Beberapa batasan yang perlu diperhatikan sebelum sistem dikembangkan lebih lanjut adalah sebagai berikut.

1. **Belum menggunakan perangkat fisik secara terintegrasi.** Prototipe belum diuji menggunakan sensor, kamera, maupun mekanisme pintu secara fisik. Dengan demikian, akurasi load cell, pengaruh getaran, serta kondisi pencahayaan nyata belum dapat dievaluasi.

2. **Cakupan produk masih terbatas.** Model hanya dilatih menggunakan dataset yang tersedia. Sistem belum dapat membaca tanggal kedaluwarsa produk. Obat lepas tanpa kemasan juga belum dapat diterima.

3. **Pemeriksaan berat memiliki asumsi tertentu.** Deteksi kemasan kosong berdasarkan berat mengasumsikan bahwa obat disetorkan menggunakan kemasan jual utuh. Karena berat kemasan kosong dapat berbeda antarproduksi, obat dengan sisa isi yang sangat sedikit berpotensi ikut ditolak.

4. **Jumlah dataset masih terbatas.** Dataset hanya memiliki sekitar 10 foto untuk setiap produk, sehingga test split hanya terdiri dari sekitar dua foto per produk. Oleh karena itu, angka akurasi yang diperoleh masih bersifat indikatif dan belum cukup untuk menggambarkan performa model dalam penggunaan nyata.

5. **Model hanya mengenali tujuh kelas.** Barang di luar kelas tersebut, seperti obat merek lain atau kaleng minuman, tetap dapat diklasifikasikan sebagai salah satu kelas yang dikenal. Keamanan proses penerimaan bergantung pada threshold confidence yang diterapkan dalam decision engine. Sebagai contoh, foto kaleng minuman pernah diklasifikasikan sebagai aerosol.

6. **Sumber foto memiliki karakteristik berbeda.** Foto bukan obat, aerosol, dan obat dari merek lain diperoleh dari Wikimedia Commons. Gaya pengambilan gambar dan latar belakangnya berbeda dari foto produk yang dikumpulkan untuk dataset utama maupun kondisi kamera di dalam mesin. Hasil pengujian saat ini belum sepenuhnya mewakili kondisi operasional mesin sebenarnya.

7. **Skenario barcode tanpa obat belum diuji.** Contohnya adalah kondisi ketika pengguna hanya memasukkan potongan kemasan yang memiliki barcode tanpa menyertakan obat. Skenario ini belum diuji karena dataset belum memiliki foto yang sesuai.

8. **Barcode masih menggunakan data dummy.** Barcode yang digunakan merupakan EAN-13 dengan awalan 2, bukan kode produk asli. Sistem juga belum dapat membaca 2D barcode BPOM (DataMatrix) yang dapat memuat informasi batch dan tanggal kedaluwarsa. Integrasi dengan master data produsen serta pembacaan informasi tersebut menjadi bagian dari pengembangan selanjutnya.

9. **Implementasi nyata membutuhkan pengelolaan limbah yang sesuai regulasi.** Penerapan MedDrop memerlukan kerja sama dengan vendor pengelola limbah B3 yang memiliki izin, penentuan kategori obat dan barang yang boleh diterima, serta persetujuan dari regulator terkait. Kategori tertentu, seperti narkotika, psikotropika, dan benda tajam, perlu dikecualikan dari sistem penerimaan.

10. **Perlindungan data pribadi perlu diperhatikan.** Sistem simulasi menggunakan token anonim untuk mengidentifikasi member. Namun, apabila sistem dikembangkan dan digunakan secara nyata, aspek privasi dan kepatuhan terhadap UU Pelindungan Data Pribadi (UU PDP) perlu menjadi pertimbangan dalam pengelolaan data pengguna.

---

**MedDrop — Healthcare & Human Wellbeing Case Study**  
*Prototype for Kalbe Advanced Engineering Internship Selection*
