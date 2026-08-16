import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor } from "../../lib/palette";
import { directionClass, directionOf, formatDateLong, formatPercent, formatRupiah } from "../../lib/format";
import { ErrorState, Loading, Notice, Segmented } from "../../components/ui";
import type { ProjectionItem, ProjectionResponse } from "../../lib/types";

export function ProjectionPage() {
  const [years, setYears] = useState(3);

  const projection = useQuery({
    queryKey: ["projections", years],
    queryFn: () => api.get<ProjectionResponse>(`/api/projections?years=${years}`),
  });

  if (projection.isLoading) return <Loading />;
  if (projection.isError)
    return <ErrorState error={projection.error} onRetry={() => projection.refetch()} />;
  if (!projection.data) return null;

  const maxGrowth = Math.max(
    ...projection.data.items.map((item) => Math.abs(item.total_growth_pct ?? 0)),
    1
  );

  return (
    <div className="stack-6">
      <header className="stack-4">
        <div className="stack-2">
          <span className="eyebrow">Perencanaan jangka panjang</span>
          <h1 className="page-title">Proyeksi Laju Kenaikan</h1>
          <p className="lede">
            Perkiraan laju kenaikan harga dua sampai tiga tahun ke depan sebagai bahan
            perencanaan pola tanam dan waktu jual.
          </p>
        </div>

        <div className="row-wrap">
          <span className="label">Horizon proyeksi</span>
          <Segmented
            value={years}
            options={[
              { value: 2, label: "2 tahun" },
              { value: 3, label: "3 tahun" },
            ]}
            onChange={setYears}
            ariaLabel="Pilih horizon proyeksi"
          />
        </div>
      </header>

      <Notice tone="warning" title="Ini bukan prediksi harga presisi">
        {projection.data.disclaimer}
      </Notice>

      <section className="stack-3">
        {projection.data.items.map((item) => (
          <ProjectionRow key={item.commodity.code} item={item} maxGrowth={maxGrowth} />
        ))}
      </section>

      <section className="card stack-3">
        <h2 className="section-title">Cara membaca angka ini</h2>
        <div className="stack-2 small secondary">
          <p>
            <strong>CAGR</strong> adalah laju pertumbuhan majemuk tahunan yang dihitung dari
            harga awal dan harga akhir data historis. Angka ini merangkum seberapa cepat harga
            tumbuh rata-rata per tahun.
          </p>
          <p>
            <strong>Proyeksi</strong> dihitung dari ekstrapolasi model trend, bukan dari model
            LightGBM. Memaksa LightGBM memprediksi nilai eksak untuk horizon tahunan adalah
            kesalahan metodologis — model tersebut dilatih untuk jangka 1, 7, dan 30 hari.
          </p>
          <p>
            <strong>Rentang</strong> melebar seiring jauhnya horizon karena ekstrapolasi linear
            makin jauh dari rentang data yang pernah dilihat model.
          </p>
        </div>
      </section>
    </div>
  );
}

function ProjectionRow({ item, maxGrowth }: { item: ProjectionItem; maxGrowth: number }) {
  const color = commodityColor(item.commodity);
  const growth = item.total_growth_pct ?? 0;
  const direction = directionOf(growth);
  const barWidth = Math.min(100, (Math.abs(growth) / maxGrowth) * 100);

  return (
    <div className="card stack-3">
      <div className="row-between">
        <div className="row" style={{ gap: "var(--space-3)" }}>
          <span
            aria-hidden="true"
            style={{ width: 10, height: 10, borderRadius: 2, background: color, flex: "none" }}
          />
          <div className="stack-1">
            <span style={{ fontWeight: 600 }}>{item.commodity.name}</span>
            <span className="xs muted">{item.commodity.family}</span>
          </div>
        </div>

        <div className="row-wrap" style={{ gap: "var(--space-6)" }}>
          <Stat label="Harga sekarang" value={formatRupiah(item.base_price)} />
          <Stat label="CAGR historis" value={formatPercent(item.cagr, 2, true)} />
          <Stat
            label={`Proyeksi ${item.horizon_years} tahun`}
            value={formatRupiah(item.projected_price)}
            className={directionClass(direction)}
          />
        </div>
      </div>

      <div className="stack-2">
        <div
          style={{
            height: 6,
            background: "var(--paper-inset)",
            borderRadius: 3,
            overflow: "hidden",
          }}
          role="img"
          aria-label={`Total pertumbuhan ${formatPercent(growth, 1)}`}
        >
          <div
            style={{
              width: `${barWidth}%`,
              height: "100%",
              background: color,
              borderRadius: 3,
            }}
          />
        </div>

        <div className="row-between xs muted">
          <span>
            Rentang: {formatRupiah(item.lower_bound)} — {formatRupiah(item.upper_bound)}
          </span>
          <span className="num">
            Total {formatPercent(growth, 1, true)} sampai {formatDateLong(item.target_date)}
          </span>
        </div>

        {item.method === "cagr_only" ? (
          <span className="xs muted">
            Model trend tidak tersedia; proyeksi dihitung dari CAGR saja.
          </span>
        ) : null}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  className,
}: {
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className="stack-1" style={{ textAlign: "right" }}>
      <span className="eyebrow">{label}</span>
      <span className={`num small ${className ?? ""}`} style={{ fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}
