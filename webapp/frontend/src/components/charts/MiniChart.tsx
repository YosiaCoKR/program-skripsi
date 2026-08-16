import { useMemo } from "react";
import {
  compactRupiah,
  dateToNumber,
  linePath,
  linearScale,
  niceTicks,
  paddedExtent,
} from "./chartUtils";
import { formatDateCompact } from "../../lib/format";

export interface MiniPoint {
  date: string;
  value: number;
}

interface Props {
  points: MiniPoint[];
  color: string;
  height?: number;
  /** Garis nol — berguna untuk komponen residual dan musiman. */
  showZeroLine?: boolean;
  formatValue?: (value: number) => string;
  ariaLabel?: string;
}

/**
 * Panel kecil untuk small multiples.
 *
 * Setiap panel punya skala sumbu-y sendiri (PRD §7.4). Ini disengaja: beras
 * (~Rp 12.000) dan cabai (~Rp 70.000) tidak bisa berbagi satu skala tanpa
 * membuat salah satunya terlihat datar sepenuhnya.
 */
export function MiniChart({
  points,
  color,
  height = 96,
  showZeroLine = false,
  formatValue = compactRupiah,
  ariaLabel,
}: Props) {
  const width = 320;
  const margin = { top: 8, right: 8, bottom: 18, left: 44 };

  const model = useMemo(() => {
    const values = points.map((p) => p.value);
    const xs = points.map((p) => dateToNumber(p.date));
    return { values, xs };
  }, [points]);

  if (points.length < 2) {
    return (
      <div className="empty" style={{ height, padding: "var(--space-4)" }}>
        <span className="xs">Data belum cukup</span>
      </div>
    );
  }

  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;

  const domain = paddedExtent(model.values, 0.1);
  const xScale = linearScale(
    [model.xs[0], model.xs[model.xs.length - 1]],
    [margin.left, margin.left + innerWidth]
  );
  const yScale = linearScale(domain, [margin.top + innerHeight, margin.top]);

  const ticks = niceTicks(domain[0], domain[1], 2);
  const path = linePath(points.map((p) => ({ x: xScale(dateToNumber(p.date)), y: yScale(p.value) })));

  const zeroInRange = showZeroLine && domain[0] <= 0 && domain[1] >= 0;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height, display: "block" }}
      role="img"
      aria-label={ariaLabel}
    >
      {ticks.map((tick) => (
        <g key={tick}>
          <line
            x1={margin.left}
            x2={margin.left + innerWidth}
            y1={yScale(tick)}
            y2={yScale(tick)}
            stroke="var(--grid-line)"
            strokeWidth={1}
          />
          <text
            x={margin.left - 6}
            y={yScale(tick)}
            textAnchor="end"
            dominantBaseline="middle"
            fill="var(--axis-text)"
            fontSize={9}
            fontFamily="var(--font-mono)"
          >
            {formatValue(tick)}
          </text>
        </g>
      ))}

      {zeroInRange ? (
        <line
          x1={margin.left}
          x2={margin.left + innerWidth}
          y1={yScale(0)}
          y2={yScale(0)}
          stroke="var(--axis-line)"
          strokeWidth={1}
          strokeDasharray="3 2"
        />
      ) : null}

      <path d={path} fill="none" stroke={color} strokeWidth={1.75} strokeLinejoin="round" />

      <text
        x={margin.left}
        y={height - 4}
        fill="var(--axis-text)"
        fontSize={9}
        fontFamily="var(--font-mono)"
      >
        {formatDateCompact(points[0].date)}
      </text>
      <text
        x={margin.left + innerWidth}
        y={height - 4}
        textAnchor="end"
        fill="var(--axis-text)"
        fontSize={9}
        fontFamily="var(--font-mono)"
      >
        {formatDateCompact(points[points.length - 1].date)}
      </text>
    </svg>
  );
}
