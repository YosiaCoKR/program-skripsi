# Program Skripsi

Monorepo penelitian dan aplikasi PANGANIA untuk prediksi harga komoditas
pangan di Provinsi DIY. Penelitian menggunakan data time series harian untuk
beras, bawang merah, dan cabai rawit dengan total sembilan komoditas.

## Struktur

```text
program-skripsi/
├── webapp/
│   ├── research/              # notebook, dataset, dan artefak model
│   ├── backend/               # FastAPI + SQLAlchemy + SQLite
│   └── frontend/              # React 18 + TypeScript + Vite
├── package.json               # workspace dan command dari root
├── PRD.md                     # kebutuhan produk
└── workflow-program.md        # alur penelitian
```

## Menjalankan

Install dependency frontend dari root:

```bash
npm install
npm run frontend:typecheck
npm run frontend:build
```

Jalankan backend dan frontend di dua terminal:

```bash
python -m pip install -r webapp/backend/requirements.txt
npm run backend:dev
```

```bash
npm run frontend:dev
```

Buka `http://127.0.0.1:5173`. Dokumentasi API tersedia di


Untuk mengisi database pertama kali:

```bash
cd webapp/backend
../../.venv/Scripts/python.exe -m pangania.seed --reset
```

## Penelitian

Semua kode dan resource penelitian berada di `webapp/research/`:

- `code.ipynb`: eksplorasi data, preprocessing, dan training model
- `DATASET-BERAS.csv`: dataset harga harian, 2.038 tanggal dan 9 komoditas
- `trend_models.pkl`: artefak model trend
- `features_transformers.pkl`: transformer fitur
- `stl_results.pkl`: hasil dekomposisi STL

Jalankan notebook dengan working directory `webapp/research/` agar path relatif
dataset dan artefak tetap bekerja. Tech stack penelitian meliputi Python,
Jupyter, Pandas, NumPy, Scikit-learn, Statsmodels, LightGBM, Seaborn, dan
Matplotlib.

## Model Aplikasi

Aplikasi hanya melakukan inference. Model hasil training disimpan di
`webapp/backend/artifacts/models/` dengan format:

```text
{algoritma}__{kode-komoditas}__h{horizon}.pkl
```

Contoh:

```text
ga_lightgbm__cabai-rawit-merah__h1.pkl
```

Daftarkan model dari folder backend:

```bash
cd webapp/backend
python -m pangania.register_models --dry-run
python -m pangania.register_models
```

Model wajib menggunakan fitur residual MSTL yang sama dengan notebook. Backend
membaca dataset dan artefak penelitian melalui `pangania.config`, sehingga
training dan inference memakai resource yang konsisten.

## Akun Pengembangan

| Item | Nilai |
| --- | --- |
| Login admin | `admin@pangania.id` |
| Kata sandi | `pangania2026` |
| Port backend | `8010` |
| Port frontend | `5173` |

Ganti kredensial dan `PANGANIA_SECRET_KEY` melalui environment variable sebelum
deployment. Data digunakan untuk kebutuhan akademik skripsi dan penggunaan
lanjutan tetap mengikuti ketentuan sumber data resmi.

