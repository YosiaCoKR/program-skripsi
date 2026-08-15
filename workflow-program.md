# Workflow Pengerjaan Skripsi

## Optimasi Hyperparameter LightGBM Regressor Menggunakan Genetic Algorithm untuk Prediksi Harga Komoditas Beras, Bawang Merah, dan Cabai Rawit di Provinsi DIY

**NIM:** 535230117 | **Nama:** Yosia Sipahutar | **Dosen Pembimbing:** Ibu Lely Hiryanto, S.T., M.Sc., Ph.D

---

## 0. Ringkasan Sistem

Penelitian ini punya **3 output berbeda** yang saling terhubung, jangan dikerjain sebagai satu model tunggal:

| Output                 | Horizon              | Metode                           | Sifat                              | Status vs proposal |
|------------------------|-----------------------|-----------------------------------|-------------------------------------|----------------------|
| Prediksi harga presisi | 1 hari, 7 hari, 30 hari | GA-LightGBM (27 model)          | Nilai eksak (Rp/kg)                | Ada di proposal (RQ, tujuan, modul) |
| Proyeksi laju kenaikan | 2-3 tahun             | Trend model (statistik)          | Persentase/rate, bukan nilai eksak | Disebut di Manfaat (1.5) & SDG (1.7) sebagai manfaat kualitatif buat petani, belum diformalkan jadi modul/tujuan teknis terpisah |
| Early warning system   | Bulanan               | Bandingkan **prediksi H+30 vs realisasi aktual** + ambang batas | Deteksi anomali | Ada di proposal (RQ #4, modul, fitur app) |

**Dataset:** Data harian harga 9 komoditas DIY dari Bank Indonesia (PIHPS), 2021-2026, **2.039 baris × 10 kolom** (tanggal + 9 komoditas). 612 tanggal (~30,0%) tidak memiliki data karena pasar tidak disurvei di akhir pekan/hari libur — **tanggal ini DIISI (interpolasi), bukan di-drop**, supaya jarak antarbaris tetap seragam. Jumlah baris final setelah preprocessing tetap **2.039 baris** (bukan berkurang).

> ⚠️ **Koreksi dari versi sebelumnya:** draft lama menulis "2039 baris → 1427 baris setelah preprocessing" — ini salah dan kontradiktif dengan proposal. 2039 − 612 = 1427 itu jumlah baris yang KOSONG, bukan jumlah baris yang tersisa setelah dibuang. Proposal eksplisit bilang tanggal kosong **diisi**, bukan didrop, supaya kontinuitas time series (lag/rolling features) tidak rusak. Baris final tetap 2.039.

**9 komoditas (univariat, tiap komoditas diperlakukan terpisah):** Beras Kualitas Bawah I & II, Medium I & II, Super I & II, Bawang Merah Ukuran Sedang, Cabai Rawit Hijau & Merah. Setiap komoditas diramal murni dari riwayat harganya sendiri (tanpa fitur komoditas lain).

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

# Sanity check — pastikan baris final = 2039, BUKAN berkurang
assert len(df) == 2039, f"Row count berubah: {len(df)} (harusnya tanggal kosong diisi, bukan didrop)"
```

**Aturan pemilihan metode:**

| Metode                       | Kapan dipakai                                                                                  |
|-------------------------------|--------------------------------------------------------------------------------------------------|
| `interpolate(method='time')` | Gap pendek 1-5 hari — default pilihan                                                            |
| Forward-fill (`ffill`)       | Gap karena hari libur pasar (harga "bertahan")                                                   |
| Mean/median                  | ❌ Jangan — merusak struktur temporal data bertrend                                              |
| Drop baris                   | ❌ Jangan dipakai di sini — proposal eksplisit minta diisi, bukan didrop (beda dengan step lama) |

Cek dulu apakah baris kosong di data kamu itu "hari tanpa observasi" (semua kolom kosong) atau "missing value parsial" (sebagian kolom kosong) — treatment-nya sama-sama interpolasi time-based, tapi laporkan proporsinya (612/2039 ≈ 30%) di BAB 3/4 karena itu angka yang sudah kamu klaim di proposal.

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

## 4. Detrend — MSTL Decomposition (Multi-Seasonal) + Secondary Extrapolation Model

**Kenapa MSTL, bukan STL single-period atau `LinearRegression` polos:** harga komoditas pangan gak bergerak sebagai garis lurus sepanjang 5 tahun, dan punya lebih dari satu pola musiman sekaligus — pola mingguan pasar DAN pola musiman tahunan (panen raya, Ramadan, El Niño/La Niña, musim wisatawan — semua disebut eksplisit di latar belakang proposal 1.1). `MSTL` (`statsmodels.tsa.seasonal.MSTL`) memisahkan trend + **beberapa** seasonal component sekaligus (`periods=(7, 365)`) + residual, jadi gak perlu milih salah satu antara weekly atau annual.

> ⚠️ **Catatan penting:** MSTL, kayak STL, itu alat *decomposition*, bukan model forecasting — gak bisa `.predict()` ke `time_idx` masa depan. Karena step 11 (proyeksi 2-3 tahun) dan step 13 (rolling forecast) butuh ekstrapolasi ke depan, kita fit **model kedua** (`LinearRegression`) di atas trend curve hasil MSTL, khusus buat keperluan ekstrapolasi. Jadi `trend_models[col]` bukan trend langsung dari data, tapi model yang di-fit ke trend hasil MSTL.
>
> Kenapa `periods=(7, 365)` dan bukan cuma salah satu: `period=7` doang berisiko nangkep artefak interpolasi (612/2039 ≈ 30% tanggal yang diisi itu polanya fixed tiap akhir pekan/libur, jadi "weekly seasonality" bisa jadi cuma ngukur metode interpolasi kamu sendiri, bukan sinyal pasar asli) — tapi tetap dimasukkan karena pola mingguan survei pasar itu nyata secara struktural. `period=365` nangkep pola musiman tahunan yang jauh lebih substantif secara domain (panen, musim wisata). Dengan MSTL, dua-duanya kepisah eksplisit jadi kolom terpisah, jadi kamu bisa justify dan interpretasi masing-masing secara terpisah di BAB 4.
>
> Efek Ramadan/hari besar **tetap tidak** sepenuhnya tertangkap `period=365` — kalender Hijriah bergeser ~11 hari tiap tahun Masehi, jadi meski ada komponen tahunan, "lonjakan Ramadan" gak selalu jatuh di titik kalender yang sama tiap siklus 365 hari → seasonal_annual component MSTL cuma nangkep rata-rata musiman kasar, bukan lonjakan presisi per tahun. Makanya fitur `is_ramadan`/`is_hari_besar_window` di step 5 **tetap wajib** dihandle eksplisit.
>
> **Limitasi jumlah siklus:** 2.039 baris ÷ 365 ≈ 5,6 siklus tahunan — di bawah rekomendasi ideal (6-10 siklus) buat estimasi seasonal annual yang stabil. Perlu disebutkan sebagai keterbatasan di BAB 4, terutama variance seasonal component di ujung-ujung data (awal & akhir series).

```python
from statsmodels.tsa.seasonal import MSTL
from sklearn.linear_model import LinearRegression
import numpy as np

df['time_idx'] = np.arange(len(df))
trend_models = {}       # model ekstrapolasi (fit di atas trend MSTL) — dipakai step 11 & 13
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
    #    supaya step 11 & 13 tetap bisa proyeksi ke time_idx masa depan
    tm = LinearRegression().fit(df[['time_idx']], df[f'{col}_trend'])
    trend_models[col] = tm
```

**Cara simpen `trend_models` dan `mstl_results`:**

```python
import joblib

joblib.dump(trend_models, 'trend_models.pkl')
joblib.dump(mstl_results, 'mstl_results.pkl')

# cara load lagi nanti (di notebook/script lain, gak perlu re-run MSTL dari awal):
trend_models = joblib.load('trend_models.pkl')
mstl_results = joblib.load('mstl_results.pkl')
```

`joblib` lebih disaranin daripada `pickle` bawaan buat nyimpen object sklearn/statsmodels (lebih efisien buat numpy array di dalemnya). `trend_models` dipakai lagi di step 11 (proyeksi 2-3 tahun) dan step 13 (rolling forecast) — jadi gak perlu re-run MSTL tiap kali butuh nge-predict trend ke depan. `mstl_results` berguna buat lampiran/visualisasi decomposition (trend, seasonal_weekly, seasonal_annual, residual) di BAB 4, dan buat debugging kalau hasil prediksi meleset jauh (bisa dicek ulang komponen mana yang aneh).

Model final LightGBM (step 8) dan model baseline (step 9) juga sama caranya:

```python
joblib.dump(models, 'lightgbm_models.pkl')          # 27 model GA-LightGBM, key: (komoditas, horizon)
joblib.dump(baseline_models, 'baseline_models.pkl')  # model default + gridsearch, key: (label, komoditas, horizon)
```

---

## 5. Feature Engineering (di level residual)

> ℹ️ **Catatan:** proposal 1.3 sebenernya eksplisit menyebutkan fitur "penanda periode Ramadan dan hari besar keagamaan" sebagai bagian dari petunjuk model — tapi berdasarkan keputusan kamu, fitur ini **sengaja tidak diimplementasikan** di workflow ini untuk simplifikasi. Kalau nanti ditanya dosen pembimbing kenapa fitur ini gak ada padahal disebut di proposal, siapin jawaban singkat (misal: dianggap sudah cukup terwakili oleh `month_sin`/`month_cos` dan `seasonal_annual` dari MSTL, atau kompleksitas implementasi kalender Hijriah dianggap di luar prioritas utama penelitian).

Manual pakai pandas (`shift()`/`rolling()`) — bukan library tambahan, biar transparan dan gampang dijelasin. Dibungkus jadi satu fungsi `build_features()` yang dipanggil di step ini DAN di step 13 (rolling forecast) — supaya logic-nya gak pernah ketulis beda antara training vs inference (baca catatan di step 13).

```python
def build_features(df, col):
    """Satu fungsi feature engineering — dipanggil di step 5 (training)
    DAN step 13 (inference/rolling forecast), supaya logic shift/rolling
    gak pernah kepeleset beda antara training vs production."""
    for lag in [1, 7, 14, 30]:
        df[f'{col}_lag{lag}'] = df[f'{col}_residual'].shift(lag)
    for window in [7, 30]:
        # shift(1) DULU sebelum rolling — biar window gak include hari ini
        # sendiri (kalau enggak, ini data leakage: pakai info hari ini buat
        # bikin fitur yang mprediksi target hari ini juga)
        df[f'{col}_roll_mean{window}'] = df[f'{col}_residual'].shift(1).rolling(window).mean()
        df[f'{col}_roll_std{window}'] = df[f'{col}_residual'].shift(1).rolling(window).std()
    return df

for col in commodity_cols:
    df = build_features(df, col)

# fitur kalender — cyclical encoding biar Desember & Januari "keliatan deket"
# ke model (bukan dianggap beda jauh kayak encoding angka biasa 12 vs 1)
df['day_of_week'] = df['tanggal'].dt.dayofweek
df['month_sin'] = np.sin(2*np.pi*df['tanggal'].dt.month/12)
df['month_cos'] = np.cos(2*np.pi*df['tanggal'].dt.month/12)
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

## 7. GA Hyperparameter Optimization

Fitness function pakai **10-Fold Cross-Validation** untuk cari kombinasi `num_leaves`, `max_depth`, `learning_rate`, `min_child_samples`, `subsample` terbaik. Proposal 1.3 sudah secara eksplisit menetapkan K-Fold CV untuk tahap pencarian GA ini (terpisah dari Time Series Split yang dipakai khusus untuk evaluasi model final di step 9) — jadi ini **bukan lagi item diskusi terbuka ke dosen pembimbing**, sudah jadi keputusan desain yang tertulis di proposal. Cukup dicatat di BAB 4/keterbatasan kalau memang masih relevan untuk dibahas potensi data leakage-nya secara teoretis.

```python
import lightgbm as lgb
from sklearn.model_selection import KFold
import numpy as np

def fitness_function(params, X, y):
    kf = KFold(n_splits=10, shuffle=True, random_state=42)
    rmses = []
    for train_idx, val_idx in kf.split(X):
        model = lgb.LGBMRegressor(**params)
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        pred = model.predict(X.iloc[val_idx])
        rmse = np.sqrt(np.mean((y.iloc[val_idx] - pred) ** 2))
        rmses.append(rmse)
    return np.mean(rmses)  # ini yang GA minimalkan

# Jalankan GA (pakai library deap atau pygad) — populasi → seleksi →
# crossover → mutasi, ulangi per komoditas × per horizon (27 proses pencarian,
# sesuai proposal 1.4: "Pencarian dilakukan untuk setiap pasangan komoditas
# dan jangka waktu, sehingga menghasilkan 27 proses pencarian")
```

---

## 8. Training Model Final per Komoditas × Horizon

```python
models = {}
for col in commodity_cols:
    for h in horizons:
        X_train = df[feature_cols_for(col)].dropna()
        y_train = df.loc[X_train.index, f'{col}_target_h{h}']
        model = lgb.LGBMRegressor(**best_params_from_GA[col][h])
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
        model_default = lgb.LGBMRegressor()  # tanpa tuning
        model_default.fit(X_train, y_train)
        baseline_models[('default', col, h)] = model_default

        # (3) LightGBM manual/grid search (one-by-one) — pembanding "penyetelan
        #     sulit direproduksi" yang disebut di latar belakang proposal
        param_grid = {
            'num_leaves': [15, 31, 63],
            'max_depth': [3, 5, 7, -1],
            'learning_rate': [0.01, 0.05, 0.1],
        }
        gs = GridSearchCV(lgb.LGBMRegressor(), param_grid, cv=10, scoring='neg_root_mean_squared_error')
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

## 11. Proyeksi Laju Kenaikan (2-3 Tahun)

Dasarnya ada di proposal 1.5 (Manfaat poin 2 — "acuan proyeksi laju kenaikan harga serta rentang ketidakpastian" buat petani/pelaku agribisnis) dan 1.7 (SDG 12 — proyeksi laju kenaikan bantu petani nyusun strategi pola tanam & waktu jual). Bukan pakai LightGBM — cukup ekstrapolasi trend model dari step 4.

```python
n_tahun_kedepan = 3

for col in commodity_cols:
    harga_awal = df[col].iloc[0]
    harga_akhir = df[col].iloc[-1]
    n_tahun_historis = (df['tanggal'].iloc[-1] - df['tanggal'].iloc[0]).days / 365

    cagr = (harga_akhir / harga_awal) ** (1 / n_tahun_historis) - 1

    time_idx_proyeksi = df['time_idx'].iloc[-1] + (365 * n_tahun_kedepan)
    trend_proyeksi = trend_models[col].predict([[time_idx_proyeksi]])[0]

    print(f"{col}: CAGR historis={cagr*100:.2f}%/tahun, "
          f"proyeksi trend {n_tahun_kedepan} tahun ke depan={trend_proyeksi:,.0f}")
```

---

## 12. Early Warning System Bulanan

> ⚠️ **Perbaikan logika:** versi sebelumnya cuma menghitung z-score dari %perubahan harga **aktual** historis — ini murni deteksi anomali statistik, tidak pernah membandingkan **prediksi vs realisasi** padahal itu yang eksplisit dijanjikan di Ringkasan Sistem (0) dan "Alur EWS" versi lama sendiri. Proposal 1.4 juga bilang ambang batas harus **bisa dikonfigurasi pengguna** (bukan hardcode `threshold_z=1.5`).

```python
def hitung_ews(df_bulanan, col, model_h30, threshold_z=1.5):
    # 1) Prediksi H+30 (dari model GA-LightGBM) dikonversi ke skala bulanan
    df_bulanan[f'{col}_pred_pct_mom'] = df_bulanan[f'{col}_pred_h30'].pct_change() * 100

    # 2) Realisasi aktual bulanan
    df_bulanan[f'{col}_actual_pct_mom'] = df_bulanan[col].pct_change() * 100

    # 3) Selisih antara realisasi dan prediksi — ini komponen "bandingkan prediksi
    #    vs realisasi" yang hilang di versi sebelumnya
    df_bulanan[f'{col}_deviation'] = (
        df_bulanan[f'{col}_actual_pct_mom'] - df_bulanan[f'{col}_pred_pct_mom']
    )

    # 4) Ambang batas statistik dari historical mean/std (threshold_z bisa
    #    di-override lewat parameter fungsi -> user-configurable di UI aplikasi)
    mean_hist = df_bulanan[f'{col}_actual_pct_mom'].mean()
    std_hist = df_bulanan[f'{col}_actual_pct_mom'].std()
    df_bulanan[f'{col}_z_score'] = (df_bulanan[f'{col}_actual_pct_mom'] - mean_hist) / std_hist

    def get_alert_level(z, deviation):
        if pd.isna(z):
            return "-"
        if z > 2:
            return "Kritis — kenaikan ekstrem"
        elif z > threshold_z:
            return "Warning — kenaikan signifikan"
        elif z > 1:
            return "Waspada — mulai menyimpang"
        return "Normal"

    df_bulanan[f'{col}_alert'] = df_bulanan.apply(
        lambda row: get_alert_level(row[f'{col}_z_score'], row[f'{col}_deviation']), axis=1
    )
    return df_bulanan
```

**Alur EWS (revisi):** resample data ke bulanan → ambil prediksi H+30 dari model GA-LightGBM (step 8) dan realisasi aktual → hitung deviasi realisasi vs prediksi **dan** z-score dari ambang batas statistik historis (threshold dapat dikonfigurasi pengguna) → trigger alert kalau menyimpang di salah satu/kedua kriteria. Status bersifat indikatif, hanya peringatan visual di aplikasi, tanpa notifikasi (sesuai proposal 1.4).

---

## 13. Rolling One-Step Forecast (Deployment/Inference)

> ⚠️ **Tambahan wajib — hilang di semua versi sebelumnya.** Proposal 1.3 menyebut "Rolling One-Step Forecast" sebagai salah satu metode, dan 1.4 modul "Peramalan Jangka Pendek" bilang model "dapat digunakan berulang kali setiap ada harga baru yang masuk tanpa perlu pelatihan ulang" — tapi belum pernah ada implementasi konkretnya di workflow. Ini bukan tahap training baru, ini tahap **inference/deployment** setelah model H+1/H+7/H+30 (step 8) sudah final.

**Poin krusial yang wajib dijelaskan di BAB 3/4:** ini beda dari *recursive forecasting*. Recursive forecasting bahaya karena prediksi model dipakai lagi sebagai input prediksi berikutnya (error numpuk) — makanya proposal kamu sengaja pilih Direct Multi-Horizon (step 6) untuk menghindari itu. Rolling one-step forecast **tidak** begitu: yang berubah tiap hari cuma *kapan model dipanggil ulang*, bukan sumber datanya. Lag/rolling features selalu dihitung ulang dari **harga aktual** yang baru masuk, bukan dari hasil prediksi model sebelumnya.

```python
import joblib

trend_models = joblib.load('trend_models.pkl')

# Rolling one-step forecast — AMAN karena lag features selalu dari data AKTUAL,
# bukan dari prediksi model sebelumnya (beda dengan recursive forecasting)
def rolling_forecast_h1(model_h1, col, df_history, tanggal_baru, harga_aktual_baru):
    # 1) data baru masuk sebagai OBSERVASI AKTUAL, bukan hasil prediksi
    df_history.loc[len(df_history)] = {'tanggal': tanggal_baru, col: harga_aktual_baru}

    # 2) recompute trend + residual pakai data aktual terbaru
    time_idx_baru = df_history['time_idx'].iloc[-1] + 1
    trend_baru = trend_models[col].predict([[time_idx_baru]])[0]
    df_history.loc[df_history.index[-1], f'{col}_residual'] = harga_aktual_baru - trend_baru

    # 3) pakai FUNGSI YANG SAMA PERSIS dari step 5 (build_features), bukan
    #    ditulis ulang manual di sini — ini yang jaga konsistensi shift()/
    #    rolling() antara training vs inference, tanpa perlu library tambahan
    df_history = build_features(df_history, col)

    features = df_history[feature_cols_for(col)].iloc[[-1]]

    # 4) prediksi H+1 pakai model yang SUDAH dilatih sekali (tanpa retrain,
    #    sesuai proposal 1.4: "tidak melakukan pelatihan ulang secara otomatis")
    pred_residual = model_h1.predict(features)[0]
    pred_harga = pred_residual + trend_baru  # balik dari residual ke skala harga

    return pred_harga

# Pola yang sama berlaku untuk model H+7 dan H+30 — bedanya cuma target
# kolom yang diprediksi, mekanismenya (recompute feature pakai build_features
# yang sama, tanpa retrain) identik untuk ketiga horizon.
```

**Dua pitfall yang wajib disebut di BAB 4 (keterbatasan):**

1. **Trend extrapolation drift.** `trend_models` (step 4) itu model `LinearRegression` yang di-fit di atas trend hasil MSTL, bukan trend mentah — tapi sifat ekstrapolasinya tetap sama: makin jauh rolling forecast berjalan dari akhir periode training, makin jauh pula ekstrapolasi linear-nya dari range yang pernah dilihat model, akurasi trend component berpotensi menurun kalau model gak pernah di-refresh. Karena proposal 1.4 eksplisit menyatakan tidak ada retraining otomatis/terjadwal, ini jadi asumsi yang harus dinyatakan eksplisit: rolling forecast valid untuk horizon deployment yang tidak terlalu jauh dari akhir data training, pembaruan model dilakukan manual (sesuai proposal).
2. **Konsistensi feature pipeline.** Fungsi `build_features()` di step 5 dan step 13 harus BENERAN fungsi yang sama (di-import/reuse, bukan copy-paste ke file lain) — kalau kamu kerja di notebook terpisah buat deployment, pastiin `build_features` didefinisiin di satu file/module yang di-import di kedua tempat, jangan retype manual. Ini sumber leakage paling sering kejadian di praktik, bukan soal "rolling"-nya itu sendiri.

---

## Urutan Eksekusi Ringkas

```
1.  Load raw data (2.039 baris × 10 kolom)
2.  Interpolasi missing value (time-based, ISI bukan drop) → tetap 2.039 baris
3.  ADF test per komoditas
4.  Detrend via MSTL decomposition (periods=(7, 365): weekly + annual) → fit LinearRegression di atas trend MSTL untuk ekstrapolasi → simpan trend_models
5.  Feature engineering di level residual pakai fungsi `build_features()` (lag, rolling, cyclical) — reusable, dipakai lagi di step 13
6.  Setup target per horizon (H+1, H+7, H+30) — direct, bukan recursive
7.  GA optimasi hyperparameter (fitness = 10-Fold CV RMSE) — 27 proses pencarian
8.  Training model final GA-LightGBM per komoditas × horizon (27 model)
9.  Training 3 model pembanding: naive, LightGBM default, LightGBM grid/manual search
10. Evaluasi (MAE/RMSE/R²/MAPE) walk-forward expanding window, 4 model dibandingkan
11. Proyeksi laju kenaikan 2-3 tahun (CAGR + ekstrapolasi trend, bukan LightGBM)
12. Early warning system bulanan (prediksi H+30 vs realisasi + threshold z-score, user-configurable)
13. Rolling one-step forecast untuk deployment (model dipakai ulang tiap ada data aktual baru, tanpa retrain)
```

## Catatan Penting yang Jangan Lupa

- **Jangan** paksa LightGBM prediksi nilai eksak untuk horizon 2-3 tahun — itu tugas trend model (step 11)
- **MSTL cuma alat decomposition, bukan forecasting model** — trend hasil MSTL gak bisa diekstrapolasi langsung, wajib fit model kedua (`LinearRegression`) di atasnya (step 4) buat kebutuhan proyeksi di step 11 & 13
- **`periods=(7, 365)` dipilih supaya weekly & annual seasonality kepisah eksplisit** — jangan cuma pakai `period=7` doang, karena itu berisiko ngukur artefak interpolasi (612/2039 tanggal kosong yang diisi punya pola fixed tiap akhir pekan), bukan sinyal pasar asli
- **Cuma ~5,6 siklus tahunan** (2039 baris ÷ 365) buat estimasi seasonal_annual — di bawah rekomendasi ideal, sebutkan sebagai keterbatasan di BAB 4
- **Jangan** drop baris missing value — proposal eksplisit minta diisi (interpolasi), baris final tetap 2.039
- **Jangan** pakai mean imputation untuk data bertrend
- **Jangan lupa** 3 model pembanding (naive, default, grid/manual search) di step 9-10 — dibutuhkan untuk menjawab rumusan masalah #3 dan tujuan #3
- **Jangan lupa** EWS harus bandingkan prediksi H+30 vs realisasi aktual (step 12), bukan cuma anomali statistik dari data aktual saja
- K-Fold CV vs Time Series Split **sudah bukan item diskusi terbuka** — proposal sudah menetapkan: K-Fold untuk fitness GA, walk-forward/expanding window untuk evaluasi final
- Model presisi itu **per komoditas × per horizon** = 9 × 3 = **27 model GA-LightGBM**, plus baseline (naive tanpa training, + 2×27 model pembanding lain)
- **Rolling one-step forecast ≠ recursive forecasting** — lag/rolling features di rolling forecast (step 13) selalu dihitung dari harga **aktual** baru, bukan dari hasil prediksi model sebelumnya. Ini poin yang wajib ditegaskan di BAB 3 supaya reviewer gak salah kira kamu pakai recursive (yang justru dihindari lewat Direct Multi-Horizon di step 6)
- Di luar scope file ini: 5 fitur aplikasi web (Dashboard Harga, Eksplorasi Data Historis, Pelatihan & Optimasi Model, Prediksi Harga Interaktif, Early Warning System) — perlu workflow terpisah untuk lapisan aplikasi/backend-frontend
