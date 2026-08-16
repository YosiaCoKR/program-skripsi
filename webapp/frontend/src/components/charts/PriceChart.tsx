import { useId, useMemo, useRef, useState } from "react";
import {
  DEFAULT_MARGIN,
  areaPath,
  compactRupiah,
  dateToNumber,
  linePath,
  linearScale,
  nearestIndex,
  niceTicks,
  paddedExtent,
  pickDateTicks,
  type Point,
} from "./chartUtils";
import { formatDateCompact, formatDateLong, formatRupiah } from "../../lib/format";

export interface ChartSeries {
  key: string;
  label: string;
  color: string;
  points: { date: string; value: number; isInterpolated?: boolean }[];
  /** Titik prediksi, digambar putus-putus menyambung dari aktual terakhir. */
  forecast?: { date: string; value: number; lower?: number | null; upper?: number | null }[];
}

interface Props {
  series: ChartSeries[];
  height?: number;
  /** Tanggal data aktual terakhir — digambar sebagai garis pemisah. */
  lastActualDate?: string | null;
  showLegend?: boolean;
  /** Label langsung di ujung garis; hanya untuk maksimal 4 seri (PRD §7.4). */
  directLabels?: boolean;
  yLabel?: string;
  emptyMessage?: string;
}

const MAX_DIRECT_LABELS = 4;

