import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { formatDateShort, formatNumber, formatPercent, formatRupiah } from "../../lib/format";
import { ErrorState, Loading, Notice, StatusBadge } from "../../components/ui";
import type { Commodity, ModelsResponse } from "../../lib/types";

const HORIZONS = [1, 7, 30];

export function ModelManagerPage() {
  const queryClient = useQueryClient();
  const [feedback, setFeedback] = useState<string | null>(null);

  const models = useQuery({
    queryKey: ["admin-models"],
    queryFn: () => api.get<ModelsResponse>("/api/admin/models"),
  });

  const commodities = useQuery({
    queryKey: ["commodities"],
    queryFn: () => api.get<{ items: Commodity[] }>("/api/commodities"),
    staleTime: Infinity,
  });

  const register = useMutation({
    mutationFn: (payload: Record<string, unknown>) => api.post("/api/admin/models", payload),
    onSuccess: () => {
      setFeedback("Model berhasil didaftarkan dan diaktifkan.");
      queryClient.invalidateQueries({ queryKey: ["admin-models"] });
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  if (models.isLoading) return <Loading />;
  if (models.isError) return <ErrorState error={models.error} onRetry={() => models.refetch()} />;
  if (!models.data) return null;

  const data = models.data;
  const artifacts = data.research_artifacts;

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Model</span>
        <h1 className="page-title">Manajemen Model</h1>
        <p className="lede">
          Registri {data.expected_count} model (9 komoditas × 3 horizon). Hanya satu versi
          yang aktif untuk tiap pasangan komoditas–horizon.
        </p>
      </header>

      <section className="grid grid-3">
        <StatCard label="Model aktif" value={`${data.active_count} / ${data.expected_count}`} />
        <StatCard
          label="Kelengkapan"
          value={formatPercent((data.active_count / data.expected_count) * 100, 0)}
        />
        <StatCard
          label="Status"
          value={data.active_count >= data.expected_count ? "Lengkap" : "Belum lengkap"}
        />
      </section>

      <section className="card stack-3">
        <h2 className="section-title">Artefak penelitian</h2>
        <p className="small muted" style={{ maxWidth: "72ch" }}>
          Artefak ini dimuat langsung dari direktori penelitian dan bersifat read-only bagi
          aplikasi. Objek transformer yang dipakai saat inference adalah objek yang sama
          persis dengan yang di-<code>fit()</code> saat training.
        </p>

        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Artefak</th>
                <th>Status</th>
                <th className="right">Jumlah komoditas</th>
                <th>Lokasi</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(artifacts).map(([name, status]) => (
                <tr key={name}>
                  <td className="num">{name}.pkl</td>
                  <td>
                    <StatusBadge
                      level={status.loaded ? "normal" : status.exists ? "warning" : "kritis"}
                      title={status.error ?? (status.loaded ? "Berhasil dimuat" : "Tidak dapat dimuat")}
                    />
                  </td>
                  <td className="num right">{status.n_commodities ?? "—"}</td>
                  <td className="xs muted" style={{ wordBreak: "break-all" }}>
                    {status.path}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.active_count === 0 ? (
        <Notice tone="info" title="Cara mendaftarkan model hasil notebook">
          <ol style={{ paddingLeft: "1.1rem", marginTop: "var(--space-2)" }}>
            <li>
              Simpan model per komoditas × horizon dari notebook, misalnya{" "}
              <code>joblib.dump(model, "ga_lgbm_cabai-rawit-merah_h1.pkl")</code>.
            </li>
            <li>
              Salin berkasnya ke direktori <code>webapp/backend/artifacts/models/</code>.
            </li>
            <li>
              Daftarkan lewat formulir di bawah, atau jalankan{" "}
              <code>python -m pangania.register_models</code> untuk mendaftarkan sekaligus.
            </li>
          </ol>
        </Notice>
      ) : null}

      {feedback ? (
        <Notice tone="success" title="Berhasil">
          {feedback}
        </Notice>
      ) : null}
      {register.isError ? <ErrorState error={register.error} /> : null}

      <RegisterForm
        commodities={commodities.data?.items ?? []}
        onSubmit={(payload) => {
          setFeedback(null);
          register.mutate(payload);
        }}
        pending={register.isPending}
      />

      <section className="stack-3">
        <h2 className="section-title">Matriks model</h2>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Komoditas</th>
                {HORIZONS.map((horizon) => (
                  <th key={horizon}>H+{horizon}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(commodities.data?.items ?? []).map((commodity) => (
                <tr key={commodity.id}>
                  <td className="small">{commodity.name}</td>
                  {HORIZONS.map((horizon) => {
                    const entry = data.matrix.find(
                      (item) => item.commodity.id === commodity.id && item.horizon === horizon
                    );
                    return (
                      <td key={horizon}>
                        {entry?.active ? (
                          <div className="stack-1">
                            <span className="badge">{entry.active.algorithm}</span>
                            <span className="xs muted num">
                              {entry.active.metrics[0]?.mape != null
                                ? `MAPE ${formatPercent(entry.active.metrics[0].mape, 2)}`
                                : "belum ada metrik"}
                            </span>
                          </div>
                        ) : (
                          <span className="xs muted">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {data.active_count > 0 ? (
        <section className="stack-3">
          <h2 className="section-title">Detail model aktif</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Komoditas</th>
                  <th>Horizon</th>
                  <th>Algoritma</th>
                  <th className="right">MAE</th>
                  <th className="right">RMSE</th>
                  <th className="right">MAPE</th>
                  <th className="right">R²</th>
                  <th>Akhir training</th>
                </tr>
              </thead>
              <tbody>
                {data.matrix
                  .filter((entry) => entry.active)
                  .map((entry) => {
                    const metric = entry.active!.metrics[0];
                    return (
                      <tr key={`${entry.commodity.id}-${entry.horizon}`}>
                        <td className="small">{entry.commodity.name}</td>
                        <td className="num">H+{entry.horizon}</td>
                        <td className="xs">{entry.active!.algorithm}</td>
                        <td className="num right">{formatRupiah(metric?.mae)}</td>
                        <td className="num right">{formatRupiah(metric?.rmse)}</td>
                        <td className="num right">{formatPercent(metric?.mape, 2)}</td>
                        <td className="num right">{formatNumber(metric?.r2, 3)}</td>
                        <td className="num xs">{formatDateShort(entry.active!.train_data_end)}</td>
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

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="card stack-1">
      <span className="eyebrow">{label}</span>
      <span className="num" style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

function RegisterForm({
  commodities,
  onSubmit,
  pending,
}: {
  commodities: Commodity[];
  onSubmit: (payload: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [commodityId, setCommodityId] = useState("");
  const [horizon, setHorizon] = useState("1");
  const [algorithm, setAlgorithm] = useState("ga_lightgbm");
  const [artifactPath, setArtifactPath] = useState("");
  const [trainDataEnd, setTrainDataEnd] = useState("");
  const [hyperparameters, setHyperparameters] = useState("");
  const [jsonError, setJsonError] = useState<string | null>(null);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    setJsonError(null);

    let parsed: Record<string, unknown> = {};
    if (hyperparameters.trim()) {
      try {
        parsed = JSON.parse(hyperparameters);
      } catch {
        setJsonError("Hyperparameter harus berupa JSON yang valid.");
        return;
      }
    }

    onSubmit({
      commodity_id: Number(commodityId),
      horizon: Number(horizon),
      algorithm,
      artifact_path: artifactPath.trim(),
      hyperparameters: parsed,
      train_data_end: trainDataEnd || null,
      activate: true,
    });
  };

  return (
    <form className="card stack-4" onSubmit={handleSubmit}>
      <div className="stack-1">
        <h2 className="section-title">Daftarkan model baru</h2>
        <p className="small muted">
          Berkas harus sudah berada di <code>webapp/backend/artifacts/models/</code>. Isi
          nama berkasnya saja, tanpa path direktori.
        </p>
      </div>

      <div className="row-wrap" style={{ gap: "var(--space-4)", alignItems: "flex-end" }}>
        <div className="field" style={{ minWidth: 220 }}>
          <label htmlFor="reg-komoditas">Komoditas</label>
          <select
            id="reg-komoditas"
            className="select"
            required
            value={commodityId}
            onChange={(event) => setCommodityId(event.target.value)}
          >
            <option value="">Pilih komoditas</option>
            {commodities.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="reg-horizon">Horizon</label>
          <select
            id="reg-horizon"
            className="select"
            value={horizon}
            onChange={(event) => setHorizon(event.target.value)}
          >
            <option value="1">H+1 (harian)</option>
            <option value="7">H+7 (mingguan)</option>
            <option value="30">H+30 (bulanan)</option>
          </select>
        </div>

        <div className="field">
          <label htmlFor="reg-algoritma">Algoritma</label>
          <select
            id="reg-algoritma"
            className="select"
            value={algorithm}
            onChange={(event) => setAlgorithm(event.target.value)}
          >
            <option value="ga_lightgbm">GA-LightGBM</option>
            <option value="lightgbm_default">LightGBM default</option>
            <option value="lightgbm_grid">LightGBM grid search</option>
            <option value="naive">Naive</option>
          </select>
        </div>

        <div className="field" style={{ minWidth: 260 }}>
          <label htmlFor="reg-artefak">Nama berkas artefak</label>
          <input
            id="reg-artefak"
            className="input"
            required
            placeholder="ga_lgbm_cabai-rawit-merah_h1.pkl"
            value={artifactPath}
            onChange={(event) => setArtifactPath(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="reg-akhir-training">Akhir data training</label>
          <input
            id="reg-akhir-training"
            type="date"
            className="input"
            value={trainDataEnd}
            onChange={(event) => setTrainDataEnd(event.target.value)}
          />
        </div>
      </div>

      <div className="field">
        <label htmlFor="reg-hyper">Hyperparameter (JSON, opsional)</label>
        <textarea
          id="reg-hyper"
          className="input"
          rows={3}
          placeholder='{"num_leaves": 64, "learning_rate": 0.05}'
          value={hyperparameters}
          onChange={(event) => setHyperparameters(event.target.value)}
          style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}
        />
        {jsonError ? <span className="xs" style={{ color: "var(--status-critical)" }}>{jsonError}</span> : null}
      </div>

      <button type="submit" className="btn btn-primary" disabled={pending} style={{ alignSelf: "flex-start" }}>
        {pending ? "Mendaftarkan…" : "Daftarkan & aktifkan"}
      </button>
    </form>
  );
}
