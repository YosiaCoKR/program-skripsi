import { Fragment, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { formatDateShort, formatDateTime, formatDuration } from "../../lib/format";
import { ErrorState, Loading, Notice } from "../../components/ui";
import { RunStatus } from "./AdminHomePage";
import type { AdminOverview, ForecastRunRow } from "../../lib/types";

export function ForecastMonitorPage() {
  const queryClient = useQueryClient();
  const [baseDate, setBaseDate] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);

  const overview = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => api.get<AdminOverview>("/api/admin/overview"),
  });

  const runs = useQuery({
    queryKey: ["forecast-runs"],
    queryFn: () => api.get<{ items: ForecastRunRow[] }>("/api/admin/forecast-runs"),
  });

  const trigger = useMutation({
    mutationFn: () =>
      api.post<{ base_date: string; forecast: { status: string; predictions_count: number; message: string | null } }>(
        "/api/admin/forecast-runs",
        { base_date: baseDate || null }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["forecast-runs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
    },
  });

  const drift = overview.data?.drift;

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Inference</span>
        <h1 className="page-title">Monitor Rolling Forecast</h1>
        <p className="lede">
          Setiap eksekusi menghitung ulang trend, residual, dan fitur lag/rolling dari harga
          aktual terbaru, lalu memanggil model H+1, H+7, dan H+30 tanpa melatih ulang.
        </p>
      </header>

      {drift && (drift.level === "peringatan" || drift.level === "kritis") ? (
        <Notice tone={drift.level === "kritis" ? "critical" : "warning"} title="Indikator kesehatan model">
          Jarak data terakhir ke akhir periode training sudah {drift.days} hari (ambang
          peringatan {drift.warning_threshold} hari, kritis {drift.critical_threshold} hari).
          Ekstrapolasi komponen trend makin jauh dari rentang data yang pernah dilihat model.
        </Notice>
      ) : null}

      <section className="card stack-4">
        <h2 className="section-title">Jalankan ulang</h2>
        <p className="small muted" style={{ maxWidth: "70ch" }}>
          Eksekusi bersifat idempoten per tanggal basis — menjalankan ulang untuk tanggal
          yang sama akan menimpa prediksi lama, bukan menduplikasinya. Kosongkan tanggal
          untuk memakai data terakhir.
        </p>

        <div className="row-wrap" style={{ gap: "var(--space-4)", alignItems: "flex-end" }}>
          <div className="field">
            <label htmlFor="tanggal-basis">Tanggal basis</label>
            <input
              id="tanggal-basis"
              type="date"
              className="input"
              value={baseDate}
              onChange={(event) => setBaseDate(event.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => trigger.mutate()}
            disabled={trigger.isPending}
          >
            {trigger.isPending ? "Menjalankan…" : "Jalankan forecast"}
          </button>
        </div>

        {trigger.isError ? <ErrorState error={trigger.error} /> : null}

        {trigger.data ? (
          <Notice
            tone={trigger.data.forecast.predictions_count > 0 ? "success" : "warning"}
            title={`Eksekusi selesai — status ${trigger.data.forecast.status}`}
          >
            {trigger.data.forecast.predictions_count} prediksi tersimpan untuk tanggal basis{" "}
            {formatDateShort(trigger.data.base_date)}.
            {trigger.data.forecast.message ? (
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-xs)",
                  marginTop: "var(--space-2)",
                }}
              >
                {trigger.data.forecast.message}
              </pre>
            ) : null}
          </Notice>
        ) : null}
      </section>

      {runs.isLoading ? <Loading /> : null}
      {runs.isError ? <ErrorState error={runs.error} onRetry={() => runs.refetch()} /> : null}

      {runs.data ? (
        <section className="stack-3">
          <h2 className="section-title">Riwayat eksekusi</h2>

          {runs.data.items.length === 0 ? (
            <p className="small muted">Belum ada eksekusi tercatat.</p>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Tanggal basis</th>
                    <th>Status</th>
                    <th>Pemicu</th>
                    <th className="right">Prediksi</th>
                    <th className="right">Durasi</th>
                    <th>Mulai</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {runs.data.items.map((run) => (
                    <Fragment key={run.id}>
                      <tr>
                        <td className="num">{formatDateShort(run.base_date)}</td>
                        <td>
                          <RunStatus status={run.status} />
                        </td>
                        <td className="xs muted">{run.trigger_type}</td>
                        <td className="num right">{run.predictions_count}</td>
                        <td className="num right">{formatDuration(run.duration_seconds)}</td>
                        <td className="xs num">{formatDateTime(run.started_at)}</td>
                        <td className="right">
                          {run.error_message ? (
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost"
                              onClick={() => setExpanded(expanded === run.id ? null : run.id)}
                            >
                              {expanded === run.id ? "Tutup" : "Detail"}
                            </button>
                          ) : null}
                        </td>
                      </tr>
                      {expanded === run.id && run.error_message ? (
                        <tr>
                          <td colSpan={7} style={{ background: "var(--paper-sunken)" }}>
                            <pre
                              style={{
                                whiteSpace: "pre-wrap",
                                fontFamily: "var(--font-mono)",
                                fontSize: "var(--text-xs)",
                                color: "var(--ink-secondary)",
                                margin: 0,
                              }}
                            >
                              {run.error_message}
                            </pre>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
