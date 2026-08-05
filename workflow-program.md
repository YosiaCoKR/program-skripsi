# Workflow Pengerjaan Skripsi

## Optimasi Hyperparameter LightGBM Regressor Menggunakan Genetic Algorithm untuk Prediksi Harga Komoditas Beras, Bawang Merah, dan Cabai Rawit di Provinsi DIY

**NIM:** 535230117 | **Nama:** Yosia Sipahutar | **Dosen Pembimbing:** Ibu Lely Hiryanto, S.T., M.Sc., Ph.D

---

## 0. Ringkasan Sistem

Penelitian ini punya **3 output berbeda** yang saling terhubung, jangan dikerjain sebagai satu model tunggal:


| Output                 | Horizon              | Metode                           | Sifat                              |
|------------------------|----------------------|----------------------------------|------------------------------------|
| Prediksi harga presisi | 7 hari & 1 bulan | GA-LightGBM                      | Nilai eksak (Rp/kg)                |
| Proyeksi laju kenaikan | 2-3 tahun            | Trend model (statistik)          | Persentase/rate, bukan nilai eksak |
| Early warning system   | Bulanan              | Bandingkan prediksi vs realisasi | Deteksi anomali                    |


**Dataset:** Data harian harga 9 komoditas DIY dari Bank Indonesia (PIHPS), 2021-2026, 2039 baris → 1427 baris setelah preprocessing.

**9 komoditas (univariat, tiap komoditas diperlakukan terpisah):** Beras Kualitas Bawah I & II, Medium I & II, Super I & II, Bawang Merah Ukuran Sedang, Cabai Rawit Hijau & Merah.

---

## 1. Raw Data Collection

```python
import pandas as pd  
  
df = pd.read_csv('DATASET-BERAS.csv', parse_dates=['tanggal'])  
df = df.sort_values('tanggal').reset_index(drop=True)
```

---

## 2. Penanganan Missing Value

**Prinsip:** jangan drop (rusak kontinuitas lag features), jangan mean (rusak trend). Pakai interpolasi berbasis waktu.

```python
df = df.set_index('tanggal')  

# Time-based linear interpolation — isi gap proporsional ke jarak waktu,  
# preserve trend lokal (beda dengan mean yang pakai satu angka statis)  
df['harga'] = df['harga'].interpolate(method='time')  

df = df.reset_index()
```

**Aturan pemilihan metode:**


| Metode                       | Kapan dipakai                                                                                  |
|------------------------------|------------------------------------------------------------------------------------------------|
| `interpolate(method='time')` | Gap pendek 1-5 hari — default pilihan                                                        |
| Forward-fill (`ffill`)       | Gap karena hari libur pasar (harga "bertahan")                                                 |
| Mean/median                  | ❌ Jangan — merusak struktur temporal data bertrend                                         |
| Drop baris                   | Hanya kalau **seluruh baris** kosong (bukan hari observasi), bukan kalau sebagian kolom kosong |


Cek dulu apakah baris kosong di data kamu itu "hari tanpa observasi" (semua kolom kosong, wajar di-exclude) atau "missing value parsial" (sebagian kolom kosong, wajib diinterpolasi) — jangan disamaratakan treatment-nya.

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

## 4. Detrend (bukan differencing polos)

**Kenapa detrend, bukan differencing:** differencing tetap butuh reconstruct recursive (cumsum) yang error-nya numpuk di horizon panjang. Detrend memisahkan komponen trend (diekstrapolasi eksplisit sekali) dari residual (yang jadi tugas LightGBM).

```python
from sklearn.linear_model import LinearRegression  
import numpy as np  

df['time_idx'] = np.arange(len(df))  
trend_models = {}  

for col in commodity_cols:  
tm = LinearRegression().fit(df[['time_idx']], df[col])  
trend_models[col] = tm  
df[f'{col}_trend'] = tm.predict(df[['time_idx']])  
df[f'{col}_residual'] = df[col] - df[f'{col}_trend']
```

Simpan `trend_models` (pickle/joblib) — dipakai lagi di step 9 (proyeksi 2-3 tahun) dan step 10 (EWS).

---

## 5. Feature Engineering (di level residual)

```python
for col in commodity_cols:  
    for lag in [1, 7, 14, 30]:  
        df[f'{col}_lag{lag}'] = df[f'{col}_residual'].shift(lag)  
    for window in [7, 30]:  
        df[f'{col}_roll_mean{window}'] = df[f'{col}_residual'].shift(1).rolling(window).mean()  
        df[f'{col}_roll_std{window}'] = df[f'{col}_residual'].shift(1).rolling(window).std()  
  
df['day_of_week'] = df['tanggal'].dt.dayofweek  
df['month_sin'] = np.sin(2*np.pi*df['tanggal'].dt.month/12)  
df['month_cos'] = np.cos(2*np.pi*df['tanggal'].dt.month/12)
```

---

## 6. Setup Direct Multi-Horizon (H+1, H+7, H+30)

