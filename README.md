# Prediksi Pangan Jogja

Aplikasi skripsi untuk memantau dan memprediksi harga komoditas pangan di Provinsi DIY. Proyek ini masih dalam tahap prototipe aplikasi berbasis Streamlit, dengan fokus pada antarmuka publik, visualisasi data, dan simulasi prediksi harga untuk 9 komoditas utama.

## Ringkasan proyek

- Dashboard publik untuk melihat harga terkini 9 komoditas pangan
- Halaman detail komoditas dengan grafik historis dan prediksi 1/7/30 hari
- Halaman data historis dengan rentang 30/60/90 hari
- Panel admin untuk login, input harga terbaru, dan pengaturan model aktif
- Folder riset berisi notebook, dataset, dan artefak analisis model

## Struktur repository

```text
program-skripsi/
├── README.md                     # dokumentasi proyek
├── WORKFLOW-PROGRAM.md          # dokumentasi alur penelitian dan workflow skripsi
├── webapp/
│   ├── research/
│   │   ├── code.ipynb           # eksplorasi data dan pemodelan
│   │   ├── code_backup.ipynb    # backup notebook
│   │   ├── DATASET-BERAS.csv    # data harga harian komoditas
│   │   └── models/              # artefak model hasil riset
│   └── streamlit_app/
│       ├── app.py               # entry point aplikasi
│       ├── auth.py              # login admin dan proteksi akses
│       ├── config.py            # konfigurasi model aktif
│       ├── db.py                # log aktivitas admin (SQLite)
│       ├── formatting.py        # formatter data tampilan
│       ├── charting.py          # plotting grafik harga
│       ├── requirements.txt     # dependency Python
│       ├── assets/
│       │   └── styles.css       # styling UI
│       ├── data/
│       │   ├── mock_commodities.py
│       │   ├── mock_models.py
│       │   └── mock_prices.py
│       └── views/
│           ├── dashboard.py
│           ├── historis.py
│           ├── detail_komoditas.py
│           ├── admin_login.py
│           ├── admin_input_harga.py
│           └── admin_model_settings.py
└── .venv/                        # environment virtual Python lokal
```

## Teknologi yang digunakan

- Python 3
- Streamlit
- Pandas
- Plotly
- SQLite
- python-dotenv
- Notebook Jupyter untuk riset dan analisis data

## Persyaratan

Pastikan Python sudah terpasang. Lalu install dependency:

```bash
cd webapp/streamlit_app
python -m pip install -r requirements.txt
```

## Menjalankan aplikasi

```bash
cd webapp/streamlit_app
streamlit run app.py
```

Setelah itu buka URL yang ditampilkan oleh Streamlit, biasanya:

```text
http://localhost:8501
```

## Kredensial admin default untuk pengembangan

Nilai default yang dipakai saat ini pada kode adalah:

- Username: `admin`
- Password: `admin123`

Nilai ini dibaca dari variabel environment `ADMIN_USERNAME` dan `ADMIN_PASSWORD`. Untuk lingkungan produksi, sebaiknya diubah agar tidak memakai nilai default demo.

## Fitur utama aplikasi

### Publik

- Dashboard harga 9 komoditas pangan
- Kategori beras dan bumbu dapur
- Detail tiap komoditas
- Grafik historis 30/60/90 hari
- Prediksi simulasi 1/7/30 hari

### Admin

- Login ke panel admin
- Input harga terbaru satu komoditas
- Pilih model aktif yang digunakan pada simulasi prediksi
- Log aktivitas login/logout disimpan ke SQLite

## Data riset dan penelitian

Folder `webapp/research/` berisi proses analisis data dan model, termasuk:

- notebook eksperimen prediksi harga
- dataset harian komoditas
- artefak model hasil riset

Saat ini, aplikasi utama masih memakai data tiruan (`mock_*`) sebagai placeholder untuk antarmuka dan alur produk. Integrasi dengan model hasil riset yang sesungguhnya masih menjadi tahap lanjutan.

## Catatan penting

Proyek ini merupakan prototipe yang fokus pada pengalaman pengguna dan alur aplikasi. Struktur kode sudah disusun agar nanti mudah dipindahkan ke integrasi model nyata, database produksi, dan API backend apabila project berkembang ke tahap berikutnya.
