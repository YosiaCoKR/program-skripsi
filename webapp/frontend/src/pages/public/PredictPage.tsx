import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor } from "../../lib/palette";
import {
  directionClass,
  directionOf,
  formatDateLong,
  formatNumber,
  formatPercent,
  formatRupiah,
} from "../../lib/format";
import { PriceChart, type ChartSeries } from "../../components/charts/PriceChart";
import { EmptyState, ErrorState, Loading, MetricGrid, Notice, Segmented } from "../../components/ui";
import type {
  Commodity,
  Horizon,
  ModelComparisonItem,
  PredictionView,
  PricePoint,
} from "../../lib/types";

interface PredictResponse {
  commodity: Commodity;
  prediction: PredictionView;
  recent_series: PricePoint[];
  latest_data_date: string | null;
}

export function PredictPage() {
  const [code, setCode] = useState("cabai-rawit-merah");
  const [horizon, setHorizon] = useState<Horizon>(1);

  const commodities = useQuery({
    queryKey: ["commodities"],
    queryFn: () => api.get<{ items: Commodity[] }>("/api/commodities"),
    staleTime: Infinity,
  });

  const result = useQuery({
    queryKey: ["predict", code, horizon],
    queryFn: () => api.get<PredictResponse>(`/api/predictions?code=${code}&horizon=${horizon}`),
    enabled: Boolean(code),
  });

  const comparison = useQuery({
    queryKey: ["model-comparison"],
    queryFn: () =>
      api.get<{ items: ModelComparisonItem[]; available: boolean; note: string }>(
        "/api/models/comparison"
      ),
  });

  const prediction = result.data?.prediction;
  const commodity = result.data?.commodity;

  const chartSeries: ChartSeries[] = commodity
    ? [
        {
          key: commodity.code,
          label: commodity.name,
          color: commodityColor(commodity),
          points: (result.data?.recent_series ?? []).map((p) => ({
            date: p.date,
            value: p.price,
            isInterpolated: p.is_interpolated,
          })),
          forecast:
            prediction?.available && prediction.target_date && prediction.predicted_price != null
              ? [
                  {
                    date: prediction.target_date,
                    value: prediction.predicted_price,
                    lower: prediction.lower_bound ?? null,
                    upper: prediction.upper_bound ?? null,
                  },
                ]
              : undefined,
        },
      ]
    : [];

  const lastPrice = result.data?.recent_series.at(-1)?.price;
  const delta =
    lastPrice != null && prediction?.predicted_price != null
      ? prediction.predicted_price - lastPrice
      : null;

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Alat prediksi</span>
        <h1 className="page-title">Prediksi Harga Interaktif</h1>
        <p className="lede">
          Pilih komoditas dan jangka waktu untuk melihat prediksi harga beserta model
          yang menghasilkannya dan metrik akurasinya.
        </p>
      </header>

      <section className="card stack-4">
        <div className="row-wrap" style={{ gap: "var(--space-5)" }}>
          <div className="field" style={{ minWidth: 260 }}>
            <label htmlFor="pilih-komoditas">Komoditas</label>
            <select
              id="pilih-komoditas"
              className="select"
              value={code}
              onChange={(event) => setCode(event.target.value)}
            >
              {commodities.data?.items.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <span className="label">Jangka waktu</span>
            <Segmented
              value={horizon}
              options={[
                { value: 1 as Horizon, label: "Harian (H+1)" },
                { value: 7 as Horizon, label: "Mingguan (H+7)" },
                { value: 30 as Horizon, label: "Bulanan (H+30)" },
              ]}
              onChange={setHorizon}
              ariaLabel="Pilih jangka waktu prediksi"
            />
          </div>
        </div>

        {result.isLoading ? <Loading /> : null}
        {result.isError ? <ErrorState error={result.error} onRetry={() => result.refetch()} /> : null}

        {prediction && !prediction.available ? (
          <EmptyState
            title="Model untuk kombinasi ini belum tersedia"
            description={prediction.reason}
          />
        ) : null}

        {prediction?.available ? (
          <div className="stack-5">
            <div className="row-wrap" style={{ gap: "var(--space-7)", alignItems: "flex-end" }}>
              <div className="stack-1">
                <span className="eyebrow">Prediksi {prediction.label.toLowerCase()}</span>
                <span className="price-hero" style={{ fontSize: "var(--text-3xl)" }}>
                  {formatRupiah(prediction.predicted_price)}
                </span>
                <span className="small muted">untuk {formatDateLong(prediction.target_date)}</span>
              </div>

              {delta != null ? (
                <div className="stack-1">
                  <span className="eyebrow">Dibanding harga terakhir</span>
                  <span
                    className={`num ${directionClass(directionOf(delta))}`}
                    style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}
                  >
                    {formatRupiah(delta)}
                  </span>
                  <span className="xs muted">dari {formatRupiah(lastPrice)}</span>
                </div>
              ) : null}

              {prediction.lower_bound != null && prediction.upper_bound != null ? (
                <div className="stack-1">
                  <span className="eyebrow">Rentang ketidakpastian</span>
                  <span className="num small">
                    {formatRupiah(prediction.lower_bound)} — {formatRupiah(prediction.upper_bound)}
                  </span>
                </div>
              ) : null}
            </div>

            <PriceChart
              series={chartSeries}
              height={300}
              lastActualDate={result.data?.latest_data_date}
              showLegend={false}
              yLabel="Rp/kg"
            />

            <div className="panel stack-3">
              <h3 className="section-title" style={{ fontSize: "var(--text-base)" }}>
                Model yang dipakai
              </h3>
              {prediction.metrics ? (
                <MetricGrid
                  metrics={[
                    { label: "MAE", value: formatRupiah(prediction.metrics.mae) },
                    { label: "RMSE", value: formatRupiah(prediction.metrics.rmse) },
                    { label: "MAPE", value: formatPercent(prediction.metrics.mape, 2) },
                    { label: "R²", value: formatNumber(prediction.metrics.r2, 2) },
                  ]}
                />
              ) : (
                <span className="small muted">Metrik evaluasi belum dicatat untuk model ini.</span>
              )}

              {prediction.model ? (
                <details>
                  <summary className="small" style={{ cursor: "pointer" }}>
                    Hyperparameter hasil optimasi ({prediction.model.algorithm})
                  </summary>
                  <div className="table-wrap" style={{ marginTop: "var(--space-3)" }}>
                    <table className="data">
                      <thead>
                        <tr>
                          <th>Parameter</th>
                          <th className="right">Nilai</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(prediction.model.hyperparameters ?? {}).map(([key, value]) => (
                          <tr key={key}>
                            <td className="num">{key}</td>
                            <td className="num right">{String(value)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <section className="card stack-4">
        <div className="stack-1">
          <h2 className="section-title">Perbandingan model</h2>
          <p className="small muted" style={{ maxWidth: "68ch" }}>
            GA-LightGBM dibandingkan dengan tiga model pembanding berdasarkan evaluasi
            walk-forward expanding window. Nilai dirata-ratakan per algoritma dan horizon.
          </p>
        </div>

        {comparison.data?.available ? (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Algoritma</th>
                  <th>Horizon</th>
                  <th className="right">Jumlah model</th>
                  <th className="right">MAE</th>
                  <th className="right">RMSE</th>
                  <th className="right">MAPE</th>
                  <th className="right">R²</th>
                </tr>
              </thead>
              <tbody>
                {comparison.data.items.map((item) => (
                  <tr key={`${item.algorithm}-${item.horizon}`}>
                    <td>{item.algorithm}</td>
                    <td>{item.horizon_label}</td>
                    <td className="num right">{item.n_models}</td>
                    <td className="num right">{formatRupiah(item.mae)}</td>
                    <td className="num right">{formatRupiah(item.rmse)}</td>
                    <td className="num right">{formatPercent(item.mape, 2)}</td>
                    <td className="num right">{formatNumber(item.r2, 3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Notice tone="info" title="Perbandingan belum tersedia">
            {comparison.data?.note ??
              "Belum ada model yang terdaftar beserta metrik evaluasinya."}{" "}
            Tabel ini terisi otomatis setelah model GA-LightGBM dan model pembanding
            didaftarkan lewat panel admin.
          </Notice>
        )}
      </section>
    </div>
  );
}
