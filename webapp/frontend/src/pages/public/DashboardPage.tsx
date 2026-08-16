import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor, familyColor } from "../../lib/palette";
import { formatDateLong, formatRupiah } from "../../lib/format";
import { Sparkline } from "../../components/charts/Sparkline";
import { DeltaValue, ErrorState, Loading, Notice, Segmented, StatusBadge } from "../../components/ui";
import type { DashboardCard, DashboardResponse, Horizon, MetaResponse } from "../../lib/types";

const FAMILY_ORDER = ["Beras", "Bawang Merah", "Cabai Rawit"];

export function DashboardPage() {
  const [horizon, setHorizon] = useState<Horizon>(1);

  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: () => api.get<MetaResponse>("/api/meta"),
  });

  const dashboard = useQuery({
    queryKey: ["dashboard", horizon],
    queryFn: () => api.get<DashboardResponse>(`/api/dashboard?horizon=${horizon}`),
  });

  const horizonOptions =
    meta.data?.horizons.map((h) => ({ value: h.value, label: h.label })) ??
    ([
      { value: 1, label: "Harian" },
      { value: 7, label: "Mingguan" },
      { value: 30, label: "Bulanan" },
    ] as { value: Horizon; label: string }[]);

  const grouped = FAMILY_ORDER.map((family) => ({
    family,
    cards: dashboard.data?.cards.filter((card) => card.commodity.family === family) ?? [],
  })).filter((group) => group.cards.length > 0);

  const modelsMissing =
    meta.data !== undefined && meta.data.active_model_count < meta.data.expected_model_count;

  return (
    <div className="stack-6">
      <header className="stack-4">
        <div className="stack-2">
          <span className="eyebrow">Provinsi Daerah Istimewa Yogyakarta</span>
          <h1 className="page-title">Harga Pangan Hari Ini</h1>
          <p className="lede">
            Harga sembilan komoditas pangan dari survei Bank Indonesia (PIHPS), lengkap
            dengan prediksi jangka harian, mingguan, dan bulanan.
          </p>
        </div>

        <div className="row-between">
          <div className="row-wrap">
            <span className="label">Jangka prediksi</span>
            <Segmented
              value={horizon}
              options={horizonOptions}
              onChange={setHorizon}
              ariaLabel="Pilih jangka prediksi"
            />
          </div>

          <dl className="row-wrap" style={{ gap: "var(--space-5)" }}>
            <SummaryStat label="Data terakhir" value={formatDateLong(dashboard.data?.latest_data_date)} />
            <SummaryStat
              label="Perlu perhatian"
              value={`${dashboard.data?.attention_count ?? 0} dari 9`}
            />
            <SummaryStat
              label="Tanggal prediksi"
              value={formatDateLong(dashboard.data?.next_target_date)}
            />
          </dl>
        </div>
      </header>

      {modelsMissing ? (
        <Notice tone="warning" title="Model prediksi belum lengkap">
          Baru {meta.data?.active_model_count} dari {meta.data?.expected_model_count} model aktif
          (9 komoditas × 3 horizon). Kartu prediksi menampilkan status "belum tersedia" sampai
          artefak model didaftarkan lewat panel admin. Data harga historis tetap tampil normal.
        </Notice>
      ) : null}

      {dashboard.isLoading ? <Loading /> : null}
      {dashboard.isError ? <ErrorState error={dashboard.error} onRetry={() => dashboard.refetch()} /> : null}

      {grouped.map((group) => (
        <section key={group.family} className="family-group">
          <div className="family-heading">
            <span
              aria-hidden="true"
              style={{
                width: 12,
                height: 12,
                borderRadius: 2,
                background: familyColor(group.family),
                flex: "none",
              }}
            />
            <h2 className="section-title">{group.family}</h2>
            <span className="xs muted">{group.cards.length} komoditas</span>
          </div>

          <div className="grid grid-cards">
            {group.cards.map((card) => (
              <CommodityCard key={card.commodity.id} card={card} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack-1">
      <dt className="eyebrow">{label}</dt>
      <dd className="num small" style={{ fontWeight: 600 }}>
        {value}
      </dd>
    </div>
  );
}

function CommodityCard({ card }: { card: DashboardCard }) {
  const color = commodityColor(card.commodity);
  const prediction = card.prediction;

  return (
    <Link to={`/komoditas/${card.commodity.code}`} className="commodity-card">
      <div className="row-between" style={{ alignItems: "flex-start", gap: "var(--space-2)" }}>
        <div className="row" style={{ gap: "var(--space-2)", alignItems: "flex-start" }}>
          <span className="series-mark" style={{ background: color, marginTop: 5 }} aria-hidden="true" />
          <span style={{ fontWeight: 600, lineHeight: 1.25 }}>{card.commodity.name}</span>
        </div>
        <StatusBadge level={card.alert_level} />
      </div>

      <div className="stack-2">
        <div className="price-hero">{formatRupiah(card.current_price)}</div>
        <div className="row-between">
          <DeltaValue delta={card.delta} deltaPct={card.delta_pct} />
          <span className="xs muted">{card.commodity.unit}</span>
        </div>
      </div>

      <Sparkline
        values={card.sparkline}
        color={color}
        width={240}
        height={34}
        label={`Tren 30 hari ${card.commodity.name}`}
      />

      <div className="panel stack-1">
        <span className="eyebrow">Prediksi {prediction.label.toLowerCase()}</span>
        {prediction.available ? (
          <>
            <span className="num" style={{ fontWeight: 600, fontSize: "var(--text-md)" }}>
              {formatRupiah(prediction.predicted_price)}
            </span>
            <span className="xs muted">
              {prediction.metrics?.mape != null
                ? `MAPE model ${prediction.metrics.mape.toFixed(2)}%`
                : "Metrik akurasi belum tersedia"}
            </span>
          </>
        ) : (
          <span className="xs muted">Model belum tersedia</span>
        )}
      </div>
    </Link>
  );
}
