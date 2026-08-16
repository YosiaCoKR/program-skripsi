import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor } from "../../lib/palette";
import {
  directionClass,
  directionOf,
  formatDateLong,
  formatDateShort,
  formatNumber,
  formatPercent,
  formatRupiah,
} from "../../lib/format";
import { PriceChart, type ChartSeries } from "../../components/charts/PriceChart";
import { ErrorState, Loading, MetricGrid, Segmented, EmptyState } from "../../components/ui";
import type {
  AccuracyResponse,
  CommodityDetailResponse,
  Horizon,
  PredictionView,
} from "../../lib/types";

const RANGES = [
  { value: "30d", label: "30 hari" },
  { value: "90d", label: "90 hari" },
  { value: "1y", label: "1 tahun" },
  { value: "all", label: "Semua" },
];

export function CommodityDetailPage() {
  const { code = "" } = useParams();
  const [range, setRange] = useState("90d");
  const [accuracyHorizon, setAccuracyHorizon] = useState<Horizon>(1);
  const [view, setView] = useState<"grafik" | "tabel">("grafik");

  const detail = useQuery({
    queryKey: ["commodity", code, range],
    queryFn: () => api.get<CommodityDetailResponse>(`/api/commodities/${code}?range=${range}`),
    enabled: Boolean(code),
  });

  const accuracy = useQuery({
    queryKey: ["accuracy", code, accuracyHorizon],
    queryFn: () =>
      api.get<AccuracyResponse>(`/api/commodities/${code}/accuracy?horizon=${accuracyHorizon}`),
    enabled: Boolean(code),
  });

  if (detail.isLoading) return <Loading />;
  if (detail.isError) return <ErrorState error={detail.error} onRetry={() => detail.refetch()} />;
  if (!detail.data) return null;

  const { commodity, series, predictions, statistics, latest_data_date } = detail.data;
  const color = commodityColor(commodity);

  // Prediksi digambar sebagai satu deret putus-putus yang menyambung dari
  // titik aktual terakhir. Ketiga horizon ditampilkan bersama karena
  // semuanya berbasis tanggal yang sama.
  const forecastPoints = predictions
    .filter((p) => p.available && p.target_date && p.predicted_price != null)
    .map((p) => ({
      date: p.target_date as string,
      value: p.predicted_price as number,
      lower: p.lower_bound ?? null,
      upper: p.upper_bound ?? null,
    }))
    .sort((a, b) => a.date.localeCompare(b.date));

  const chartSeries: ChartSeries[] = [
    {
      key: commodity.code,
      label: commodity.name,
      color,
      points: series.map((p) => ({
        date: p.date,
        value: p.price,
        isInterpolated: p.is_interpolated,
      })),
      forecast: forecastPoints.length ? forecastPoints : undefined,
    },
  ];

  const changeDirection = directionOf(statistics.change_pct);

  return (
    <div className="stack-6">
      <header className="stack-3">
        <Link to="/" className="xs muted">
          ← Kembali ke dashboard
        </Link>
        <div className="row-between">
          <div className="stack-2">
            <span className="eyebrow">{commodity.family}</span>
            <h1 className="page-title">{commodity.name}</h1>
          </div>
          <div className="stack-1" style={{ textAlign: "right" }}>
            <span className="eyebrow">Harga terakhir</span>
            <span className="price-hero">{formatRupiah(statistics.last)}</span>
            <span className="xs muted">{formatDateLong(latest_data_date)}</span>
          </div>
        </div>
      </header>

      <section className="card stack-4">
        <div className="row-between">
          <h2 className="section-title">Pergerakan harga &amp; prediksi</h2>
          <div className="row-wrap">
            <Segmented value={range} options={RANGES} onChange={setRange} ariaLabel="Rentang waktu" />
            <Segmented
              value={view}
              options={[
                { value: "grafik" as const, label: "Grafik" },
                { value: "tabel" as const, label: "Tabel" },
              ]}
              onChange={setView}
              ariaLabel="Tampilan data"
            />
          </div>
        </div>

        {view === "grafik" ? (
          <PriceChart
            series={chartSeries}
            height={360}
            lastActualDate={latest_data_date}
            showLegend={false}
            yLabel="Rp/kg"
          />
        ) : (
          <SeriesTable points={series} />
        )}

        <div className="panel">
          <MetricGrid
            metrics={[
              { label: "Terendah", value: formatRupiah(statistics.min) },
              { label: "Tertinggi", value: formatRupiah(statistics.max) },
              { label: "Rata-rata", value: formatRupiah(statistics.mean) },
              {
                label: "Perubahan periode",
                value: formatPercent(statistics.change_pct, 2, true),
              },
              {
                label: "Titik interpolasi",
                value: `${statistics.interpolated_count ?? 0} titik`,
                hint: `${formatPercent(statistics.interpolated_pct, 1)} dari periode ini`,
              },
              { label: "Jumlah data", value: `${formatNumber(statistics.count)} hari` },
            ]}
          />
          <p className={`xs ${directionClass(changeDirection)}`} style={{ marginTop: "var(--space-3)" }}>
            Selama periode yang ditampilkan, harga bergerak dari{" "}
            {formatRupiah(statistics.first)} menjadi {formatRupiah(statistics.last)}.
          </p>
        </div>
      </section>

      <section className="stack-4">
        <h2 className="section-title">Prediksi per jangka waktu</h2>
        <div className="grid grid-3">
          {predictions.map((prediction) => (
            <PredictionCard key={prediction.horizon} prediction={prediction} currentPrice={statistics.last} />
          ))}
        </div>
      </section>

      <section className="card stack-4">
        <div className="row-between">
          <div className="stack-1">
            <h2 className="section-title">Riwayat akurasi</h2>
            <p className="small muted" style={{ maxWidth: "62ch" }}>
              Perbandingan prediksi masa lalu dengan realisasi aktual. Ini bukti empiris
              seberapa bisa dipercaya angka prediksi di atas.
            </p>
          </div>
          <Segmented
            value={accuracyHorizon}
            options={[
              { value: 1 as Horizon, label: "Harian" },
              { value: 7 as Horizon, label: "Mingguan" },
              { value: 30 as Horizon, label: "Bulanan" },
            ]}
            onChange={setAccuracyHorizon}
            ariaLabel="Horizon riwayat akurasi"
          />
        </div>

        {accuracy.isLoading ? <Loading label="Memuat riwayat akurasi…" /> : null}
        {accuracy.data && accuracy.data.items.length === 0 ? (
          <EmptyState
            title="Belum ada riwayat akurasi"
            description="Riwayat muncul setelah model menghasilkan prediksi dan tanggal targetnya sudah terlewati sehingga realisasi aktualnya tersedia."
          />
        ) : null}

        {accuracy.data && accuracy.data.items.length > 0 ? (
          <div className="stack-4">
            <MetricGrid
              metrics={[
                { label: "Jumlah pasangan", value: formatNumber(accuracy.data.summary.count) },
                { label: "MAE realisasi", value: formatRupiah(accuracy.data.summary.mae) },
                { label: "MAPE realisasi", value: formatPercent(accuracy.data.summary.mape, 2) },
              ]}
            />
            <div className="table-wrap" style={{ maxHeight: 340, overflowY: "auto" }}>
              <table className="data">
                <thead>
                  <tr>
                    <th>Tanggal target</th>
                    <th className="right">Prediksi</th>
                    <th className="right">Aktual</th>
                    <th className="right">Selisih</th>
                    <th className="right">Selisih %</th>
                  </tr>
                </thead>
                <tbody>
                  {accuracy.data.items.map((item) => (
                    <tr key={`${item.base_date}-${item.target_date}`}>
                      <td className="num">{formatDateShort(item.target_date)}</td>
                      <td className="num right">{formatRupiah(item.predicted_price)}</td>
                      <td className="num right">{formatRupiah(item.actual_price)}</td>
                      <td className={`num right ${directionClass(directionOf(item.error))}`}>
                        {formatRupiah(item.error)}
                      </td>
                      <td className="num right">{formatPercent(item.error_pct, 2, true)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>

      <a
        className="btn"
        style={{ alignSelf: "flex-start" }}
        href={`/api/export/prices.csv?codes=${commodity.code}`}
      >
        Unduh data CSV
      </a>
    </div>
  );
}

function PredictionCard({
  prediction,
  currentPrice,
}: {
  prediction: PredictionView;
  currentPrice?: number;
}) {
  if (!prediction.available) {
    return (
      <div className="card stack-3">
        <div className="stack-1">
          <span className="eyebrow">{prediction.label}</span>
          <span className="small muted">{prediction.description}</span>
        </div>
        <div className="empty" style={{ padding: "var(--space-5)" }}>
          <span className="small">Model belum tersedia</span>
          <span className="xs">{prediction.reason}</span>
        </div>
      </div>
    );
  }

  const delta =
    currentPrice != null && prediction.predicted_price != null
      ? prediction.predicted_price - currentPrice
      : null;
  const direction = directionOf(delta);

  return (
    <div className="card stack-3">
      <div className="stack-1">
        <span className="eyebrow">{prediction.label}</span>
        <span className="xs muted">{formatDateLong(prediction.target_date)}</span>
      </div>

      <div className="stack-1">
        <span className="price-hero">{formatRupiah(prediction.predicted_price)}</span>
        {delta != null ? (
          <span className={`small num ${directionClass(direction)}`} style={{ fontWeight: 600 }}>
            {formatRupiah(delta)} dari harga terakhir
          </span>
        ) : null}
      </div>

      {prediction.lower_bound != null && prediction.upper_bound != null ? (
        <div className="stack-1">
          <span className="eyebrow">Rentang ketidakpastian</span>
          <span className="num small">
            {formatRupiah(prediction.lower_bound)} — {formatRupiah(prediction.upper_bound)}
          </span>
        </div>
      ) : null}

      <div className="panel stack-2">
        <span className="eyebrow">Akurasi model</span>
        {prediction.metrics ? (
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: "var(--space-2)" }}>
            <MetricPair label="MAE" value={formatRupiah(prediction.metrics.mae)} />
            <MetricPair label="RMSE" value={formatRupiah(prediction.metrics.rmse)} />
            <MetricPair label="MAPE" value={formatPercent(prediction.metrics.mape, 2)} />
            <MetricPair label="R²" value={formatNumber(prediction.metrics.r2, 2)} />
          </div>
        ) : (
          <span className="xs muted">Metrik evaluasi belum dicatat untuk model ini.</span>
        )}
        {prediction.model ? (
          <span className="xs muted">
            {prediction.model.algorithm} · dilatih {formatDateShort(prediction.model.trained_at)}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function MetricPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack-1">
      <span className="xs muted">{label}</span>
      <span className="num small" style={{ fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

function SeriesTable({ points }: { points: { date: string; price: number; is_interpolated: boolean }[] }) {
  const rows = [...points].reverse();
  return (
    <div className="table-wrap" style={{ maxHeight: 360, overflowY: "auto" }}>
      <table className="data">
        <thead>
          <tr>
            <th>Tanggal</th>
            <th className="right">Harga</th>
            <th>Sumber</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((point) => (
            <tr key={point.date}>
              <td className="num">{formatDateShort(point.date)}</td>
              <td className="num right">{formatRupiah(point.price)}</td>
              <td className="xs">
                {point.is_interpolated ? (
                  <span className="badge">Interpolasi</span>
                ) : (
                  <span className="muted">Survei PIHPS</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
