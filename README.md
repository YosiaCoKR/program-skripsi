# Program Skripsi

## Definisi Proyek

Proyek ini adalah penelitian prediksi harga komoditas pangan di Provinsi DIY berbasis data time series harian. Fokus utama proyek ada pada pembersihan data, pemodelan prediksi harga jangka pendek, dan optimasi parameter model agar hasil prediksi lebih stabil dan akurat.

Komoditas yang dianalisis mencakup kelompok beras, bawang merah, dan cabai rawit dengan total 9 variabel harga.

## Tech Stack

- Python
- Jupyter Notebook
- Pandas dan NumPy untuk olah data
- Seaborn dan Matplotlib untuk visualisasi
- Scikit-learn untuk utilitas machine learning
- Statsmodels untuk analisis time series statistik
- LightGBM sebagai model regresi utama
- Genetic Algorithm (planned) untuk optimasi hyperparameter

## Ringkasan Data

| Item | Nilai |
| --- | --- |
| Nama file | DATASET-BERAS.csv |
| Jumlah baris | 2038 |
| Jumlah kolom | 10 |
| Rentang tanggal | 2021-01-04 sampai 2026-08-03 |
| Jumlah fitur komoditas | 9 |

Keterangan kolom komoditas:

- Beras Kualitas Bawah I
- Beras Kualitas Bawah II
- Beras Kualitas Medium I
- Beras Kualitas Medium II
- Beras Kualitas Super I
- Beras Kualitas Super II
- Bawang Merah Ukuran Sedang
- Cabai Rawit Hijau
- Cabai Rawit Merah

## Isi Workspace

- code.ipynb: proses eksplorasi data dan preprocessing
- DATASET-BERAS.csv: data harga harian
- workflow-program.md: rancangan alur metodologi penelitian
- README.md: dokumentasi proyek

## Cara Pakai Singkat

Install dependency:

```bash
pip install numpy pandas seaborn matplotlib scikit-learn statsmodels lightgbm
```

Lalu buka code.ipynb dan jalankan sel dari atas ke bawah.

## Catatan

Data dipakai untuk kebutuhan akademik skripsi. Penggunaan lanjutan tetap mengikuti ketentuan sumber data resmi.