Model terpisah per horizon — bukan recursive (prediksi H+1 dipakai buat prediksi H+2, dst) karena itu bikin error numpuk.

```python
horizons = [1, 7, 30]  

for col in commodity_cols:  
for h in horizons:  
df[f'{col}_target_h{h}'] = df[f'{col}_residual'].shift(-h)
```

---

## 7. GA Hyperparameter Optimization

Fitness function pakai **10-Fold Cross-Validation** (sesuai sinopsis) untuk cari kombinasi `num_leaves`, `max_depth`, `learning_rate`, `min_child_samples`, `subsample` terbaik.

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
# crossover → mutasi, ulangi per komoditas × per horizon
```

> 
> **Catatan buat didiskusikan ke dosen pembimbing:** 10-Fold CV random bisa berpotensi data leakage untuk time series (fold validation bisa berisi data yang secara kronologis mendahului training-nya). Kalau sinopsis sudah fix, ini bisa jadi catatan di bab keterbatasan; kalau masih bisa direvisi, `TimeSeriesSplit`/blocked CV lebih aman.
> 

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

## 9. Evaluasi Model (MAE, RMSE, R²)

```python
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score  
  
for (col, h), model in models.items():  
    y_pred = model.predict(X_test[(col, h)])  
    mae = mean_absolute_error(y_test[(col, h)], y_pred)  
    rmse = np.sqrt(mean_squared_error(y_test[(col, h)], y_pred))  
    r2 = r2_score(y_test[(col, h)], y_pred)  
    print(f"{col} H+{h}: MAE={mae:.2f}, RMSE={rmse:.2f}, R²={r2:.4f}")
```

**Backtest untuk validasi (bukan cuma 1 titik):**

```python
from sklearn.model_selection import TimeSeriesSplit  

tscv = TimeSeriesSplit(n_splits=5)  
results = []  
for train_idx, test_idx in tscv.split(df.dropna()):  
# fit ulang trend_model + model_h di train_idx  
# evaluasi di test_idx, simpan MAE/RMSE/R² per fold  
pass  
# rata-ratakan hasil semua fold — ini yang dilaporkan di BAB 4, bukan 1 split doang
```

---

## 10. Proyeksi Laju Kenaikan (2-3 Tahun)

**Bukan pakai LightGBM** — cukup ekstrapolasi trend model dari step 4.

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

## 11. Early Warning System Bulanan

```python
def hitung_ews(df_bulanan, col, threshold_z=1.5):  
df_bulanan[f'{col}_pct_change_mom'] = df_bulanan[col].pct_change() * 100  

mean_hist = df_bulanan[f'{col}_pct_change_mom'].mean()  
std_hist = df_bulanan[f'{col}_pct_change_mom'].std()  

df_bulanan[f'{col}_z_score'] = (df_bulanan[f'{col}_pct_change_mom'] - mean_hist) / std_hist  

def get_alert_level(z):  
if pd.isna(z): return "-"  
if z > 2: return "Kritis — kenaikan ekstrem"  
elif z > threshold_z: return "Warning — kenaikan signifikan"  
elif z > 1: return "Waspada — mulai menyimpang"  
return "Normal"  

df_bulanan[f'{col}_alert'] = df_bulanan[f'{col}_z_score'].apply(get_alert_level)  
return df_bulanan
```

**Alur EWS:** resample data ke bulanan → hitung % perubahan MoM aktual → bandingkan ke threshold statistik (mean ± std historis komoditas tsb) sekaligus ke proyeksi laju kenaikan dari step 10 → trigger alert kalau nyimpang.

---

## Urutan Eksekusi Ringkas

```
1. Load raw data  
2. Interpolasi missing value (time-based, bukan mean/drop)  
3. ADF test per komoditas  
4. Detrend (pisah trend vs residual) → simpan trend_models  
5. Feature engineering di level residual (lag, rolling, cyclical)  
6. Setup target per horizon (H+1, H+7, H+30) — direct, bukan recursive  
7. GA optimasi hyperparameter (fitness = 10-Fold CV RMSE)  
8. Training model final per komoditas × horizon  
9. Evaluasi (MAE/RMSE/R²) + backtest TimeSeriesSplit multi-fold  
10. Proyeksi laju kenaikan 2-3 tahun (CAGR + ekstrapolasi trend, bukan LightGBM)  
11. Early warning system bulanan (bandingkan realisasi vs proyeksi + threshold z-score)
```

## Catatan Penting yang Jangan Lupa

- **Jangan** paksa LightGBM prediksi nilai eksak untuk horizon 2-3 tahun — itu tugas trend model (step 10)
- **Jangan** drop baris missing value kalau cuma sebagian kolom kosong
- **Jangan** pakai mean imputation untuk data bertrend
- **Diskusikan** ke Bu Lely soal 10-Fold CV vs TimeSeriesSplit untuk fitness function GA (potensi data leakage)
- Model itu **per komoditas × per horizon** — total kombinasi = 9 komoditas × 3 horizon = 27 model (atau kelompokkan horizon jadi grup kalau terlalu berat komputasi)

 
