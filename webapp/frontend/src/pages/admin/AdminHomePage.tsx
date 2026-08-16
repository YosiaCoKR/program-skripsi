import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { formatDateLong, formatDateShort, formatDateTime } from "../../lib/format";
import { ErrorState, Loading, Notice } from "../../components/ui";
import type { AdminOverview } from "../../lib/types";

export function AdminHomePage() {
  const overview = useQuery({
    queryKey: ["admin-overview"],
    queryFn: () => api.get<AdminOverview>("/api/admin/overview"),
  });

  if (overview.isLoading) return <Loading />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;
  if (!overview.data) return null;

  const data = overview.data;
  const drift = data.drift;

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Beranda admin</span>
        <h1 className="page-title">Status Sistem</h1>
      </header>

      {data.missing_count > 0 ? (
        <Notice tone="warning" title={`${data.missing_count} tanggal belum terisi`}>
          Data terakhir tercatat {formatDateLong(data.latest_data_date)}, sedangkan hari ini{" "}
          {formatDateLong(data.today)}. Isi harga terbaru agar prediksi mengikuti kondisi
          pasar terkini.{" "}
          <Link to="/admin/input-harga" style={{ textDecoration: "underline" }}>
            Buka input harga
          </Link>
        </Notice>
      ) : (
        <Notice tone="success" title="Data harga mutakhir">
          Tidak ada tanggal yang bolong sampai hari ini.
        </Notice>
      )}

      {!data.models_ready ? (
        <Notice tone="warning" title="Model prediksi belum lengkap">
          Baru {data.active_model_count} dari {data.expected_model_count} model aktif.
          Prediksi belum dapat dihasilkan sampai artefak model didaftarkan.{" "}
          <Link to="/admin/model" style={{ textDecoration: "underline" }}>
            Buka manajemen model
          </Link>
        </Notice>
      ) : null}

      {drift.level === "peringatan" || drift.level === "kritis" ? (
        <Notice tone={drift.level === "kritis" ? "critical" : "warning"} title="Trend extrapolation drift">
          Data terakhir sudah {drift.days} hari melewati akhir periode training model.
          Semakin jauh jaraknya, semakin jauh pula ekstrapolasi linear komponen trend dari
          rentang yang pernah dilihat model — akurasi berpotensi menurun. Pertimbangkan
          melatih ulang model di notebook lalu mendaftarkan versi barunya.
        </Notice>
      ) : null}

      <section className="grid grid-3">
        <StatCard label="Data terakhir" value={formatDateShort(data.latest_data_date)} />
        <StatCard label="Tanggal bolong" value={`${data.missing_count} hari`} />
        <StatCard
          label="Model aktif"
          value={`${data.active_model_count} / ${data.expected_model_count}`}
        />
        <StatCard
          label="Drift terhadap training"
          value={drift.days != null ? `${drift.days} hari` : "belum diketahui"}
          hint={
            drift.level === "unknown"
              ? "Terisi setelah model terdaftar"
              : `Ambang peringatan ${drift.warning_threshold} hari`
          }
        />
      </section>

      <section className="card stack-4">
        <div className="row-between">
          <h2 className="section-title">Eksekusi forecast terakhir</h2>
          <Link to="/admin/forecast" className="btn btn-sm">
            Lihat semua
          </Link>
        </div>

        {data.recent_runs.length === 0 ? (
          <p className="small muted">
            Belum ada eksekusi forecast. Eksekusi berjalan otomatis setiap kali harga baru
            disimpan.
          </p>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Tanggal basis</th>
                  <th>Status</th>
                  <th className="right">Prediksi</th>
                  <th>Waktu mulai</th>
                </tr>
              </thead>
              <tbody>
                {data.recent_runs.map((run) => (
                  <tr key={run.id}>
                    <td className="num">{formatDateShort(run.base_date)}</td>
                    <td>
                      <RunStatus status={run.status} />
                    </td>
                    <td className="num right">{run.predictions_count}</td>
                    <td className="num xs">{formatDateTime(run.started_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card stack-3">
        <h2 className="section-title">Rutinitas harian</h2>
        <ol className="stack-2 small secondary" style={{ paddingLeft: "1.2rem" }}>
          <li>Periksa status di halaman ini — apakah ada tanggal yang bolong.</li>
          <li>Buka Input Harga, pilih tanggal, sesuaikan angka yang berubah dari rilis PIHPS.</li>
          <li>
            Simpan. Sistem otomatis mengisi tanggal bolong lewat interpolasi, lalu
            menjalankan rolling forecast untuk ketiga horizon tanpa melatih ulang model.
          </li>
          <li>Pastikan status eksekusi bernilai sukses di Monitor Forecast.</li>
        </ol>
      </section>
    </div>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card stack-1">
      <span className="eyebrow">{label}</span>
      <span className="num" style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>
        {value}
      </span>
      {hint ? <span className="xs muted">{hint}</span> : null}
    </div>
  );
}

export function RunStatus({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: "status-good",
    partial: "status-warning",
    failed: "status-critical",
    pending: "status-neutral",
  };
  const labels: Record<string, string> = {
    success: "Sukses",
    partial: "Sebagian",
    failed: "Gagal",
    pending: "Menunggu",
  };
  return <span className={`status ${map[status] ?? "status-neutral"}`}>{labels[status] ?? status}</span>;
}
