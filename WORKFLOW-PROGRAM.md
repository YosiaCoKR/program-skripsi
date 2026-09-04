# Workflow Pengerjaan Skripsi

## Optimasi Hyperparameter LightGBM Regressor Menggunakan Genetic Algorithm untuk Prediksi Harga Komoditas Beras, Bawang Merah, dan Cabai Rawit di Provinsi DIY

**NIM:** 535230117 | **Nama:** Yosia Sipahutar | **Dosen Pembimbing:** Ibu Lely Hiryanto, S.T., M.Sc., Ph.D

---

## 0. Ringkasan Sistem

Penelitian ini punya **2 output berbeda** yang saling terhubung, jangan dikerjain sebagai satu model tunggal:

| Output                 | Horizon              | Metode                           | Sifat                              | Status vs proposal |
|------------------------|-----------------------|-----------------------------------|-------------------------------------|----------------------|
| Prediksi harga presisi | 1 hari, 7 hari, 30 hari | GA-LightGBM (27 model)          | Nilai eksak (Rp/kg)                | Ada di proposal (RQ, tujuan, modul) |
| Early warning system   | Bulanan               | Persentase selisih **prediksi H+30 vs harga hari ini** + ambang tetap | Peringatan dini menghadap ke depan | Ada di proposal (RQ #4, modul, fitur app) |

**Dataset:** Data harian harga 9 komoditas DIY dari Bank Indonesia (PIHPS), **4 Jan 2021 – 3 Agu 2026**, **2.038 baris × 10 kolom** (tanggal + 9 komoditas). 611 tanggal (**29,98%**) tidak memiliki data karena pasar tidak disurvei di akhir pekan/hari libur — **tanggal ini DIISI (interpolasi), bukan di-drop**, supaya jarak antarbaris tetap seragam. Jumlah baris final setelah preprocessing tetap **2.038 baris** (bukan berkurang).

> ⚠️ **Koreksi angka — diverifikasi ulang langsung dari `DATASET-BERAS.csv` (20 Agu 2026):** jumlah baris sebenarnya **2.038**, bukan 2.039, dan tanggal kosong **611**, bukan 612. Kekosongan selalu terjadi di kesembilan kolom sekaligus (tidak ada missing parsial). Angka **1.427** yang muncul di draft lama itu = 2.038 − 611 = jumlah baris yang PUNYA data, yaitu sisa baris seandainya tanggal kosong di-drop — bukan "jumlah baris kosong" seperti tertulis di catatan revisi sebelumnya. Substansinya tidak berubah: tanggal kosong tetap **diisi**, bukan di-drop, supaya kontinuitas lag/rolling tidak rusak, sehingga baris final tetap 2.038.
>
> ⚠️ **Ikutan yang harus dikoreksi:** BAB I proposal masih menulis 2.039 baris / 612 tanggal / 30,0%. Angka itu perlu diperbaiki juga supaya konsisten. BAB II sudah memakai angka yang benar.

**9 komoditas (univariat, tiap komoditas diperlakukan terpisah):** Beras Kualitas Bawah I & II, Medium I & II, Super I & II, Bawang Merah Ukuran Sedang, Cabai Rawit Hijau & Merah. Setiap komoditas diramal murni dari riwayat harganya sendiri (tanpa fitur komoditas lain).

---

## 0.1 Keputusan Terbaru (30 Agustus 2026)

Empat perubahan ruang lingkup. Bagian-bagian di bawah sudah disesuaikan; yang belum beres ditandai eksplisit.

| # | Keputusan | Dampak |
|---|---|---|
| 1 | **Holt / ETS(A,A,N) dibuang** — step 11 dibatalkan | Luaran final tinggal **27 model GA-LightGBM + EWS bulanan** |
| 2 | **`trend_models` (LinearRegression) jadi satu-satunya model tren** | Tabel "dua model trend" di step 4 disederhanakan |
| 3 | **EWS disederhanakan** jadi selisih persentase, ambang tetap | Tanpa z-score, tanpa threshold configurable, **stateless** |
| 4 | **PACF & Ljung-Box = diagnostik BAB IV**, bukan bagian pipeline | Skripnya sudah ada di `webapp/research/`, tinggal dijalankan |

**MSTL TETAP WAJIB.** Ini yang paling sering salah paham: Holt itu *konsumen* output MSTL (di-fit di atas deret terdeseasonalisasi), bukan alasan keberadaannya. Setelah Holt dibuang, MSTL tetap menyuplai step 5, 6, 8, 10, 12, dan 13 — dan justru makin krusial, karena `trend_models` jadi satu-satunya yang bisa mengekstrapolasi tren ke tanggal masa depan. Tanpa itu, keluaran 27 model berhenti sebagai residual (~0,05) dan tidak pernah jadi rupiah.

**Sisa pekerjaan administratif:**

| Item | Status |
|---|---|
| Proposal **1.5** (Manfaat poin 2 — proyeksi laju kenaikan) | ✅ sudah dihapus |
| Proposal **1.7** (SDG 12) | ⬜ belum — arahkan framing-nya ke EWS bulanan |
| Tabel `projections` + `services/projections.py` di backend | ⬜ yatim, perlu dibersihkan |
| Tabel `predictions`, `ews_alerts`, `ews_settings` | ⬜ tidak terpakai lagi oleh EWS versi baru |


---

## 1. Raw Data Collection

```python
import pandas as pd

df = pd.read_csv('DATASET-BERAS.csv', parse_dates=['tanggal'])
df = df.sort_values('tanggal').reset_index(drop=True)
```

---

## 2. Penanganan Missing Value

**Prinsip:** jangan drop (rusak kontinuitas lag features), jangan mean (rusak trend). Pakai interpolasi berbasis waktu — sesuai proposal 1.3, tanggal kosong "diisi ... agar jarak antarbaris tetap seragam".

```python
df = df.set_index('tanggal')

# Time-based linear interpolation — isi gap proporsional ke jarak waktu,
# preserve trend lokal (beda dengan mean yang pakai satu angka statis)
df['harga'] = df['harga'].interpolate(method='time')

df = df.reset_index()

# Sanity check — pastikan baris final = 2038, BUKAN berkurang
assert len(df) == 2038, f"Row count berubah: {len(df)} (harusnya tanggal kosong diisi, bukan didrop)"
```

**Aturan pemilihan metode:**

| Metode                       | Kapan dipakai                                                                                  |
|-------------------------------|--------------------------------------------------------------------------------------------------|
| `interpolate(method='time')` | Gap pendek 1-5 hari — default pilihan                                                            |
| Forward-fill (`ffill`)       | Gap karena hari libur pasar (harga "bertahan")                                                   |
| Mean/median                  | ❌ Jangan — merusak struktur temporal data bertrend                                              |
| Drop baris                   | ❌ Jangan dipakai di sini — proposal eksplisit minta diisi, bukan didrop (beda dengan step lama) |

Cek dulu apakah baris kosong di data kamu itu "hari tanpa observasi" (semua kolom kosong) atau "missing value parsial" (sebagian kolom kosong) — treatment-nya sama-sama interpolasi time-based, tapi laporkan proporsinya (611/2038 ≈ 29,98%) di BAB 3/4 — dan perbaiki dulu angka 612/2039 yang terlanjur ditulis di proposal.

---

## 3. Cek Stasioneritas (ADF Test)

```python
from statsmodels.tsa.stattools import adfuller

commodity_cols = ['beras_bawah_1', 'beras_bawah_2', 'beras_medium_1', 'beras_medium_2',
                   'beras_super_1', 'beras_super_2', 'bawang_merah', 'cabai_hijau', 'cabai_merah']

for col in commodity_cols:
    p_value = adfuller(df[col].dropna())[1]
    status = 'non-stationary (perlu detrend)' if p_value > 0.05 else 'stationary'
    print(f"{col}: p-value={p_value:.4f} → {status}")
```

---

## 4. Detrend — MSTL Decomposition (Multi-Seasonal) + Model Trend

**Kenapa MSTL, bukan STL single-period atau `LinearRegression` polos:** harga komoditas pangan gak bergerak sebagai garis lurus sepanjang 5 tahun, dan punya lebih dari satu pola musiman sekaligus — pola mingguan pasar DAN pola musiman tahunan (panen raya, Ramadan, El Niño/La Niña, musim wisatawan — semua disebut eksplisit di latar belakang proposal 1.1). `MSTL` (`statsmodels.tsa.seasonal.MSTL`) memisahkan trend + **beberapa** seasonal component sekaligus (`periods=(7, 365)`) + residual, jadi gak perlu milih salah satu antara weekly atau annual.

> ⚠️ **Catatan penting:** MSTL, kayak STL, itu alat *decomposition*, bukan model forecasting — gak bisa `.predict()` ke `time_idx` masa depan. Karena step 12 (EWS) dan step 13 (rolling forecast) butuh ekstrapolasi ke depan, kita fit satu model tambahan di atas hasil MSTL.
>
> **Satu model trend — `trend_models`:**
>
> | Model | Dipakai di | Input | Kenapa model ini |
> |---|---|---|---|
> | `trend_models` — `LinearRegression` atas `time_idx` | **step 12 & 13** (EWS + rekonstruksi harga H+1/H+7/H+30) | kurva `{col}_trend` hasil MSTL | Definisi residual pas training ngacu ke kurva trend MSTL. Komponen trend saat inference WAJIB konsisten sama kurva itu — kalau ditukar model lain, input LightGBM bergeser sistematis dan semua prediksi jadi bias. |
>
> Jadi `trend_models[col]` bukan trend langsung dari data, tapi model yang di-fit ke trend hasil MSTL.
>
> ⚠️ **Konsekuensi buang Holt (30 Agu 2026):** beban ekstrapolasi sekarang 100% di `LinearRegression`, dan asumsinya keras — tren harga dianggap satu garis lurus untuk seluruh 5 tahun data. Dulu kelemahan ini ditawar Holt (bobot meluruh eksponensial, mengikuti kecenderungan terkini); sekarang tidak ada penawarnya. Dampaknya terbatas karena horizon terjauh cuma 30 hari, **tapi wajib ditulis di keterbatasan BAB IV**: ekstrapolasi tren mengasumsikan laju linear, valid untuk horizon pendek.
>
> Kenapa `periods=(7, 365)` dan bukan cuma salah satu: `period=7` doang berisiko nangkep artefak interpolasi (611/2038 ≈ 30% tanggal yang diisi itu polanya fixed tiap akhir pekan/libur, jadi "weekly seasonality" bisa jadi cuma ngukur metode interpolasi kamu sendiri, bukan sinyal pasar asli) — tapi tetap dimasukkan karena pola mingguan survei pasar itu nyata secara struktural. `period=365` nangkep pola musiman tahunan yang jauh lebih substantif secara domain (panen, musim wisata). Dengan MSTL, dua-duanya kepisah eksplisit jadi kolom terpisah, jadi kamu bisa justify dan interpretasi masing-masing secara terpisah di BAB 4.
>
> Efek Ramadan/hari besar **tetap tidak** sepenuhnya tertangkap `period=365` — kalender Hijriah bergeser ~11 hari tiap tahun Masehi, jadi meski ada komponen tahunan, "lonjakan Ramadan" gak selalu jatuh di titik kalender yang sama tiap siklus 365 hari → seasonal_annual component MSTL cuma nangkep rata-rata musiman kasar, bukan lonjakan presisi per tahun. Makanya fitur `is_ramadan`/`is_hari_besar_window` di step 5 **tetap wajib** dihandle eksplisit.
>
> **Limitasi jumlah siklus:** 2.038 baris ÷ 365 ≈ 5,6 siklus tahunan — di bawah rekomendasi ideal (6-10 siklus) buat estimasi seasonal annual yang stabil. Perlu disebutkan sebagai keterbatasan di BAB 4, terutama variance seasonal component di ujung-ujung data (awal & akhir series).

```python
from statsmodels.tsa.seasonal import MSTL
from sklearn.linear_model import LinearRegression
import numpy as np

df['time_idx'] = np.arange(len(df))
trend_models = {}       # model ekstrapolasi (fit di atas trend MSTL) — dipakai step 12 & 13
mstl_results = {}        # simpan full MSTL result kalau perlu inspeksi/plot residual

for col in commodity_cols:
    # 1) MSTL decomposition — trend lokal + weekly & annual seasonality terpisah,
    #    jauh lebih realistis dari linear fit tunggal atau STL single-period
    mstl = MSTL(df.set_index('tanggal')[col], periods=(7, 365), stl_kwargs={'robust': True}).fit()
    mstl_results[col] = mstl

    df[f'{col}_trend'] = mstl.trend.values
    df[f'{col}_seasonal_weekly'] = mstl.seasonal['seasonal_7'].values
    df[f'{col}_seasonal_annual'] = mstl.seasonal['seasonal_365'].values
    df[f'{col}_residual'] = mstl.resid.values  # ini yang lanjut ke step 5 (feature engineering)

    # 2) fit model ekstrapolasi terpisah di atas trend hasil MSTL —
    #    supaya step 12 & 13 tetap bisa proyeksi ke time_idx masa depan
    tm = LinearRegression().fit(df[['time_idx']], df[f'{col}_trend'])
    trend_models[col] = tm
```


**Cara simpen `trend_models` dan `mstl_results`:**

```python
import joblib

joblib.dump(trend_models, 'trend_models.pkl')   # LinearRegression -> step 12 & 13
joblib.dump(mstl_results, 'mstl_results.pkl')

# cara load lagi nanti (di notebook/script lain, gak perlu re-run MSTL dari awal):
trend_models = joblib.load('trend_models.pkl')
mstl_results = joblib.load('mstl_results.pkl')
```

`joblib` lebih disaranin daripada `pickle` bawaan buat nyimpen object sklearn/statsmodels (lebih efisien buat numpy array di dalemnya). `trend_models` dipakai lagi di step 12 (EWS) dan step 13 (rolling forecast) — jadi gak perlu re-run MSTL tiap kali butuh nge-predict trend ke depan. `mstl_results` berguna buat lampiran/visualisasi decomposition (trend, seasonal_weekly, seasonal_annual, residual) di BAB 4, dan buat debugging kalau hasil prediksi meleset jauh (bisa dicek ulang komponen mana yang aneh).

Model final LightGBM (step 8) dan model baseline (step 9) juga sama caranya:

```python
joblib.dump(models, 'lightgbm_models.pkl')          # 27 model GA-LightGBM, key: (komoditas, horizon)
joblib.dump(baseline_models, 'baseline_models.pkl')  # model default + gridsearch, key: (label, komoditas, horizon)
```

---

## 5. Feature Engineering (di level residual)

> ℹ️ **Catatan:** proposal 1.3 sebenernya eksplisit menyebutkan fitur "penanda periode Ramadan dan hari besar keagamaan" sebagai bagian dari petunjuk model — tapi berdasarkan keputusan kamu, fitur ini **sengaja tidak diimplementasikan** di workflow ini untuk simplifikasi. Kalau nanti ditanya dosen pembimbing kenapa fitur ini gak ada padahal disebut di proposal, siapin jawaban singkat (misal: dianggap sudah cukup terwakili oleh `month_sin`/`month_cos` dan `seasonal_annual` dari MSTL, atau kompleksitas implementasi kalender Hijriah dianggap di luar prioritas utama penelitian).

> ℹ️ **PACF — diagnostik, bukan bagian pipeline (catatan 30 Agu 2026).** Angka lag `[1, 7, 14, 30]` di step ini ditulis langsung, padahal BAB II menyebut PACF sebagai dasarnya. Model berbasis pohon memang **tidak** butuh PACF sebagai syarat teknis — di ARIMA order `p` harfiah dibaca dari PACF, di LightGBM tidak. Jadi PACF tidak masuk arsitektur sistem dan tidak menghasilkan kolom apa pun. Tapi demi konsistensi naskah, pilih salah satu:
>
> 1. Jalankan `python webapp/research/pacf_cek.py` sekali — hasilnya jadi tabel + grafik BAB IV. **(disarankan: skripnya sudah jadi, jalannya beberapa detik)**
> 2. Atau hapus klaim PACF dari BAB II, ganti alasan domain: lag 1 (harian), 7 (mingguan), 14 (dwimingguan), 30 (bulanan).

> 🔓 **Keputusan terbuka — fitur kalender Hijriah.** Catatan di atas menyatakan fitur Ramadan sengaja tidak diimplementasikan. Ini masih bisa ditinjau ulang, dan argumennya kuat: MSTL `period=365` mengunci pola tahunan ke kalender Masehi, sementara Lebaran bergeser hampir 2 bulan penuh sepanjang rentang data (13 Mei 2021 → 20 Mar 2026). Lonjakan itu **tidak** terserap `seasonal_annual`, jadi murni tertinggal di residual — artinya sekarang dia jadi error model.
>
> Kalau diambil: `pip install hijridate`, lalu fitur `days_from_idulfitri` (bertanda, di-clip ±60 hari — negatif = menuju Lebaran, positif = pasca), `is_ramadan`, `ramadan_progress`, `hijri_month_sin/cos`. Nilainya **diketahui pasti untuk tanggal masa depan**, jadi harus di-align ke tanggal target (`cal.shift(-h)`), bukan tanggal `t` — ini berlaku juga untuk `day_of_week`/`month_sin`/`month_cos` yang sudah ada. Catatan akurasi: `hijridate` pakai Umm al-Qura (Saudi), tanggal Kemenag bisa beda 1 hari; untuk 6 tanggal Idul Fitri 2021-2026 lebih baik di-hardcode.
>
> ⚠️ **Belum diputuskan.** Kalau diambil, GA **wajib** dijalankan ulang karena himpunan fiturnya berubah.

Pakai `feature-engine` (`pip install feature-engine`) — transformer sklearn-style (`fit()`/`transform()`) buat lag & rolling window features. Alasan pindah dari manual pandas: bukan cuma soal konsistensi train/inference (dibahas di step 13), tapi juga manual pandas rawan `PerformanceWarning: DataFrame is highly fragmented` kalau nambahin banyak kolom satu-satu di loop — `feature-engine` nge-handle ini secara internal jadi gak ganggu.

```python
from feature_engine.timeseries.forecasting import LagFeatures, WindowFeatures
import joblib

feature_transformers = {}  # simpan 1 pasang transformer per komoditas

for col in commodity_cols:
    lag_transformer = LagFeatures(
        variables=[f'{col}_residual'],
        periods=[1, 7, 14, 30],
    )
    window_transformer = WindowFeatures(
        variables=[f'{col}_residual'],
        window=[7, 30],
        functions=['mean', 'std'],
    )
    # WindowFeatures secara default udah nge-shift(1) dulu sebelum rolling
    # (gak include baris hari ini sendiri) — jadi gak perlu mikirin manual
    # shift(1) kayak versi pandas polos, ini udah dihandle bawaan library-nya

    df = lag_transformer.fit_transform(df)
    df = window_transformer.fit_transform(df)

    feature_transformers[col] = {'lag': lag_transformer, 'window': window_transformer}

# fitur kalender — cyclical encoding biar Desember & Januari "keliatan deket"
# ke model (bukan dianggap beda jauh kayak encoding angka biasa 12 vs 1),
# ini tetep manual, gak perlu library tambahan buat hal sesimpel ini
df['day_of_week'] = df['tanggal'].dt.dayofweek
df['month_sin'] = np.sin(2*np.pi*df['tanggal'].dt.month/12)
df['month_cos'] = np.cos(2*np.pi*df['tanggal'].dt.month/12)

# simpan transformer-nya — WAJIB, dipakai lagi di step 13 biar konsisten
joblib.dump(feature_transformers, 'feature_transformers.pkl')
```

**Nama kolom hasil transform beda format dari manual:** `LagFeatures`/`WindowFeatures` otomatis kasih nama kolom baru (misal `{col}_residual_lag_1`, `{col}_residual_window_7_mean`), bukan `{col}_lag1`/`{col}_roll_mean7`.

**`feature_cols_for(col)` — dipakai berkali-kali mulai step 6 dst, definisiin di sini:**

```python
def feature_cols_for(col):
    """Ambil semua kolom fitur buat 1 komoditas — cari otomatis berdasarkan
    prefix '{col}_residual_' (hasil LagFeatures/WindowFeatures), BUKAN hardcode
    nama kolom satu-satu. Kalau format nama dari feature-engine beda dikit
    (versi library beda dll), ini tetep jalan tanpa perlu diubah manual —
    lebih robust daripada nebak-nebak format persis."""
    lag_window_cols = [c for c in df.columns if c.startswith(f'{col}_residual_')]
    calendar_cols = ['day_of_week', 'month_sin', 'month_cos']
    return lag_window_cols + calendar_cols

# cek hasilnya sebelum lanjut ke step 6 — pastiin isinya cuma lag/rolling
# window (bukan kecampur kolom lain yang prefix-nya mirip, misal _trend/
# _seasonal_weekly dari MSTL step 4)
print(feature_cols_for(commodity_cols[0]))
```

---

## 6. Setup Direct Multi-Horizon (H+1, H+7, H+30)

Model terpisah per horizon — bukan recursive (prediksi H+1 dipakai buat prediksi H+2, dst) karena itu bikin error numpuk. Sesuai proposal 1.3: "Direct Multi-step Forecasting ... meminimalkan kesalahan agar tidak merembet antarjangka waktu."

```python
horizons = [1, 7, 30]

for col in commodity_cols:
    for h in horizons:
        df[f'{col}_target_h{h}'] = df[f'{col}_residual'].shift(-h)
```

---

## 7. GA Hyperparameter Optimization — `pygad`

Fitness function pakai **10-Fold Cross-Validation** untuk cari kombinasi hyperparameter LightGBM terbaik. Proposal 1.3 sudah secara eksplisit menetapkan K-Fold CV untuk tahap pencarian GA ini (terpisah dari Time Series Split yang dipakai khusus untuk evaluasi model final di step 9-10) — jadi ini **bukan lagi item diskusi terbuka ke dosen pembimbing**, sudah jadi keputusan desain yang tertulis di proposal.

Dipilih `pygad` (bukan `deap`) — API-nya jauh lebih ringkas buat kasus hyperparameter search kayak ini, gak butuh boilerplate `Toolbox`/`creator` manual kayak `deap`. Sebelas hyperparameter dicari sekaligus: `num_leaves`, `learning_rate`, `max_depth`, `n_estimators`, `min_child_samples`, `subsample`, `colsample_bytree`, `min_child_weight`, `reg_alpha`, `reg_lambda`, `min_split_gain` — `bagging_freq` di-fixed (bukan gene GA) karena `subsample` gak akan efektif tanpa itu.

> ⚠️ **Hindari pasangan alias di LightGBM:** `min_child_samples`≡`min_data_in_leaf` dan `min_child_weight`≡`min_sum_hessian_in_leaf` itu literally parameter yang sama dengan nama beda — jangan masukin dua-duanya sebagai gene terpisah, buang-buang dimensi search space GA. Yang dipakai di sini cuma salah satu dari tiap pasangan.

```python
import lightgbm as lgb
from sklearn.model_selection import KFold
import numpy as np
import pygad

def fitness_function(params, X, y):
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    rmses = []
    for train_idx, val_idx in kf.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

        model = lgb.LGBMRegressor(**params, verbose=-1)   # verbose=-1: silent-in log internal
                                                             # LightGBM (misal "no further splits
                                                             # with positive gain" — itu normal,
                                                             # bukan error, cuma noise output)
        model.fit(
            X_train, y_train,
            eval_X=X_val, eval_y=y_val,   # nama parameter baru (versi LightGBM lebih baru
                                            # deprecated eval_set=[(X_val, y_val)])
            callbacks=[lgb.early_stopping(stopping_rounds=20, verbose=False)],
        )  # early stopping — n_estimators gede di gene_space gak selalu kepake penuh,
           # LightGBM berhenti sendiri kalau 20 iterasi berturut gak improve

        pred = model.predict(X_val)
        rmses.append(np.sqrt(np.mean((y_val - pred) ** 2)))
    return np.mean(rmses)  # ini yang mau diminimalkan


def fitness_func_pygad(ga_instance, solution, solution_idx):
    params = {
        "num_leaves": int(solution[0]),
        "learning_rate": solution[1],
        "max_depth": int(solution[2]),
        "n_estimators": int(solution[3]),
        "min_child_samples": int(solution[4]),
        "subsample": solution[5],
        "colsample_bytree": solution[6],
        "min_child_weight": solution[7],
        "reg_alpha": solution[8],
        "reg_lambda": solution[9],
        "min_split_gain": solution[10],
        "bagging_freq": 1,   # fixed, bukan gene — wajib biar subsample beneran aktif
    }
    return -fitness_function(params, X, y)   # dikali -1: pygad maximize, kita mau minimize RMSE


def run_ga_for(X, y):
    ga_instance = pygad.GA(
        num_generations=30,
        num_parents_mating=15,
        sol_per_pop=40,
        fitness_func=fitness_func_pygad,
        num_genes=11,
        mutation_percent_genes=[20, 5],   # list 2 elemen — wajib karena mutation_type="adaptive"
                                            # [rate solusi jelek, rate solusi bagus]
        gene_space=[
            {"low": 20, "high": 1000},     # num_leaves
            {"low": 0.001, "high": 0.5},   # learning_rate
            {"low": 3, "high": 15},        # max_depth
            {"low": 50, "high": 1000},     # n_estimators
            {"low": 1, "high": 100},       # min_child_samples
            {"low": 0.5, "high": 1.0},     # subsample
            {"low": 0.5, "high": 1.0},     # colsample_bytree
            {"low": 1e-6, "high": 10.0},   # min_child_weight
            {"low": 0.0, "high": 10.0},    # reg_alpha
            {"low": 0.0, "high": 10.0},    # reg_lambda
            {"low": 0.0, "high": 1.0},     # min_split_gain
        ],
        gene_type=float,
        parent_selection_type="tournament",
        K_tournament=5,
        crossover_type="single_point",
        crossover_probability=0.9,
        mutation_type="adaptive",
        keep_elitism=1,
        on_generation=lambda ga: print(
            f"  Gen {ga.generations_completed}: RMSE terbaik = {-ga.best_solution()[1]:.4f}"
        ),  # fitness itu -RMSE (dibalik biar pygad bisa maximize), jadi
            # di-flip lagi di sini biar progress kebaca sebagai RMSE positif
            # normal (makin generasi, angkanya makin turun/mendekati 0 = makin bagus)
    )
    ga_instance.run()
    best_solution, best_fitness, _ = ga_instance.best_solution()
    return best_solution, ga_instance


# Jalankan per komoditas × per horizon (27 proses pencarian, sesuai proposal 1.4:
# "Pencarian dilakukan untuk setiap pasangan komoditas dan jangka waktu, sehingga
# menghasilkan 27 proses pencarian")
best_params_from_GA = {}
for col in commodity_cols:
    best_params_from_GA[col] = {}
    for h in horizons:
        X = df[feature_cols_for(col)].dropna()
        y = df.loc[X.index, f'{col}_target_h{h}']
        best_solution, ga_instance = run_ga_for(X, y)

        best_params_from_GA[col][h] = {
            "num_leaves": int(best_solution[0]),
            "learning_rate": best_solution[1],
            "max_depth": int(best_solution[2]),
            "n_estimators": int(best_solution[3]),
            "min_child_samples": int(best_solution[4]),
            "subsample": best_solution[5],
            "colsample_bytree": best_solution[6],
            "min_child_weight": best_solution[7],
            "reg_alpha": best_solution[8],
            "reg_lambda": best_solution[9],
            "min_split_gain": best_solution[10],
            "bagging_freq": 1,
        }
```

**Kenapa `n_estimators`/`num_leaves` range-nya masih lumayan lebar (bukan yang udah dikecilin sebelumnya):** ini keputusan trade-off eksplorasi vs biaya komputasi — dengan `sol_per_pop=40` × `num_generations=30` × 10-fold CV × 27 kombinasi, itu udah lumayan berat (ratusan ribu kali training). Kalau ternyata kelamaan di eksekusi beneran, turunin `sol_per_pop`/`num_generations` dulu (bukan range gene_space-nya) — biar ruang pencariannya tetap representatif, cuma budget evaluasinya yang dikurangin.

---

## 8. Training Model Final per Komoditas × Horizon

```python
models = {}
for col in commodity_cols:
    for h in horizons:
        X_train = df[feature_cols_for(col)].dropna()
        y_train = df.loc[X_train.index, f'{col}_target_h{h}']
        model = lgb.LGBMRegressor(**best_params_from_GA[col][h], verbose=-1)
        model.fit(X_train, y_train)
        models[(col, h)] = model
```

---

## 9. Model Pembanding (Baseline) — WAJIB, sebelumnya hilang di workflow

> ⚠️ **Ini gap paling penting.** Rumusan masalah #3 dan tujuan #3 di proposal eksplisit meminta perbandingan GA-LightGBM terhadap **4 model**: (1) tebakan sederhana (naive baseline), (2) LightGBM pengaturan bawaan (default hyperparameter), (3) LightGBM dengan pengaturan yang ditelusuri satu per satu (manual/grid search — proposal 1.6 menyebut publikasi pembanding pakai `GridSearchCV`, jadi ini bisa jadi acuan), dan (4) GA-LightGBM (model utama). Draft workflow sebelumnya cuma melatih 1 model per komoditas×horizon tanpa baseline apapun — evaluasi di step 10 jadi tidak bisa menjawab RQ3.

```python
from sklearn.model_selection import GridSearchCV

baseline_models = {}

for col in commodity_cols:
    for h in horizons:
        X_train = df[feature_cols_for(col)].dropna()
        y_train = df.loc[X_train.index, f'{col}_target_h{h}']

        # (1) Naive baseline — tebakan sederhana: harga besok = harga hari ini
        #     (persistence model / random walk), dihitung langsung saat evaluasi,
        #     tidak perlu "dilatih".

        # (2) LightGBM default hyperparameter
        model_default = lgb.LGBMRegressor(verbose=-1)  # tanpa tuning
        model_default.fit(X_train, y_train)
        baseline_models[('default', col, h)] = model_default

        # (3) LightGBM manual/grid search (one-by-one) — pembanding "penyetelan
        #     sulit direproduksi" yang disebut di latar belakang proposal
        param_grid = {
            'num_leaves': [15, 31, 63],
            'max_depth': [3, 5, 7, -1],
            'learning_rate': [0.01, 0.05, 0.1],
        }
        gs = GridSearchCV(lgb.LGBMRegressor(verbose=-1), param_grid, cv=10, scoring='neg_root_mean_squared_error')
        gs.fit(X_train, y_train)
        baseline_models[('gridsearch', col, h)] = gs.best_estimator_

        # (4) GA-LightGBM sudah ada di `models` dari step 8
```

---

## 10. Evaluasi Model (MAE, RMSE, R², MAPE) — 4 model dibandingkan

Proposal 1.4 modul "Pelatihan dan Evaluasi Model": evaluasi pakai **walk-forward validation dengan expanding window** (setara `TimeSeriesSplit` yang tiap fold berikutnya memasukkan lebih banyak data historis), dihitung hanya pada tanggal yang benar-benar diobservasi (bukan hasil interpolasi), dan dibandingkan ke 4 model dari step 9.

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

def naive_predict(df, col, h):
    return df[col].shift(h)  # harga h hari lalu sebagai tebakan h hari ke depan

tscv = TimeSeriesSplit(n_splits=5)  # expanding window
results = []

for col in commodity_cols:
    for h in horizons:
        df_valid = df.dropna(subset=[f'{col}_target_h{h}'])
        # filter hanya tanggal yang benar-benar diobservasi (bukan hasil interpolasi)
        df_valid = df_valid[df_valid[f'{col}_is_observed'] == 1]

        for train_idx, test_idx in tscv.split(df_valid):
            y_test = df_valid.iloc[test_idx][f'{col}_target_h{h}']

            for label, model in [
                ('naive', None),
                ('default', baseline_models[('default', col, h)]),
                ('gridsearch', baseline_models[('gridsearch', col, h)]),
                ('ga_lightgbm', models[(col, h)]),
            ]:
                if label == 'naive':
                    y_pred = naive_predict(df_valid.iloc[test_idx], col, h)
                else:
                    y_pred = model.predict(df_valid.iloc[test_idx][feature_cols_for(col)])

                mae = mean_absolute_error(y_test, y_pred)
                rmse = np.sqrt(mean_squared_error(y_test, y_pred))
                mape = np.mean(np.abs((y_test - y_pred) / y_test)) * 100
                results.append({'komoditas': col, 'horizon': h, 'model': label,
                                 'mae': mae, 'rmse': rmse, 'mape': mape})

# rata-ratakan per model × horizon — ini yang dilaporkan di BAB 4, dan
# jadi bukti untuk indikator capaian tujuan #1 (error < 10%) dan #3 (GA < 4 baseline lain)
```

---

## 11. ~~Proyeksi Laju Kenaikan (2-3 Tahun)~~ — DIBATALKAN

> 🚫 **Dibatalkan 30 Agustus 2026.** Holt's linear trend / ETS(A,A,N) tidak jadi dipakai. Step ini keluar dari ruang lingkup penelitian. Nomornya sengaja dipertahankan supaya rujukan "step 12"/"step 13" di bagian lain tidak bergeser.
>
> **Yang hilang, supaya kamu sadar konsekuensinya:**
>
> - Proyeksi laju kenaikan 2-3 tahun beserta interval prediksi 95% — tidak ada lagi
> - Klaim di proposal **1.5** (Manfaat poin 2) sudah dihapus; **1.7** (SDG 12) masih perlu diarahkan ulang ke EWS bulanan
> - `holt_models.pkl` tidak pernah dibuat dan memang tidak perlu
> - Tabel `projections` + `services/projections.py` di backend jadi yatim
>
> **Yang TIDAK ikut dibuang:** MSTL dan `trend_models`. Lihat 0.1 — Holt itu konsumen output MSTL, bukan alasan keberadaannya.
>
> **Kalau nanti berubah pikiran** dan ingin proyeksi jangka panjang tanpa menghidupkan Holt: ekstrapolasi `trend_models` yang sudah ada, dan turunkan intervalnya dari standar deviasi residual — bukan dari persentase tebakan seperti `UNCERTAINTY_PCT_PER_YEAR = 0.06` di draft lama. Kualitasnya di bawah Holt (bobot semua tahun dianggap sama), tapi nol tambahan library.

---


## 12. Early Warning System Bulanan

> ♻️ **Disederhanakan 30 Agustus 2026.** Versi lama — z-score deviasi prediksi vs realisasi, dengan ambang batas yang bisa dikonfigurasi pengguna — diganti selisih persentase sederhana.
>
> **Alasannya:** ambang batas itu **konstanta metodologis yang ditetapkan di awal penelitian**, bukan preferensi pengguna. Kalau admin bisa menggesernya sendiri, hasil EWS tidak reproducible dan justru lemah kalau ditanya penguji.
>
> ⚠️ Draft lama file ini menulis *"Proposal 1.4 bilang ambang batas harus bisa dikonfigurasi pengguna"*. Klaim itu **belum diverifikasi** ke BAB I .docx. Kalau proposal memang tidak menuntut itu, klaim tersebut salah — dan sudah dikoreksi di sini.

**Rumusnya — itu saja:**

```python
def hitung_ews(col):
    harga_hari_ini = df[col].iloc[-1]
    harga_30_hari  = prediksi_h30(col)   # WAJIB sudah dalam rupiah, lihat catatan
    persen = (harga_30_hari - harga_hari_ini) / harga_hari_ini * 100

    if persen > 10:
        status = "Warning - kenaikan signifikan"
    elif persen > 5:
        status = "Waspada - mulai menyimpang"
    else:
        status = "Normal"
    return persen, status
```

> **Satu-satunya langkah yang tidak boleh dilewat:** `prediksi_h30(col)` harus sudah dikembalikan ke **rupiah**. Keluaran mentah LightGBM itu residual (angka ~0,05), bukan harga — kalau lupa, kamu mengurangi 0,05 dari 11.750. Rekonstruksinya `trend + seasonal_weekly + seasonal_annual + residual_pred`, sudah ada di step 13, tinggal dipanggil. Komponen `trend` di tanggal masa depan hanya bisa datang dari `trend_models` (step 4).

**Kenapa versi ini lebih tepat disebut *early warning*:**

| | Versi lama (prediksi vs realisasi) | Versi baru (prediksi vs hari ini) |
|---|---|---|
| Arah pandang | Ke belakang — mengevaluasi akurasi model | **Ke depan** — benar-benar peringatan dini |
| Perlu menyimpan prediksi lama? | Ya (tabel `predictions`) | **Tidak — stateless** |
| Ambang batas | z-score, configurable | Persentase tetap, ditetapkan di awal |
| Perlu database? | Ya | **Tidak** |

Versi lama sebenarnya lebih pas disebut *model monitoring*, bukan peringatan dini: dia baru bisa bicara setelah realisasi sebulan berlalu.

Status bersifat indikatif, hanya peringatan visual di aplikasi, tanpa notifikasi (sesuai proposal 1.4).

---


## 13. Rolling One-Step Forecast (Deployment/Inference)

> ⚠️ **Tambahan wajib — hilang di semua versi sebelumnya.** Proposal 1.3 menyebut "Rolling One-Step Forecast" sebagai salah satu metode, dan 1.4 modul "Peramalan Jangka Pendek" bilang model "dapat digunakan berulang kali setiap ada harga baru yang masuk tanpa perlu pelatihan ulang" — tapi belum pernah ada implementasi konkretnya di workflow. Ini bukan tahap training baru, ini tahap **inference/deployment** setelah model H+1/H+7/H+30 (step 8) sudah final.

**Poin krusial yang wajib dijelaskan di BAB 3/4:** ini beda dari *recursive forecasting*. Recursive forecasting bahaya karena prediksi model dipakai lagi sebagai input prediksi berikutnya (error numpuk) — makanya proposal kamu sengaja pilih Direct Multi-Horizon (step 6) untuk menghindari itu. Rolling one-step forecast **tidak** begitu: yang berubah tiap hari cuma *kapan model dipanggil ulang*, bukan sumber datanya. Lag/rolling features selalu dihitung ulang dari **harga aktual** yang baru masuk, bukan dari hasil prediksi model sebelumnya.

```python
import joblib

# Load transformer yang SAMA PERSIS dipakai pas training (step 5) — ini
# yang bikin rolling forecast konsisten, gak perlu nulis ulang logic manual
feature_transformers = joblib.load('feature_transformers.pkl')
trend_models = joblib.load('trend_models.pkl')

def rolling_forecast_h1(model_h1, col, df_history, tanggal_baru, harga_aktual_baru):
    # 1) data baru masuk sebagai OBSERVASI AKTUAL, bukan hasil prediksi
    df_history.loc[len(df_history)] = {'tanggal': tanggal_baru, col: harga_aktual_baru}

    # 2) recompute komponen deterministik + residual pakai data aktual terbaru.
    #    WAJIB ikut komponen musiman, bukan trend doang — lihat catatan di
    #    bawah blok kode ini.
    time_idx_baru = df_history['time_idx'].iloc[-1] + 1
    trend_baru = trend_models[col].predict([[time_idx_baru]])[0]
    seasonal_baru = seasonal_at(col, tanggal_baru)   # seasonal_7 + seasonal_365
    df_history.loc[df_history.index[-1], f'{col}_residual'] = (
        harga_aktual_baru - trend_baru - seasonal_baru
    )

    # 3) transform pakai transformer yang SAMA dari step 5 (bukan ditulis
    #    ulang manual) — konsistensi dijamin karena objectnya literally
    #    sama, bukan cuma "logic yang mirip"
    lag_tf = feature_transformers[col]['lag']
    window_tf = feature_transformers[col]['window']
    df_history = lag_tf.transform(df_history)
    df_history = window_tf.transform(df_history)

    features = df_history[feature_cols_for(col)].iloc[[-1]]

    # 4) prediksi H+1 pakai model yang SUDAH dilatih sekali (tanpa retrain,
    #    sesuai proposal 1.4: "tidak melakukan pelatihan ulang secara otomatis")
    pred_residual = model_h1.predict(features)[0]
    # balik dari residual ke skala harga — komponen musiman ikut dijumlah lagi
    pred_harga = pred_residual + trend_baru + seasonal_baru

    return pred_harga

# Pola yang sama berlaku untuk model H+7 dan H+30 — bedanya cuma target
# kolom yang diprediksi, mekanismenya (transform pakai transformer yang sama
# dari step 5, tanpa retrain) identik untuk ketiga horizon.
```

> ⚠️ **Koreksi (20 Agu 2026): residual WAJIB ikut dikurangi komponen musiman.** Versi sebelumnya nulis `residual = harga_aktual - trend_baru` doang. Itu gak konsisten sama definisi residual di step 4, yang bunyinya `residual = observed - trend - seasonal_7 - seasonal_365`. Kalau di inference cuma dikurangi trend, input model bergeser sistematis sebesar komponen musiman dan semua prediksi jadi bias. Rekonstruksinya juga harus simetris: `harga = residual_prediksi + trend + seasonal_7 + seasonal_365`.
>
> `seasonal_at(col, tanggal)` ngambil komponen musiman dari `stl_results.pkl` kalau tanggalnya masih di dalam rentang data training, dan ngulang siklus penuh terakhir secara periodik kalau di luar rentang. Backend udah ngelakuin ini dengan benar di `webapp/backend/pangania/ml/decomposition.py` — dokumen ini yang sebelumnya ketinggalan.

**Dua pitfall yang wajib disebut di BAB 4 (keterbatasan):**

1. **Trend extrapolation drift.** `trend_models` (step 4) itu model `LinearRegression` yang di-fit di atas trend hasil MSTL, bukan trend mentah — tapi sifat ekstrapolasinya tetap sama: makin jauh rolling forecast berjalan dari akhir periode training, makin jauh pula ekstrapolasi linear-nya dari range yang pernah dilihat model, akurasi trend component berpotensi menurun kalau model gak pernah di-refresh. Karena proposal 1.4 eksplisit menyatakan tidak ada retraining otomatis/terjadwal, ini jadi asumsi yang harus dinyatakan eksplisit: rolling forecast valid untuk horizon deployment yang tidak terlalu jauh dari akhir data training, pembaruan model dilakukan manual (sesuai proposal).
2. ~~Konsistensi feature pipeline manual~~ — **udah gak jadi masalah** sejak pindah ke `feature-engine` di step 5: `feature_transformers[col]` yang di-load di sini itu **object yang sama persis** yang di-`fit()` pas training, bukan fungsi ditulis ulang. Risiko logic `shift()`/`rolling()` beda antara training vs production otomatis hilang.

---

## Urutan Eksekusi Ringkas

```
1.  Load raw data (2.038 baris × 10 kolom, 4 Jan 2021 – 3 Agu 2026)
2.  Interpolasi missing value (time-based, ISI bukan drop) → tetap 2.038 baris
3.  ADF test per komoditas
4.  Detrend via MSTL decomposition (periods=(7, 365): weekly + annual) -> fit LinearRegression di atas trend MSTL (buat step 12 & 13) -> simpan trend_models + mstl_results
5.  Feature engineering di level residual pakai `feature-engine` (LagFeatures/WindowFeatures + cyclical calendar) → simpan feature_transformers
6.  Setup target per horizon (H+1, H+7, H+30) — direct, bukan recursive
7.  GA optimasi hyperparameter pakai `pygad` (fitness = 10-Fold CV RMSE + early stopping) — 27 proses pencarian, 11 hyperparameter
8.  Training model final GA-LightGBM per komoditas × horizon (27 model)
9.  Training 3 model pembanding: naive, LightGBM default, LightGBM grid/manual search
10. Evaluasi (MAE/RMSE/R²/MAPE) walk-forward expanding window, 4 model dibandingkan
11. ~~Proyeksi laju kenaikan 2-3 tahun~~ -- DIBATALKAN (30 Agu 2026), Holt/ETS tidak dipakai
12. Early warning system bulanan: (prediksi H+30 - harga hari ini) / harga hari ini * 100, ambang tetap, stateless
13. Rolling one-step forecast untuk deployment (model dipakai ulang tiap ada data aktual baru, tanpa retrain)
```

## Lapisan Aplikasi — Catatan Keputusan (30 Agu 2026)

Detail teknisnya di luar scope file ini, tapi tiga keputusan berikut lahir dari perubahan di atas dan perlu dicatat supaya tidak lupa.

**1. EWS versi baru tidak butuh database.** Rumusnya stateless: harga hari ini dari data terakhir, prediksi dari `.pkl`, hitung saat halaman dibuka, selesai. Tidak ada yang perlu diingat dari bulan lalu. Empat tabel jadi tidak terpakai: `predictions`, `ews_alerts`, `ews_settings`, dan `projections` (yatim sejak Holt dibuang).

**2. Streamlit untuk halaman admin — Streamlit sendiri memang tidak butuh database.** Dia framework UI, tanpa penyimpanan apa pun. Yang menciptakan kebutuhan database itu **apa yang dikerjakan** halaman admin, bukan pilihan framework-nya:

| Kebutuhan | Perlu penyimpanan? |
|---|---|
| Menampilkan grafik, prediksi, status EWS | Tidak — cukup CSV + `.pkl` |
| Admin input harga harian baru | **Ya** — hasil input harus bertahan setelah restart |
| Login admin | **Ya** — Streamlit tidak punya auth bawaan |
| Riwayat versi & metrik model | Ya |

⚠️ **Jebakan Streamlit:** setiap interaksi menjalankan ulang seluruh script dari atas, dan `st.session_state` hilang saat refresh. Streamlit **tidak bisa** dipakai sebagai tempat penyimpanan.

**3. Database sudah terlanjur ada dan sudah jalan.** `webapp/backend/pangania/db.py` — SQLite + SQLAlchemy, 11 tabel, dan `routers/admin.py` sudah punya 19 endpoint. Membuangnya berarti menulis ulang backend yang sudah berfungsi. Jalan termurah: **Streamlit jadi klien FastAPI**, panggil endpoint yang sudah ada pakai `requests` (pola di `webapp/research/test.py`). Streamlit tidak perlu tahu apa-apa soal database. SQLite sudah lebih dari cukup untuk skala skripsi — tidak perlu Postgres.

---


## Catatan Penting yang Jangan Lupa

- **Horizon terjauh penelitian ini 30 hari.** Proyeksi 2-3 tahun sudah dibatalkan (step 11) — jangan dihidupkan lagi, dan jangan diganti dengan memaksa LightGBM meramal sejauh itu
- **Satu model trend saja:** `trend_models` (LinearRegression atas kurva trend MSTL), dipakai step 12 & 13 untuk rekonstruksi harga. Sejak Holt dibuang, asumsi "tren = garis lurus 5 tahun" tidak ada penawarnya — tulis di keterbatasan BAB IV
- **MSTL cuma alat decomposition, bukan forecasting model** — trend hasil MSTL gak bisa diekstrapolasi langsung, wajib fit model tambahan di atasnya (step 4) buat kebutuhan step 12 & 13
- **`periods=(7, 365)` dipilih supaya weekly & annual seasonality kepisah eksplisit** — jangan cuma pakai `period=7` doang, karena itu berisiko ngukur artefak interpolasi (611/2038 tanggal kosong yang diisi punya pola fixed tiap akhir pekan), bukan sinyal pasar asli
- **Cuma ~5,6 siklus tahunan** (2038 baris ÷ 365) buat estimasi seasonal_annual — di bawah rekomendasi ideal, sebutkan sebagai keterbatasan di BAB 4
- **Jangan** drop baris missing value — proposal eksplisit minta diisi (interpolasi), baris final tetap 2.038
- **Jangan** pakai mean imputation untuk data bertrend
- **Jangan lupa** 3 model pembanding (naive, default, grid/manual search) di step 9-10 — dibutuhkan untuk menjawab rumusan masalah #3 dan tujuan #3
- **EWS = (prediksi H+30 − harga hari ini) / harga hari ini × 100** dengan ambang tetap (step 12). Bukan z-score, bukan prediksi-vs-realisasi, bukan threshold yang bisa diatur pengguna. Pastikan prediksi H+30 sudah direkonstruksi ke rupiah dulu, bukan residual mentah
- K-Fold CV vs Time Series Split **sudah bukan item diskusi terbuka** — proposal sudah menetapkan: K-Fold untuk fitness GA, walk-forward/expanding window untuk evaluasi final. Validitasnya bersandar pada Bergmeir, Hyndman & Koo (2018) — rujukan [24] BAB II: K-Fold sah untuk model autoregresif **asal sisaannya tidak berkorelasi serial**. Buktikan dengan `python webapp/research/ljung_box_cek.py`, laporkan sebagai tabel uji prasyarat di BAB IV
- Model presisi itu **per komoditas × per horizon** = 9 × 3 = **27 model GA-LightGBM**, plus baseline (naive tanpa training, + 2×27 model pembanding lain)
- **Rolling one-step forecast ≠ recursive forecasting** — lag/rolling features di rolling forecast (step 13) selalu dihitung dari harga **aktual** baru, bukan dari hasil prediksi model sebelumnya. Ini poin yang wajib ditegaskan di BAB 3 supaya reviewer gak salah kira kamu pakai recursive (yang justru dihindari lewat Direct Multi-Horizon di step 6)
- Di luar scope file ini: 5 fitur aplikasi web (Dashboard Harga, Eksplorasi Data Historis, Pelatihan & Optimasi Model, Prediksi Harga Interaktif, Early Warning System) — perlu workflow terpisah untuk lapisan aplikasi/backend-frontend
