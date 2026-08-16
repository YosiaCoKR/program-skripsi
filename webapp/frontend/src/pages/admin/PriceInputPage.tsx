import { useEffect, useMemo, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../lib/api";
import { commodityColor } from "../../lib/palette";
import { formatDateLong, formatDateShort, formatPercent, formatRupiah, toIsoDate } from "../../lib/format";
import { ErrorState, Loading, Notice, Segmented } from "../../components/ui";
import type { OutlierWarning, PrefillResponse, SaveDailyResponse } from "../../lib/types";

type Mode = "harian" | "impor";

export function PriceInputPage() {
  const [mode, setMode] = useState<Mode>("harian");

  return (
    <div className="stack-6">
      <header className="stack-3">
        <div className="stack-2">
          <span className="eyebrow">Input data</span>
          <h1 className="page-title">Input Harga Terkini</h1>
          <p className="lede">
            Setiap harga baru yang disimpan langsung memicu rolling one-step forecast untuk
            ketiga horizon — tanpa melatih ulang model.
          </p>
        </div>

        <Segmented
          value={mode}
          options={[
            { value: "harian" as Mode, label: "Mode harian" },
            { value: "impor" as Mode, label: "Impor CSV" },
          ]}
          onChange={setMode}
          ariaLabel="Mode input"
        />
      </header>

      {mode === "harian" ? <DailyForm /> : <CsvImport />}
    </div>
  );
}

/* ============================================================ mode harian */

function DailyForm() {
  const queryClient = useQueryClient();
  const [targetDate, setTargetDate] = useState(() => toIsoDate(new Date()));
  const [values, setValues] = useState<Record<number, string>>({});
  const [warnings, setWarnings] = useState<OutlierWarning[] | null>(null);
  const [result, setResult] = useState<SaveDailyResponse | null>(null);
  const [fillGaps, setFillGaps] = useState(true);

  const prefill = useQuery({
    queryKey: ["prefill", targetDate],
    queryFn: () => api.get<PrefillResponse>(`/api/admin/prices/prefill?target_date=${targetDate}`),
    enabled: Boolean(targetDate),
  });

  // Isi form dengan harga hari sebelumnya sebagai nilai awal — harga sering
  // tidak berubah, jadi ini memangkas pekerjaan mengetik. Tetap harus
  // dikonfirmasi admin sebelum tersimpan.
  useEffect(() => {
    if (!prefill.data) return;
    const next: Record<number, string> = {};
    for (const item of prefill.data.items) {
      next[item.commodity.id] =
        item.suggested_price != null ? String(Math.round(item.suggested_price)) : "";
    }
    setValues(next);
    setWarnings(null);
    setResult(null);
  }, [prefill.data]);

  const save = useMutation({
    mutationFn: (confirmOutliers: boolean) =>
      api.post<SaveDailyResponse>("/api/admin/prices/daily", {
        price_date: targetDate,
        entries: Object.entries(values)
          .filter(([, value]) => value.trim() !== "")
          .map(([commodityId, value]) => ({
            commodity_id: Number(commodityId),
            price: Number(value),
          })),
        fill_gaps: fillGaps,
        confirm_outliers: confirmOutliers,
        run_forecast: true,
      }),
    onSuccess: (data) => {
      if (data.status === "needs_confirmation") {
        setWarnings(data.warnings ?? []);
        setResult(null);
        return;
      }
      setWarnings(null);
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["prefill"] });
    },
  });

  const changeFor = (commodityId: number, previous: number | null): number | null => {
    const raw = values[commodityId];
    if (!raw || previous == null || previous === 0) return null;
    return ((Number(raw) - previous) / previous) * 100;
  };

  const filledCount = useMemo(
    () => Object.values(values).filter((value) => value.trim() !== "").length,
    [values]
  );

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(false);
  };

  return (
    <form className="stack-5" onSubmit={handleSubmit}>
      <section className="card stack-4">
        <div className="row-wrap" style={{ gap: "var(--space-5)", alignItems: "flex-end" }}>
          <div className="field">
            <label htmlFor="tanggal-input">Tanggal data</label>
            <input
              id="tanggal-input"
              type="date"
              className="input"
              value={targetDate}
              onChange={(event) => setTargetDate(event.target.value)}
              required
            />
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={fillGaps}
              onChange={(event) => setFillGaps(event.target.checked)}
            />
            Isi tanggal bolong dengan interpolasi
          </label>

          <span className="small muted">{filledCount} dari 9 komoditas terisi</span>
        </div>

        {prefill.data && prefill.data.gap_dates.length > 0 ? (
          <Notice tone="warning" title={`${prefill.data.gap_dates.length} tanggal bolong terdeteksi`}>
            Rentang {formatDateShort(prefill.data.gap_dates[0])} sampai{" "}
            {formatDateShort(prefill.data.gap_dates.at(-1))} belum punya data.{" "}
            {fillGaps
              ? "Tanggal tersebut akan diisi otomatis lewat interpolasi berbasis waktu dan ditandai sebagai data interpolasi."
              : "Pengisian otomatis sedang dimatikan — deret waktu akan berlubang dan fitur lag/rolling bisa rusak."}
          </Notice>
        ) : null}
      </section>

      {prefill.isLoading ? <Loading label="Memuat nilai awal…" /> : null}
      {prefill.isError ? <ErrorState error={prefill.error} onRetry={() => prefill.refetch()} /> : null}

      {prefill.data ? (
        <section className="card stack-3">
          <div className="price-entry-row" style={{ borderBottom: "1px solid var(--rule-strong)" }}>
            <span className="eyebrow">Komoditas</span>
            <span className="eyebrow" style={{ textAlign: "right" }}>
              Harga (Rp)
            </span>
            <span className="eyebrow col-hide-sm" style={{ textAlign: "right" }}>
              Sebelumnya
            </span>
            <span className="eyebrow col-hide-sm" style={{ textAlign: "right" }}>
              Perubahan
            </span>
          </div>

          {prefill.data.items.map((item) => {
            const change = changeFor(item.commodity.id, item.previous_price);
            const isOutlier =
              change != null && Math.abs(change) > prefill.data!.outlier_threshold_pct;

            return (
              <div key={item.commodity.id} className="price-entry-row">
                <label
                  htmlFor={`harga-${item.commodity.id}`}
                  className="row"
                  style={{ gap: "var(--space-2)" }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: commodityColor(item.commodity),
                      flex: "none",
                    }}
                  />
                  <span className="small">{item.commodity.name}</span>
                </label>

                <input
                  id={`harga-${item.commodity.id}`}
                  className={`input num ${isOutlier ? "input-invalid" : ""}`}
                  type="number"
                  min="1"
                  step="50"
                  inputMode="numeric"
                  value={values[item.commodity.id] ?? ""}
                  onChange={(event) =>
                    setValues((current) => ({
                      ...current,
                      [item.commodity.id]: event.target.value,
                    }))
                  }
                  aria-describedby={isOutlier ? `peringatan-${item.commodity.id}` : undefined}
                />

                <span className="num small muted col-hide-sm" style={{ textAlign: "right" }}>
                  {formatRupiah(item.previous_price)}
                </span>

                <span
                  id={`peringatan-${item.commodity.id}`}
                  className={`num small col-hide-sm ${
                    isOutlier ? "dir-up" : change && change < 0 ? "dir-down" : "muted"
                  }`}
                  style={{ textAlign: "right", fontWeight: isOutlier ? 600 : 400 }}
                >
                  {formatPercent(change, 1, true)}
                </span>
              </div>
            );
          })}
        </section>
      ) : null}

      {warnings && warnings.length > 0 ? (
        <Notice tone="warning" title={`${warnings.length} harga menyimpang jauh`}>
          <div className="stack-2" style={{ marginTop: "var(--space-2)" }}>
            <ul style={{ paddingLeft: "1.1rem" }}>
              {warnings.map((warning) => (
                <li key={warning.commodity_id} className="num">
                  {warning.commodity_name}: {formatRupiah(warning.previous_price)} →{" "}
                  {formatRupiah(warning.new_price)} ({formatPercent(warning.change_pct, 1, true)})
                </li>
              ))}
            </ul>
            <p>
              Lonjakan sebesar ini bisa saja benar — harga cabai memang sering bergerak
              ekstrem. Periksa kembali angkanya, lalu konfirmasi bila sudah sesuai.
            </p>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ alignSelf: "flex-start" }}
              onClick={() => save.mutate(true)}
              disabled={save.isPending}
            >
              Ya, simpan dengan angka ini
            </button>
          </div>
        </Notice>
      ) : null}

      {save.isError ? <ErrorState error={save.error} /> : null}

      {result?.status === "saved" ? (
        <Notice tone="success" title="Harga tersimpan">
          {result.saved} baris baru, {result.updated} diperbarui
          {result.interpolated ? `, ${result.interpolated} baris interpolasi` : ""} untuk{" "}
          {formatDateLong(targetDate)}.{" "}
          {result.forecast
            ? result.forecast.predictions_count > 0
              ? `Rolling forecast menghasilkan ${result.forecast.predictions_count} prediksi baru.`
              : `Rolling forecast belum menghasilkan prediksi — ${
                  result.forecast.message ?? "model belum terdaftar"
                }.`
            : null}
        </Notice>
      ) : null}

      <div className="row" style={{ gap: "var(--space-3)" }}>
        <button type="submit" className="btn btn-primary" disabled={save.isPending || filledCount === 0}>
          {save.isPending ? "Menyimpan…" : "Simpan & jalankan forecast"}
        </button>
        <span className="xs muted">
          Navigasi antar kolom harga dapat menggunakan tombol Tab.
        </span>
      </div>
    </form>
  );
}

