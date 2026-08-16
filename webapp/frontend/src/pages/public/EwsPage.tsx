import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor, statusStyle } from "../../lib/palette";
import { directionClass, directionOf, formatMonth, formatNumber, formatPercent } from "../../lib/format";
import { ErrorState, Loading, Notice, StatusBadge } from "../../components/ui";
import type { AlertLevel, EwsItem, EwsResponse } from "../../lib/types";

const LEVEL_ORDER: AlertLevel[] = ["kritis", "warning", "waspada", "normal", "tidak_tersedia"];

export function EwsPage() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const ews = useQuery({
    queryKey: ["ews"],
    queryFn: () => api.get<EwsResponse>("/api/ews?months=12"),
  });

  if (ews.isLoading) return <Loading />;
  if (ews.isError) return <ErrorState error={ews.error} onRetry={() => ews.refetch()} />;
  if (!ews.data) return null;

  const counts = LEVEL_ORDER.reduce<Record<string, number>>((acc, level) => {
    acc[level] = ews.data.items.filter((item) => item.latest?.level === level).length;
    return acc;
  }, {});

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Sistem peringatan dini</span>
        <h1 className="page-title">Peringatan Dini Bulanan</h1>
        <p className="lede">
          Perbandingan perubahan harga bulanan realisasi terhadap prediksi H+30, disertai
          z-score terhadap pola historis. Ambang batas dapat disesuaikan oleh admin.
        </p>
      </header>

      {!ews.data.has_prediction_component ? (
        <Notice tone="warning" title="Komponen perbandingan prediksi belum aktif">
          {ews.data.note}
        </Notice>
      ) : null}

      <section className="row-wrap" style={{ gap: "var(--space-3)" }}>
        {LEVEL_ORDER.map((level) => {
          const style = statusStyle(level);
          return (
            <div key={level} className="card" style={{ padding: "var(--space-3) var(--space-4)", minWidth: 150 }}>
              <div className="stack-2">
                <StatusBadge level={level} />
                <div className="num" style={{ fontSize: "var(--text-xl)", fontWeight: 600 }}>
                  {counts[level] ?? 0}
                </div>
                <span className="xs muted">{style.description}</span>
              </div>
            </div>
          );
        })}
      </section>

      <section className="stack-4">
        <h2 className="section-title">Status per komoditas</h2>
        <div className="stack-3">
          {ews.data.items.map((item) => (
            <CommodityEwsRow
              key={item.commodity.code}
              item={item}
              expanded={expanded === item.commodity.code}
              onToggle={() =>
                setExpanded((current) =>
                  current === item.commodity.code ? null : item.commodity.code
                )
              }
            />
          ))}
        </div>
      </section>

      <p className="xs muted" style={{ maxWidth: "76ch" }}>
        Status bersifat indikatif dan bukan keputusan kebijakan. Peringatan hanya
        ditampilkan secara visual di dalam aplikasi — tidak ada notifikasi keluar berupa
        email, pesan singkat, maupun push notification.
      </p>
    </div>
  );
}

function CommodityEwsRow({
  item,
  expanded,
  onToggle,
}: {
  item: EwsItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const latest = item.latest;

  return (
    <div className="card-flush">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        style={{
          width: "100%",
          background: "transparent",
          border: 0,
          padding: "var(--space-4)",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div className="row-between">
          <div className="row" style={{ gap: "var(--space-3)" }}>
            <span
              aria-hidden="true"
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                background: commodityColor(item.commodity),
                flex: "none",
              }}
            />
            <div className="stack-1">
              <span style={{ fontWeight: 600 }}>{item.commodity.name}</span>
              <span className="xs muted">
                Periode terakhir: {latest ? formatMonth(latest.period_month) : "—"}
              </span>
            </div>
          </div>

          <div className="row-wrap" style={{ gap: "var(--space-5)" }}>
            <div className="stack-1" style={{ textAlign: "right" }}>
              <span className="eyebrow">Realisasi MoM</span>
              <span
                className={`num small ${directionClass(directionOf(latest?.actual_pct_mom))}`}
                style={{ fontWeight: 600 }}
              >
                {formatPercent(latest?.actual_pct_mom, 2, true)}
              </span>
            </div>
            <div className="stack-1" style={{ textAlign: "right" }}>
              <span className="eyebrow">Z-score</span>
              <span className="num small" style={{ fontWeight: 600 }}>
                {formatNumber(latest?.z_score, 2)}
              </span>
            </div>
            <StatusBadge level={latest?.level ?? "tidak_tersedia"} />
          </div>
        </div>
      </button>

      {expanded ? (
        <div style={{ borderTop: "1px solid var(--rule)", padding: "var(--space-4)" }}>
          <div className="stack-3">
            <div className="row-wrap xs muted" style={{ gap: "var(--space-4)" }}>
              <span>Ambang waspada: z &gt; {item.thresholds.threshold_waspada}</span>
              <span>Warning: z &gt; {item.thresholds.threshold_warning}</span>
              <span>Kritis: z &gt; {item.thresholds.threshold_kritis}</span>
            </div>

            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Bulan</th>
                    <th className="right">Realisasi MoM</th>
                    <th className="right">Prediksi H+30 MoM</th>
                    <th className="right">Deviasi</th>
                    <th className="right">Z-score</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {[...item.rows].reverse().map((row) => (
                    <tr key={row.period_month}>
                      <td className="num">{formatMonth(row.period_month)}</td>
                      <td className={`num right ${directionClass(directionOf(row.actual_pct_mom))}`}>
                        {formatPercent(row.actual_pct_mom, 2, true)}
                      </td>
                      <td className="num right">
                        {row.has_prediction ? (
                          formatPercent(row.predicted_pct_mom, 2, true)
                        ) : (
                          <span className="muted">belum ada</span>
                        )}
                      </td>
                      <td className="num right">
                        {row.deviation != null ? formatPercent(row.deviation, 2, true) : "—"}
                      </td>
                      <td className="num right">{formatNumber(row.z_score, 2)}</td>
                      <td>
                        <StatusBadge level={row.level} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
