import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, buildQuery } from "../../lib/api";
import { MAX_EXPLORE_SERIES, commodityColor } from "../../lib/palette";
import { compactRupiah } from "../../components/charts/chartUtils";
import { formatPercent, formatRupiah } from "../../lib/format";
import { PriceChart, type ChartSeries } from "../../components/charts/PriceChart";
import { MiniChart } from "../../components/charts/MiniChart";
import { ErrorState, Loading, Notice } from "../../components/ui";
import type { Commodity, DecompositionResponse, ExploreSeries } from "../../lib/types";

export function ExplorePage() {
  const [selected, setSelected] = useState<string[]>(["beras-medium-1", "cabai-rawit-merah"]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [showDecomposition, setShowDecomposition] = useState(false);
  const [decompCode, setDecompCode] = useState("beras-medium-1");

  const commodities = useQuery({
    queryKey: ["commodities"],
    queryFn: () => api.get<{ items: Commodity[] }>("/api/commodities"),
    staleTime: Infinity,
  });

  const explore = useQuery({
    queryKey: ["explore", selected, start, end],
    queryFn: () =>
      api.get<{ series: ExploreSeries[] }>(
        `/api/explore${buildQuery({ codes: selected.join(","), start, end })}`
      ),
    enabled: selected.length > 0,
  });

  const decomposition = useQuery({
    queryKey: ["decomposition", decompCode, start, end],
    queryFn: () =>
      api.get<DecompositionResponse>(
        `/api/explore/decomposition${buildQuery({ code: decompCode, start, end })}`
      ),
    enabled: showDecomposition,
  });

  const atLimit = selected.length >= MAX_EXPLORE_SERIES;

  const toggle = (code: string) => {
    setSelected((current) => {
      if (current.includes(code)) return current.filter((c) => c !== code);
      if (current.length >= MAX_EXPLORE_SERIES) return current;
      return [...current, code];
    });
  };

  const chartSeries: ChartSeries[] =
    explore.data?.series.map((item) => ({
      key: item.commodity.code,
      label: item.commodity.name,
      color: commodityColor(item.commodity),
      points: item.points.map((p) => ({
        date: p.date,
        value: p.price,
        isInterpolated: p.is_interpolated,
      })),
    })) ?? [];

  return (
    <div className="stack-6">
      <header className="stack-2">
        <span className="eyebrow">Data historis</span>
        <h1 className="page-title">Eksplorasi Data</h1>
        <p className="lede">
          Bandingkan pergerakan harga antar komoditas dan telusuri komponen dekomposisi
          MSTL yang menjadi dasar pemodelan.
        </p>
      </header>

      <section className="card stack-4">
        <div className="row-wrap" style={{ gap: "var(--space-5)", alignItems: "flex-end" }}>
          <div className="field">
            <label htmlFor="tgl-mulai">Dari tanggal</label>
            <input
              id="tgl-mulai"
              type="date"
              className="input"
              value={start}
              onChange={(event) => setStart(event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="tgl-akhir">Sampai tanggal</label>
            <input
              id="tgl-akhir"
              type="date"
              className="input"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              setStart("");
              setEnd("");
            }}
          >
            Reset rentang
          </button>
        </div>

        <div className="stack-3">
          <div className="row-between">
            <span className="label">
              Komoditas ({selected.length}/{MAX_EXPLORE_SERIES})
            </span>
            {atLimit ? (
              <span className="xs muted">
                Batas {MAX_EXPLORE_SERIES} seri tercapai — hapus satu pilihan untuk menambah
                yang lain.
              </span>
            ) : null}
          </div>

          <div className="row-wrap" style={{ gap: "var(--space-2)" }}>
            {commodities.data?.items.map((item) => {
              const active = selected.includes(item.code);
              const disabled = !active && atLimit;
              return (
                <button
                  key={item.code}
                  type="button"
                  className="btn btn-sm"
                  disabled={disabled}
                  aria-pressed={active}
                  onClick={() => toggle(item.code)}
                  style={{
                    borderColor: active ? commodityColor(item) : undefined,
                    background: active ? "var(--paper-sunken)" : undefined,
                  }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      background: commodityColor(item),
                      opacity: active ? 1 : 0.35,
                    }}
                  />
                  {item.name}
                </button>
              );
            })}
          </div>
        </div>

        <Notice tone="info" title="Kenapa dibatasi 3 komoditas?">
          Palet warna yang dipakai hanya terjamin dapat dibedakan — termasuk oleh pengguna
          dengan buta warna — sampai tiga seri dalam satu grafik. Untuk melihat seluruh
          sembilan komoditas sekaligus, gunakan panel small multiples di bawah.
        </Notice>

        {explore.isLoading ? <Loading /> : null}
        {explore.isError ? <ErrorState error={explore.error} onRetry={() => explore.refetch()} /> : null}

        {chartSeries.length > 0 ? (
          <PriceChart series={chartSeries} height={360} directLabels yLabel="Rp/kg" />
        ) : null}

        <a
          className="btn btn-sm"
          style={{ alignSelf: "flex-start" }}
          href={`/api/export/prices.csv${buildQuery({ codes: selected.join(","), start, end })}`}
        >
          Unduh CSV sesuai filter
        </a>
      </section>

      <section className="card stack-4">
        <div className="stack-1">
          <h2 className="section-title">Seluruh komoditas — small multiples</h2>
          <p className="small muted" style={{ maxWidth: "70ch" }}>
            Sembilan panel terpisah, satu komoditas per panel, masing-masing dengan skala
            sumbu-y sendiri. Menggambar sembilan garis dalam satu grafik akan membuat beras
            (sekitar Rp 12.000) terlihat datar sepenuhnya di samping cabai (sekitar Rp 70.000).
          </p>
        </div>

        <AllCommoditiesGrid start={start} end={end} />
      </section>

      <section className="card stack-4">
        <div className="row-between">
          <div className="stack-1">
            <h2 className="section-title">Dekomposisi MSTL</h2>
            <p className="small muted" style={{ maxWidth: "66ch" }}>
              Harga dipecah menjadi trend, musiman mingguan, musiman tahunan, dan residual.
              Model prediksi bekerja pada komponen residual, bukan pada harga mentah.
            </p>
          </div>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={showDecomposition}
              onChange={(event) => setShowDecomposition(event.target.checked)}
            />
            Tampilkan dekomposisi
          </label>
        </div>

        {showDecomposition ? (
          <div className="stack-4">
            <div className="field" style={{ maxWidth: 280 }}>
              <label htmlFor="pilih-dekomposisi">Komoditas</label>
              <select
                id="pilih-dekomposisi"
                className="select"
                value={decompCode}
                onChange={(event) => setDecompCode(event.target.value)}
              >
                {commodities.data?.items.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </div>

            {decomposition.isLoading ? <Loading label="Memuat dekomposisi…" /> : null}

            {decomposition.data && !decomposition.data.available ? (
              <Notice tone="warning" title="Dekomposisi tidak tersedia">
                {decomposition.data.reason ??
                  "Artefak stl_results.pkl tidak dapat dimuat dari direktori penelitian."}
              </Notice>
            ) : null}

            {decomposition.data?.available ? (
              <DecompositionPanels data={decomposition.data} />
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}

function AllCommoditiesGrid({ start, end }: { start: string; end: string }) {
  const commodities = useQuery({
    queryKey: ["commodities"],
    queryFn: () => api.get<{ items: Commodity[] }>("/api/commodities"),
    staleTime: Infinity,
  });

  // Diambil bertahap tiga-tiga agar tetap mematuhi batas API.
  const groups = [0, 1, 2].map((groupIndex) =>
    (commodities.data?.items ?? []).slice(groupIndex * 3, groupIndex * 3 + 3)
  );

  return (
    <div className="grid grid-small-multiples">
      {groups.map((group, groupIndex) => (
        <MiniGroup key={groupIndex} commodities={group} start={start} end={end} />
      ))}
    </div>
  );
}

function MiniGroup({
  commodities,
  start,
  end,
}: {
  commodities: Commodity[];
  start: string;
  end: string;
}) {
  const codes = commodities.map((c) => c.code).join(",");
  const query = useQuery({
    queryKey: ["explore-mini", codes, start, end],
    queryFn: () =>
      api.get<{ series: ExploreSeries[] }>(`/api/explore${buildQuery({ codes, start, end })}`),
    enabled: codes.length > 0,
  });

  if (!query.data) {
    return (
      <>
        {commodities.map((commodity) => (
          <div key={commodity.code} className="skeleton" style={{ height: 140 }} />
        ))}
      </>
    );
  }

  return (
    <>
      {query.data.series.map((item) => (
        <div key={item.commodity.code} className="card" style={{ padding: "var(--space-3)" }}>
          <div className="stack-2">
            <div className="row" style={{ gap: "var(--space-2)" }}>
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
              <span className="xs" style={{ fontWeight: 600, lineHeight: 1.2 }}>
                {item.commodity.name}
              </span>
            </div>
            <MiniChart
              points={item.points.map((p) => ({ date: p.date, value: p.price }))}
              color={commodityColor(item.commodity)}
              height={88}
              ariaLabel={`Pergerakan harga ${item.commodity.name}`}
            />
            <div className="row-between xs muted">
              <span className="num">{formatRupiah(item.statistics.last)}</span>
              <span className="num">{formatPercent(item.statistics.change_pct, 1, true)}</span>
            </div>
          </div>
        </div>
      ))}
    </>
  );
}

function DecompositionPanels({ data }: { data: DecompositionResponse }) {
  const color = commodityColor(data.commodity);
  const panels = [
    { key: "observed", label: "Observed — harga aktual", zero: false },
    { key: "trend", label: "Trend — arah jangka panjang", zero: false },
    { key: "seasonal_weekly", label: "Musiman mingguan (periode 7 hari)", zero: true },
    { key: "seasonal_yearly", label: "Musiman tahunan (periode 365 hari)", zero: true },
    { key: "residual", label: "Residual — bagian yang dimodelkan LightGBM", zero: true },
  ] as const;

  return (
    <div className="stack-4">
      {panels.map((panel) => (
        <div key={panel.key} className="stack-2">
          <span className="eyebrow">{panel.label}</span>
          <MiniChart
            points={data.points.map((point) => ({ date: point.date, value: point[panel.key] }))}
            color={panel.key === "residual" ? "var(--ink-secondary)" : color}
            height={110}
            showZeroLine={panel.zero}
            formatValue={compactRupiah}
            ariaLabel={panel.label}
          />
        </div>
      ))}
      <p className="xs muted">
        Observed = Trend + Musiman mingguan + Musiman tahunan + Residual. Data training
        berakhir {data.train_end}; di luar rentang tersebut komponen trend diekstrapolasi
        secara linear dan komponen musiman diulang secara periodik.
      </p>
    </div>
  );
}