/* ============================================================= impor CSV */

interface ImportPreview {
  status: string;
  accepted_count: number;
  rejected_count: number;
  rejected: { row: number; date?: string; reason: string }[];
  date_range?: { start: string; end: string } | null;
  saved?: number;
  updated?: number;
  interpolated?: number;
  forecast?: { status: string; predictions_count: number; message: string | null } | null;
}

function CsvImport() {
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<{ price_date: string; values: Record<string, number> }[]>([]);
  const [fileName, setFileName] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);

  const send = useMutation({
    mutationFn: (commit: boolean) =>
      api.post<ImportPreview>("/api/admin/prices/import", { rows, commit, run_forecast: true }),
    onSuccess: (data) => {
      setPreview(data);
      if (data.status === "committed") {
        queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
        queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
  });

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setParseError(null);
    setPreview(null);

    try {
      const text = await file.text();
      setRows(parseCsv(text));
    } catch (error) {
      setParseError(error instanceof Error ? error.message : "Gagal membaca berkas.");
      setRows([]);
    }
  };

  return (
    <div className="stack-5">
      <section className="card stack-4">
        <div className="stack-1">
          <h2 className="section-title">Impor banyak tanggal sekaligus</h2>
          <p className="small muted" style={{ maxWidth: "70ch" }}>
            Berkas CSV harus berkolom <code>tanggal</code> diikuti nama komoditas persis
            seperti pada dataset penelitian. Berkas diperiksa lebih dulu — tidak ada yang
            tersimpan sebelum kamu menekan tombol simpan.
          </p>
        </div>

        <div className="field" style={{ maxWidth: 420 }}>
          <label htmlFor="berkas-csv">Berkas CSV</label>
          <input id="berkas-csv" type="file" accept=".csv,text/csv" onChange={handleFile} className="input" />
        </div>

        {fileName ? (
          <p className="small">
            <strong>{fileName}</strong> — {rows.length} baris terbaca.
          </p>
        ) : null}

        {parseError ? <Notice tone="critical" title="Gagal membaca berkas">{parseError}</Notice> : null}

        <div className="row" style={{ gap: "var(--space-3)" }}>
          <button
            type="button"
            className="btn"
            disabled={rows.length === 0 || send.isPending}
            onClick={() => send.mutate(false)}
          >
            Periksa dulu
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!preview || preview.accepted_count === 0 || send.isPending}
            onClick={() => send.mutate(true)}
          >
            {send.isPending ? "Memproses…" : "Simpan hasil impor"}
          </button>
        </div>
      </section>

      {send.isError ? <ErrorState error={send.error} /> : null}

      {preview ? (
        <section className="card stack-4">
          <h2 className="section-title">
            {preview.status === "committed" ? "Hasil impor" : "Pratinjau impor"}
          </h2>

          <div className="grid grid-3">
            <Stat label="Baris diterima" value={String(preview.accepted_count)} />
            <Stat label="Baris ditolak" value={String(preview.rejected_count)} />
            {preview.date_range ? (
              <Stat
                label="Rentang tanggal"
                value={`${formatDateShort(preview.date_range.start)} — ${formatDateShort(
                  preview.date_range.end
                )}`}
              />
            ) : null}
            {preview.status === "committed" ? (
              <>
                <Stat label="Tersimpan" value={String(preview.saved ?? 0)} />
                <Stat label="Diperbarui" value={String(preview.updated ?? 0)} />
                <Stat label="Interpolasi" value={String(preview.interpolated ?? 0)} />
              </>
            ) : null}
          </div>

          {preview.rejected.length > 0 ? (
            <div className="stack-2">
              <span className="label">Baris yang ditolak</span>
              <div className="table-wrap" style={{ maxHeight: 260, overflowY: "auto" }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Baris</th>
                      <th>Tanggal</th>
                      <th>Alasan</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rejected.map((item) => (
                      <tr key={item.row}>
                        <td className="num">{item.row}</td>
                        <td className="num">{item.date ? formatDateShort(item.date) : "—"}</td>
                        <td className="small">{item.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : null}

          {preview.status === "committed" && preview.forecast ? (
            <Notice tone="success" title="Impor selesai">
              Rolling forecast menghasilkan {preview.forecast.predictions_count} prediksi.
              {preview.forecast.message ? ` Catatan: ${preview.forecast.message}` : ""}
            </Notice>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stack-1">
      <span className="eyebrow">{label}</span>
      <span className="num" style={{ fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

/**
 * Parser CSV sederhana.
 *
 * Cukup untuk berkas ekspor PIHPS yang formatnya seragam: pemisah koma,
 * tanpa tanda kutip bersarang. Angka menerima pemisah ribuan titik maupun
 * koma desimal.
 */
function parseCsv(text: string): { price_date: string; values: Record<string, number> }[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) {
    throw new Error("Berkas harus memuat baris judul dan minimal satu baris data.");
  }

  const header = lines[0].split(",").map((cell) => cell.trim());
  const dateIndex = header.findIndex((cell) => /^(tanggal|date|price_date)$/i.test(cell));
  if (dateIndex === -1) {
    throw new Error("Kolom 'tanggal' tidak ditemukan pada baris judul.");
  }

  return lines.slice(1).map((line) => {
    const cells = line.split(",").map((cell) => cell.trim());
    const values: Record<string, number> = {};

    header.forEach((name, index) => {
      if (index === dateIndex || !name) return;
      const raw = cells[index];
      if (!raw) return;
      const numeric = Number(raw.replace(/\./g, "").replace(",", "."));
      if (Number.isFinite(numeric)) values[name] = numeric;
    });

    return { price_date: cells[dateIndex], values };
  });
}