export function PriceChart({
  series,
  height = 320,
  lastActualDate,
  showLegend = true,
  directLabels = true,
  yLabel,
  emptyMessage = "Belum ada data untuk ditampilkan.",
}: Props) {
  const clipId = useId().replace(/:/g, "");
  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const [width, setWidth] = useState(760);

  const margin = DEFAULT_MARGIN;

  // Sumbu-x memakai gabungan seluruh tanggal (aktual + prediksi) supaya
  // seri dengan panjang berbeda tetap sejajar.
  const model = useMemo(() => {
    const dateSet = new Set<string>();
    for (const item of series) {
      item.points.forEach((p) => dateSet.add(p.date));
      item.forecast?.forEach((p) => dateSet.add(p.date));
    }
    const dates = [...dateSet].sort();
    const xs = dates.map(dateToNumber);

    const values: number[] = [];
    for (const item of series) {
      item.points.forEach((p) => values.push(p.value));
      item.forecast?.forEach((p) => {
        values.push(p.value);
        if (p.lower != null) values.push(p.lower);
        if (p.upper != null) values.push(p.upper);
      });
    }

    return { dates, xs, values };
  }, [series]);

  const hasData = model.dates.length > 0 && model.values.length > 0;

  const innerWidth = Math.max(120, width - margin.left - margin.right);
  const innerHeight = Math.max(80, height - margin.top - margin.bottom);

  const xScale = useMemo(
    () =>
      linearScale(
        [model.xs[0] ?? 0, model.xs[model.xs.length - 1] ?? 1],
        [margin.left, margin.left + innerWidth]
      ),
    [model.xs, margin.left, innerWidth]
  );

  const yDomain = useMemo(() => paddedExtent(model.values), [model.values]);
  const yScale = useMemo(
    () => linearScale(yDomain, [margin.top + innerHeight, margin.top]),
    [yDomain, margin.top, innerHeight]
  );

  const yTicks = useMemo(() => niceTicks(yDomain[0], yDomain[1], 5), [yDomain]);
  const xTicks = useMemo(() => pickDateTicks(model.dates, 6), [model.dates]);

  // Ukur lebar kontainer agar grafik responsif tanpa pustaka tambahan.
  const measure = (node: HTMLDivElement | null) => {
    if (!node) return;
    (wrapRef as { current: HTMLDivElement | null }).current = node;
    const next = node.clientWidth;
    if (next > 0 && Math.abs(next - width) > 2) setWidth(next);
  };

  if (!hasData) {
    return <div className="empty">{emptyMessage}</div>;
  }

  const dividerX = lastActualDate ? xScale(dateToNumber(lastActualDate)) : null;

  const handleMove = (event: React.MouseEvent<SVGRectElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const value = xScale.invert(event.clientX - bounds.left + margin.left);
    setHoverIndex(nearestIndex(model.xs, value));
  };

  const hoverDate = hoverIndex !== null ? model.dates[hoverIndex] : null;
  const hoverX = hoverDate !== null ? xScale(dateToNumber(hoverDate)) : null;

  return (
    <div className="stack-3">
      <div className="chart-wrap" ref={measure}>
        <svg
          className="chart-svg"
          viewBox={`0 0 ${width} ${height}`}
          height={height}
          role="img"
          aria-label={`Grafik harga: ${series.map((s) => s.label).join(", ")}`}
        >
          <defs>
            <clipPath id={`clip-${clipId}`}>
              <rect x={margin.left} y={margin.top} width={innerWidth} height={innerHeight} />
            </clipPath>
          </defs>

          {/* Grid resesif — tidak pernah bersaing dengan data. */}
          <g aria-hidden="true">
            {yTicks.map((tick) => (
              <line
                key={tick}
                x1={margin.left}
                x2={margin.left + innerWidth}
                y1={yScale(tick)}
                y2={yScale(tick)}
                stroke="var(--grid-line)"
                strokeWidth={1}
              />
            ))}
          </g>

          {/* Sumbu-y */}
          <g>
            {yTicks.map((tick) => (
              <text
                key={tick}
                x={margin.left - 10}
                y={yScale(tick)}
                textAnchor="end"
                dominantBaseline="middle"
                fill="var(--axis-text)"
                fontSize={11}
                fontFamily="var(--font-mono)"
              >
                {compactRupiah(tick)}
              </text>
            ))}
            {yLabel ? (
              <text
                x={margin.left - 10}
                y={margin.top - 6}
                textAnchor="end"
                fill="var(--axis-text)"
                fontSize={10}
                fontFamily="var(--font-mono)"
              >
                {yLabel}
              </text>
            ) : null}
          </g>

          {/* Sumbu-x */}
          <g>
            <line
              x1={margin.left}
              x2={margin.left + innerWidth}
              y1={margin.top + innerHeight}
              y2={margin.top + innerHeight}
              stroke="var(--axis-line)"
              strokeWidth={1}
            />
            {xTicks.map((date) => (
              <text
                key={date}
                x={xScale(dateToNumber(date))}
                y={margin.top + innerHeight + 16}
                textAnchor="middle"
                fill="var(--axis-text)"
                fontSize={11}
                fontFamily="var(--font-mono)"
              >
                {formatDateCompact(date)}
              </text>
            ))}
          </g>

          <g clipPath={`url(#clip-${clipId})`}>
            {/* Pita ketidakpastian: isian tanpa garis tepi. */}
            {series.map((item) => {
              if (!item.forecast?.length) return null;
              const upper: Point[] = [];
              const lower: Point[] = [];
              for (const point of item.forecast) {
                if (point.lower == null || point.upper == null) continue;
                const x = xScale(dateToNumber(point.date));
                upper.push({ x, y: yScale(point.upper) });
                lower.push({ x, y: yScale(point.lower) });
              }
              if (upper.length < 2) return null;
              return (
                <path
                  key={`band-${item.key}`}
                  d={areaPath(upper, lower)}
                  fill={item.color}
                  fillOpacity={0.12}
                  stroke="none"
                />
              );
            })}

            {/* Garis aktual: solid 2px. */}
            {series.map((item) => {
              const points = item.points.map((p) => ({
                x: xScale(dateToNumber(p.date)),
                y: yScale(p.value),
              }));
              return (
                <path
                  key={`line-${item.key}`}
                  d={linePath(points)}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              );
            })}

            {/* Garis prediksi: putus-putus, menyambung dari titik aktual
                terakhir tanpa celah. */}
            {series.map((item) => {
              if (!item.forecast?.length) return null;
              const lastActual = item.points[item.points.length - 1];
              const joined = lastActual
                ? [{ date: lastActual.date, value: lastActual.value }, ...item.forecast]
                : item.forecast;
              const points = joined.map((p) => ({
                x: xScale(dateToNumber(p.date)),
                y: yScale(p.value),
              }));
              return (
                <path
                  key={`forecast-${item.key}`}
                  d={linePath(points)}
                  fill="none"
                  stroke={item.color}
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  strokeLinecap="round"
                />
              );
            })}

            {/* Titik hasil interpolasi: marker BERONGGA, bukan padat —
                pengguna harus bisa membedakan data survei asli dari data
                yang diisi (PRD §7.6 poin 3). */}
            {series.length <= 2
              ? series.map((item) =>
                  item.points
                    .filter((p) => p.isInterpolated)
                    .map((p) => (
                      <circle
                        key={`interp-${item.key}-${p.date}`}
                        cx={xScale(dateToNumber(p.date))}
                        cy={yScale(p.value)}
                        r={2.4}
                        fill="var(--paper-raised)"
                        stroke={item.color}
                        strokeWidth={1}
                      />
                    ))
                )
              : null}

            {/* Titik prediksi ditandai jelas. */}
            {series.map((item) =>
              item.forecast?.map((p) => (
                <circle
                  key={`fp-${item.key}-${p.date}`}
                  cx={xScale(dateToNumber(p.date))}
                  cy={yScale(p.value)}
                  r={4}
                  fill={item.color}
                  stroke="var(--paper-raised)"
                  strokeWidth={2}
                />
              ))
            )}
          </g>

          {/* Pemisah "data terakhir". */}
          {dividerX !== null ? (
            <g>
              <line
                x1={dividerX}
                x2={dividerX}
                y1={margin.top}
                y2={margin.top + innerHeight}
                stroke="var(--ink-muted)"
                strokeWidth={1}
                strokeDasharray="2 3"
              />
              <text
                x={dividerX + 5}
                y={margin.top + 10}
                fill="var(--ink-muted)"
                fontSize={10}
                fontFamily="var(--font-mono)"
              >
                data terakhir
              </text>
            </g>
          ) : null}

          {/* Label langsung di ujung garis, maksimal 4 seri. */}
          {directLabels && series.length <= MAX_DIRECT_LABELS
            ? series.map((item) => {
                const forecastLast = item.forecast?.[item.forecast.length - 1];
                const last = forecastLast
                  ? { date: forecastLast.date, value: forecastLast.value }
                  : item.points[item.points.length - 1];
                if (!last) return null;
                return (
                  <text
                    key={`label-${item.key}`}
                    x={xScale(dateToNumber(last.date)) + 8}
                    y={yScale(last.value)}
                    dominantBaseline="middle"
                    fill={item.color}
                    fontSize={11}
                    fontWeight={600}
                    fontFamily="var(--font-mono)"
                  >
                    {compactRupiah(last.value)}
                  </text>
                );
              })
            : null}

          {/* Crosshair */}
          {hoverX !== null ? (
            <line
              x1={hoverX}
              x2={hoverX}
              y1={margin.top}
              y2={margin.top + innerHeight}
              stroke="var(--ink-muted)"
              strokeWidth={1}
            />
          ) : null}

          {/* Area tangkap interaksi — hit target lebih besar dari mark. */}
          <rect
            x={margin.left}
            y={margin.top}
            width={innerWidth}
            height={innerHeight}
            fill="transparent"
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverIndex(null)}
          />
        </svg>

        {hoverDate ? (
          <Tooltip
            date={hoverDate}
            series={series}
            x={hoverX ?? 0}
            containerWidth={width}
          />
        ) : null}
      </div>

      {showLegend && series.length >= 2 ? (
        <div className="chart-legend">
          {series.map((item) => (
            <span key={item.key} className="legend-item">
              <span className="legend-swatch" style={{ background: item.color }} />
              {item.label}
            </span>
          ))}
        </div>
      ) : null}

      <div className="chart-legend muted xs">
        <span className="legend-item">
          <span className="legend-swatch" style={{ background: "var(--ink-muted)" }} />
          Harga aktual
        </span>
        <span className="legend-item">
          <span
            className="legend-swatch dashed"
            style={{ color: "var(--ink-muted)", background: "none" }}
          />
          Prediksi
        </span>
        <span className="legend-item">
          <svg width="12" height="12" aria-hidden="true">
            <circle cx="6" cy="6" r="3" fill="var(--paper-raised)" stroke="var(--ink-muted)" />
          </svg>
          Data interpolasi
        </span>
      </div>
    </div>
  );
}

