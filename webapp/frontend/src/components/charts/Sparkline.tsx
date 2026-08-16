import { linePath, linearScale, paddedExtent } from "./chartUtils";

interface Props {
  values: number[];
  color: string;
  width?: number;
  height?: number;
  label?: string;
}

/**
 * Sparkline untuk kartu komoditas.
 *
 * Sengaja tanpa sumbu, grid, atau label: perannya menunjukkan BENTUK
 * pergerakan, bukan nilai eksak. Nilai eksaknya sudah tampil sebagai angka
 * besar di sebelahnya.
 */
export function Sparkline({ values, color, width = 120, height = 32, label }: Props) {
  if (values.length < 2) {
    return <div style={{ height }} aria-hidden="true" />;
  }

  const [min, max] = paddedExtent(values, 0.12);
  const xScale = linearScale([0, values.length - 1], [1, width - 1]);
  const yScale = linearScale([min, max], [height - 2, 2]);

  const points = values.map((value, index) => ({ x: xScale(index), y: yScale(value) }));
  const last = points[points.length - 1];

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label ?? "Tren 30 hari terakhir"}
      style={{ overflow: "visible" }}
    >
      <path
        d={linePath(points)}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={last.x} cy={last.y} r={2.5} fill={color} />
    </svg>
  );
}
