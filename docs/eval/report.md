# Hasil evaluasi model

Split test: 22 foto. Dataset kecil, jadi angka ini kasar dan bersifat indikatif.

| Metrik | Nilai |
|---|---|
| Akurasi klasifikasi (7 kelas) | 93% |
| False Accept Rate, hanya foto | 0% dari 12 barang |
| False Accept Rate, dengan barcode yang cocok | 0% dari 12 barang |
| Produk asli yang ditolak (barcode dan berat benar) | 0% dari 10 foto |

False Accept Rate dihitung untuk foto bukan obat, aerosol/inhaler, dan obat di luar dataset, dengan asumsi terburuk bahwa berat barang cocok dengan produk yang ditebak foto.

## Per kelas

| Kelas | Precision | Recall | Foto test |
|---|---|---|---|
| entrostop | 1.0 | 1.0 | 2 |
| fatigon | 1.0 | 1.0 | 2 |
| kalpanax | 0.67 | 1.0 | 2 |
| promag | 1.0 | 1.0 | 2 |
| woods | 1.0 | 1.0 | 2 |
| non_drug | 1.0 | 0.5 | 2 |
| aerosol_inhaler | 1.0 | 1.0 | 2 |

## Semua prediksi

| Foto | Sebenarnya | Prediksi | Keyakinan |
|---|---|---|---|
| aerosol_inhaler/aerosol-03.jpg | aerosol_inhaler | aerosol_inhaler | 90% |
| aerosol_inhaler/hairspray-03.jpg | aerosol_inhaler | aerosol_inhaler | 85% |
| entrostop/entrostop-1.jpg | entrostop | entrostop | 66% |
| entrostop/entrostop-9.jpg | entrostop | entrostop | 98% |
| fatigon/fatigon-5.jpg | fatigon | fatigon | 75% |
| fatigon/fatigon-8.jpg | fatigon | fatigon | 93% |
| kalpanax/kalpanax-10.jpg | kalpanax | kalpanax | 88% |
| kalpanax/kalpanax-8.jpg | kalpanax | kalpanax | 97% |
| non_drug/botol-02.jpg | non_drug | non_drug | 94% |
| non_drug/pulpen-01.jpg | non_drug | kalpanax (salah) | 38% |
| out_of_dataset/aspirin-01.jpg | out_of_dataset | aerosol_inhaler | 74% |
| out_of_dataset/aspirin-02.jpg | out_of_dataset | kalpanax | 52% |
| out_of_dataset/bayer-01.jpg | out_of_dataset | aerosol_inhaler | 30% |
| out_of_dataset/blister-01.jpg | out_of_dataset | non_drug | 63% |
| out_of_dataset/doreta-01.jpg | out_of_dataset | non_drug | 26% |
| out_of_dataset/jardiance-01.jpg | out_of_dataset | kalpanax | 51% |
| out_of_dataset/palgotal-01.jpg | out_of_dataset | fatigon | 50% |
| out_of_dataset/zaldiar-01.jpg | out_of_dataset | promag | 27% |
| promag/promag-1.jpg | promag | promag | 73% |
| promag/promag-4.jpg | promag | promag | 95% |
| woods/woods-3.jpg | woods | woods | 75% |
| woods/woods-8.jpg | woods | woods | 91% |
