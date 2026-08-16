import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, buildQuery } from "../../lib/api";
import { formatDateShort, formatDateTime, formatRupiah } from "../../lib/format";
import { ErrorState, Loading, Notice } from "../../components/ui";
import type { AdminPriceRow, Commodity } from "../../lib/types";

const PAGE_SIZE = 50;

export function PriceHistoryPage() {
  const queryClient = useQueryClient();
  const [commodityId, setCommodityId] = useState<string>("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [onlyInterpolated, setOnlyInterpolated] = useState(false);
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<AdminPriceRow | null>(null);
  const [editValue, setEditValue] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);

  const commodities = useQuery({
    queryKey: ["commodities"],
    queryFn: () => api.get<{ items: Commodity[] }>("/api/commodities"),
    staleTime: Infinity,
  });

  const query = buildQuery({
    commodity_id: commodityId,
    start,
    end,
    only_interpolated: onlyInterpolated ? true : "",
    limit: PAGE_SIZE,
    offset,
  });

  const prices = useQuery({
    queryKey: ["admin-prices", query],
    queryFn: () =>
      api.get<{ total: number; items: AdminPriceRow[]; limit: number; offset: number }>(
        `/api/admin/prices${query}`
      ),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["admin-prices"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["admin-overview"] });
  };

  const update = useMutation({
    mutationFn: ({ id, price }: { id: number; price: number }) =>
      api.put(`/api/admin/prices/${id}`, { price, run_forecast: true }),
    onSuccess: () => {
      setFeedback("Harga diperbarui. Prediksi untuk tanggal terdampak dihitung ulang.");
      setEditing(null);
      invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/admin/prices/${id}`),
    onSuccess: () => {
      setFeedback("Baris harga dihapus dan tercatat di log audit.");
      invalidate();
    },
  });

  const total = prices.data?.total ?? 0;
  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Data harga</span>
        <h1 className="page-title">Riwayat &amp; Koreksi</h1>
        <p className="lede">
          Setiap koreksi memicu perhitungan ulang prediksi untuk tanggal terdampak dan
          tercatat di log audit lengkap dengan nilai sebelum dan sesudah.
        </p>
      </header>

      <section className="card stack-4">
        <div className="row-wrap" style={{ gap: "var(--space-4)", alignItems: "flex-end" }}>
          <div className="field" style={{ minWidth: 220 }}>
            <label htmlFor="filter-komoditas">Komoditas</label>
            <select
              id="filter-komoditas"
              className="select"
              value={commodityId}
              onChange={(event) => {
                setCommodityId(event.target.value);
                setOffset(0);
              }}
            >
              <option value="">Semua komoditas</option>
              {commodities.data?.items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="filter-mulai">Dari</label>
            <input
              id="filter-mulai"
              type="date"
              className="input"
              value={start}
              onChange={(event) => {
                setStart(event.target.value);
                setOffset(0);
              }}
            />
          </div>

          <div className="field">
            <label htmlFor="filter-akhir">Sampai</label>
            <input
              id="filter-akhir"
              type="date"
              className="input"
              value={end}
              onChange={(event) => {
                setEnd(event.target.value);
                setOffset(0);
              }}
            />
          </div>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={onlyInterpolated}
              onChange={(event) => {
                setOnlyInterpolated(event.target.checked);
                setOffset(0);
              }}
            />
            Hanya data interpolasi
          </label>
        </div>

        <span className="small muted">
          {total.toLocaleString("id-ID")} baris cocok · halaman {page} dari {pageCount}
        </span>
      </section>

      {feedback ? (
        <Notice tone="success" title="Perubahan tersimpan">
          {feedback}
        </Notice>
      ) : null}

      {update.isError ? <ErrorState error={update.error} /> : null}
      {remove.isError ? <ErrorState error={remove.error} /> : null}

      {prices.isLoading ? <Loading /> : null}
      {prices.isError ? <ErrorState error={prices.error} onRetry={() => prices.refetch()} /> : null}

      {prices.data ? (
        <section className="stack-4">
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Tanggal</th>
                  <th>Komoditas</th>
                  <th className="right">Harga</th>
                  <th>Sumber</th>
                  <th>Diubah</th>
                  <th className="right">Aksi</th>
                </tr>
              </thead>
              <tbody>
                {prices.data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="num">{formatDateShort(row.price_date)}</td>
                    <td className="small">{row.commodity_name}</td>
                    <td className="num right">
                      {editing?.id === row.id ? (
                        <input
                          className="input num"
                          type="number"
                          min="1"
                          step="50"
                          value={editValue}
                          autoFocus
                          onChange={(event) => setEditValue(event.target.value)}
                          style={{ width: 120 }}
                        />
                      ) : (
                        formatRupiah(row.price)
                      )}
                    </td>
                    <td className="xs">
                      {row.is_interpolated ? (
                        <span className="badge">Interpolasi</span>
                      ) : (
                        <span className="muted">{row.source}</span>
                      )}
                    </td>
                    <td className="xs muted">{formatDateTime(row.updated_at)}</td>
                    <td className="right">
                      {editing?.id === row.id ? (
                        <div className="row" style={{ justifyContent: "flex-end", gap: "var(--space-2)" }}>
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            disabled={update.isPending}
                            onClick={() =>
                              update.mutate({ id: row.id, price: Number(editValue) })
                            }
                          >
                            Simpan
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-ghost"
                            onClick={() => setEditing(null)}
                          >
                            Batal
                          </button>
                        </div>
                      ) : (
                        <div className="row" style={{ justifyContent: "flex-end", gap: "var(--space-2)" }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => {
                              setEditing(row);
                              setEditValue(String(Math.round(row.price)));
                              setFeedback(null);
                            }}
                          >
                            Ubah
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-danger"
                            disabled={remove.isPending}
                            onClick={() => {
                              const ok = window.confirm(
                                `Hapus harga ${row.commodity_name} pada ${formatDateShort(
                                  row.price_date
                                )}?\n\nMenghapus baris membuat deret waktu berlubang dan dapat merusak fitur lag/rolling.`
                              );
                              if (ok) {
                                setFeedback(null);
                                remove.mutate(row.id);
                              }
                            }}
                          >
                            Hapus
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="row" style={{ gap: "var(--space-3)" }}>
            <button
              type="button"
              className="btn btn-sm"
              disabled={offset === 0}
              onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
            >
              ← Sebelumnya
            </button>
            <button
              type="button"
              className="btn btn-sm"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset((current) => current + PAGE_SIZE)}
            >
              Berikutnya →
            </button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