function Tooltip({
  date,
  series,
  x,
  containerWidth,
}: {
  date: string;
  series: ChartSeries[];
  x: number;
  containerWidth: number;
}) {
  const rows = series.map((item) => {
    const actual = item.points.find((p) => p.date === date);
    const forecast = item.forecast?.find((p) => p.date === date);
    return { item, actual, forecast };
  });

  const anyValue = rows.some((row) => row.actual || row.forecast);
  if (!anyValue) return null;

  // Balikkan arah tooltip bila mendekati tepi kanan.
  const flip = x > containerWidth - 200;

  return (
    <div
      className="chart-tooltip"
      style={{
        left: flip ? undefined : x + 12,
        right: flip ? containerWidth - x + 12 : undefined,
        top: 8,
      }}
    >
      <div className="xs muted" style={{ marginBottom: 4 }}>
        {formatDateLong(date)}
      </div>
      {rows.map(({ item, actual, forecast }) => {
        if (!actual && !forecast) return null;
        return (
          <div key={item.key} className="tooltip-row">
            <span className="legend-item">
              <span className="legend-swatch" style={{ background: item.color }} />
              {item.label}
              {forecast && !actual ? <span className="muted"> (prediksi)</span> : null}
              {actual?.isInterpolated ? <span className="muted"> (interpolasi)</span> : null}
            </span>
            <span className="num" style={{ fontWeight: 600 }}>
              {formatRupiah(actual?.value ?? forecast?.value)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
