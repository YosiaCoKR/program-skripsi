import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { statusStyle } from "../../lib/palette";
import { formatNumber } from "../../lib/format";
import { ErrorState, Loading, Notice, StatusBadge } from "../../components/ui";
import type { AlertLevel, EwsPreviewResponse, EwsSettingsResponse } from "../../lib/types";

const LEVELS: AlertLevel[] = ["normal", "waspada", "warning", "kritis"];

export function EwsConfigPage() {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<string>("global");
  const [waspada, setWaspada] = useState("1");
  const [warning, setWarning] = useState("1.5");
  const [kritis, setKritis] = useState("2");
  const [feedback, setFeedback] = useState<string | null>(null);

  const settings = useQuery({
    queryKey: ["ews-settings"],
    queryFn: () => api.get<EwsSettingsResponse>("/api/admin/ews/settings"),
  });

  // Isi form dengan nilai yang berlaku untuk cakupan terpilih.
  useEffect(() => {
    if (!settings.data) return;
    const source =
      scope === "global"
        ? settings.data.global
        : settings.data.overrides.find((item) => String(item.commodity_id) === scope) ??
          settings.data.global;

    if (source) {
      setWaspada(String(source.threshold_waspada));
      setWarning(String(source.threshold_warning));
      setKritis(String(source.threshold_kritis));
    }
  }, [settings.data, scope]);

  const thresholdPayload = {
    commodity_id: scope === "global" ? null : Number(scope),
    threshold_waspada: Number(waspada),
    threshold_warning: Number(warning),
    threshold_kritis: Number(kritis),
  };

  const ordered =
    Number(waspada) < Number(warning) && Number(warning) < Number(kritis);

  const preview = useQuery({
    queryKey: ["ews-preview", thresholdPayload],
    queryFn: () => api.post<EwsPreviewResponse>("/api/admin/ews/preview", thresholdPayload),
    enabled: ordered,
  });

  const save = useMutation({
    mutationFn: () => api.put("/api/admin/ews/settings", thresholdPayload),
    onSuccess: () => {
      setFeedback("Ambang batas tersimpan dan seluruh status EWS dihitung ulang.");
      queryClient.invalidateQueries({ queryKey: ["ews-settings"] });
      queryClient.invalidateQueries({ queryKey: ["ews"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const removeOverride = useMutation({
    mutationFn: (commodityId: number) => api.delete(`/api/admin/ews/settings/${commodityId}`),
    onSuccess: () => {
      setFeedback("Override dihapus. Komoditas kembali mengikuti ambang global.");
      setScope("global");
      queryClient.invalidateQueries({ queryKey: ["ews-settings"] });
      queryClient.invalidateQueries({ queryKey: ["ews"] });
    },
  });

  if (settings.isLoading) return <Loading />;
  if (settings.isError) return <ErrorState error={settings.error} onRetry={() => settings.refetch()} />;
  if (!settings.data) return null;

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Peringatan dini</span>
        <h1 className="page-title">Konfigurasi EWS</h1>
        <p className="lede">
          Ambang batas z-score menentukan kapan sebuah perubahan harga dianggap menyimpang.
          Nilai dapat diatur global atau di-override per komoditas.
        </p>
      </header>

      <Notice tone="info" title="Kenapa perlu override per komoditas?">
        Cabai jauh lebih volatil daripada beras. Memakai satu ambang untuk keduanya membuat
        cabai terus-menerus berstatus kritis padahal fluktuasinya normal, sementara
        pergeseran kecil pada beras yang sebenarnya penting justru tidak terdeteksi.
      </Notice>

      <section className="card stack-4">
        <div className="field" style={{ maxWidth: 320 }}>
          <label htmlFor="cakupan">Cakupan pengaturan</label>
          <select
            id="cakupan"
            className="select"
            value={scope}
            onChange={(event) => {
              setScope(event.target.value);
              setFeedback(null);
            }}
          >
            <option value="global">Global (semua komoditas)</option>
            {settings.data.commodities.map((commodity) => {
              const hasOverride = settings.data!.overrides.some(
                (item) => item.commodity_id === commodity.id
              );
              return (
                <option key={commodity.id} value={commodity.id}>
                  {commodity.name}
                  {hasOverride ? " (punya override)" : ""}
                </option>
              );
            })}
          </select>
        </div>

        <div className="row-wrap" style={{ gap: "var(--space-4)" }}>
          <ThresholdField
            id="thr-waspada"
            label="Waspada — z >"
            value={waspada}
            onChange={setWaspada}
            level="waspada"
          />
          <ThresholdField
            id="thr-warning"
            label="Warning — z >"
            value={warning}
            onChange={setWarning}
            level="warning"
          />
          <ThresholdField
            id="thr-kritis"
            label="Kritis — z >"
            value={kritis}
            onChange={setKritis}
            level="kritis"
          />
        </div>

        {!ordered ? (
          <Notice tone="critical" title="Urutan ambang tidak valid">
            Nilai harus menaik: waspada &lt; warning &lt; kritis.
          </Notice>
        ) : null}

        {feedback ? (
          <Notice tone="success" title="Tersimpan">
            {feedback}
          </Notice>
        ) : null}
        {save.isError ? <ErrorState error={save.error} /> : null}

        <div className="row" style={{ gap: "var(--space-3)" }}>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!ordered || save.isPending}
            onClick={() => {
              setFeedback(null);
              save.mutate();
            }}
          >
            {save.isPending ? "Menyimpan…" : "Simpan ambang batas"}
          </button>

          {scope !== "global" &&
          settings.data.overrides.some((item) => String(item.commodity_id) === scope) ? (
            <button
              type="button"
              className="btn btn-danger"
              disabled={removeOverride.isPending}
              onClick={() => removeOverride.mutate(Number(scope))}
            >
              Hapus override
            </button>
          ) : null}
        </div>
      </section>

      <section className="card stack-4">
        <div className="stack-1">
          <h2 className="section-title">Pratinjau dampak</h2>
          <p className="small muted" style={{ maxWidth: "70ch" }}>
            Berapa banyak status historis yang akan berubah bila ambang ini disimpan.
            Dihitung sebelum menyimpan, sehingga kamu bisa membandingkan dulu.
          </p>
        </div>

        {!ordered ? (
          <p className="small muted">Perbaiki urutan ambang untuk melihat pratinjau.</p>
        ) : preview.isLoading ? (
          <Loading label="Menghitung pratinjau…" />
        ) : preview.data ? (
          <div className="stack-4">
            <div className="row-wrap" style={{ gap: "var(--space-6)" }}>
              <div className="stack-1">
                <span className="eyebrow">Total periode dinilai</span>
                <span className="num" style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
                  {formatNumber(preview.data.total)}
                </span>
              </div>
              <div className="stack-1">
                <span className="eyebrow">Status berubah</span>
                <span
                  className="num"
                  style={{
                    fontSize: "var(--text-lg)",
                    fontWeight: 600,
                    color: preview.data.changed > 0 ? "var(--status-warning)" : undefined,
                  }}
                >
                  {formatNumber(preview.data.changed)}
                </span>
              </div>
            </div>

            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Status</th>
                    <th className="right">Sekarang</th>
                    <th className="right">Setelah disimpan</th>
                    <th className="right">Selisih</th>
                  </tr>
                </thead>
                <tbody>
                  {LEVELS.map((level) => {
                    const before = preview.data!.before[level] ?? 0;
                    const after = preview.data!.after[level] ?? 0;
                    const diff = after - before;
                    return (
                      <tr key={level}>
                        <td>
                          <StatusBadge level={level} />
                        </td>
                        <td className="num right">{before}</td>
                        <td className="num right">{after}</td>
                        <td
                          className="num right"
                          style={{
                            color:
                              diff > 0
                                ? "var(--dir-up)"
                                : diff < 0
                                ? "var(--dir-down)"
                                : "var(--ink-muted)",
                            fontWeight: diff !== 0 ? 600 : 400,
                          }}
                        >
                          {diff > 0 ? `+${diff}` : diff}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </section>

      {settings.data.overrides.length > 0 ? (
        <section className="card stack-3">
          <h2 className="section-title">Override aktif</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Komoditas</th>
                  <th className="right">Waspada</th>
                  <th className="right">Warning</th>
                  <th className="right">Kritis</th>
                </tr>
              </thead>
              <tbody>
                {settings.data.overrides.map((item) => {
                  const commodity = settings.data!.commodities.find(
                    (c) => c.id === item.commodity_id
                  );
                  return (
                    <tr key={item.commodity_id}>
                      <td className="small">{commodity?.name ?? item.commodity_id}</td>
                      <td className="num right">{item.threshold_waspada}</td>
                      <td className="num right">{item.threshold_warning}</td>
                      <td className="num right">{item.threshold_kritis}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function ThresholdField({
  id,
  label,
  value,
  onChange,
  level,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  level: AlertLevel;
}) {
  const style = statusStyle(level);
  return (
    <div className="field" style={{ minWidth: 150 }}>
      <label htmlFor={id} className="row" style={{ gap: "var(--space-2)" }}>
        <span
          aria-hidden="true"
          className={`status ${style.className}`}
          style={{ width: 10, height: 10, padding: 0, borderRadius: 2, display: "inline-block" }}
        />
        {label}
      </label>
      <input
        id={id}
        className="input num"
        type="number"
        step="0.1"
        min="0.1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
