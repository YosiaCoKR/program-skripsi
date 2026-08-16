/**
 * Utilitas grafik.
 *
 * Grafik digambar sebagai SVG langsung, bukan lewat pustaka bagan siap pakai.
 * Alasannya bukan gaya-gayaan: PRD §7.4 menuntut anotasi yang tidak disediakan
 * pustaka umum secara langsung — pita ketidakpastian tanpa garis tepi, garis
 * putus-putus prediksi yang menyambung tanpa celah dari titik aktual terakhir,
 * penanda berongga untuk tanggal hasil interpolasi, dan garis pemisah
 * "data terakhir".
 */

import { parseDate } from "../../lib/format";

export interface Margin {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export const DEFAULT_MARGIN: Margin = { top: 16, right: 64, bottom: 28, left: 64 };

export interface Point {
  x: number;
  y: number;
}

export interface LinearScale {
  (value: number): number;
  domain: [number, number];
  range: [number, number];
  invert(pixel: number): number;
}

export function linearScale(
  domain: [number, number],
  range: [number, number]
): LinearScale {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0 || 1;

  const scale = ((value: number) => r0 + ((value - d0) / span) * (r1 - r0)) as LinearScale;
  scale.domain = domain;
  scale.range = range;
  scale.invert = (pixel: number) => d0 + ((pixel - r0) / (r1 - r0 || 1)) * span;
  return scale;
}

export function dateToNumber(value: string | Date): number {
  return parseDate(value).getTime();
}

/** Padding domain agar garis tidak menempel di tepi area gambar. */
export function paddedExtent(
  values: number[],
  paddingRatio = 0.08
): [number, number] {
  const finite = values.filter((v) => Number.isFinite(v));
  if (finite.length === 0) return [0, 1];
  let min = Math.min(...finite);
  let max = Math.max(...finite);
  if (min === max) {
    const delta = Math.abs(min) * 0.05 || 1;
    min -= delta;
    max += delta;
  }
  const padding = (max - min) * paddingRatio;
  return [min - padding, max + padding];
}

export function linePath(points: Point[]): string {
  if (points.length === 0) return "";
  return points
    .map((point, index) => `${index === 0 ? "M" : "L"}${point.x.toFixed(2)},${point.y.toFixed(2)}`)
    .join(" ");
}

/** Area tertutup untuk pita ketidakpastian (atas maju, bawah mundur). */
export function areaPath(upper: Point[], lower: Point[]): string {
  if (upper.length === 0 || lower.length === 0) return "";
  const forward = upper
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ");
  const backward = [...lower]
    .reverse()
    .map((p) => `L${p.x.toFixed(2)},${p.y.toFixed(2)}`)
    .join(" ");
  return `${forward} ${backward} Z`;
}

/**
 * Nilai sumbu yang "bulat" secara manusiawi (1, 2, 2.5, 5, 10 x 10^n).
 * Sumbu bertuliskan 12.500 jauh lebih mudah dibaca daripada 12.437.
 */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  const span = max - min;
  const rawStep = span / Math.max(1, count);
  const magnitude = 10 ** Math.floor(Math.log10(rawStep));
  const normalized = rawStep / magnitude;

  let step: number;
  if (normalized <= 1) step = 1;
  else if (normalized <= 2) step = 2;
  else if (normalized <= 2.5) step = 2.5;
  else if (normalized <= 5) step = 5;
  else step = 10;
  step *= magnitude;

  const ticks: number[] = [];
  const start = Math.ceil(min / step) * step;
  for (let value = start; value <= max + step * 0.001; value += step) {
    ticks.push(Math.round(value / step) * step);
  }
  return ticks;
}

/** Pilih sebagian tanggal sebagai label sumbu-x agar tidak bertumpuk. */
export function pickDateTicks<T>(items: T[], maxTicks = 6): T[] {
  if (items.length <= maxTicks) return items;
  const stride = Math.ceil(items.length / maxTicks);
  const picked: T[] = [];
  for (let i = 0; i < items.length; i += stride) picked.push(items[i]);
  const last = items[items.length - 1];
  if (picked[picked.length - 1] !== last) picked.push(last);
  return picked;
}

/** Indeks titik terdekat pada sumbu-x — dasar interaksi crosshair. */
export function nearestIndex(values: number[], target: number): number {
  if (values.length === 0) return -1;
  let best = 0;
  let bestDistance = Math.abs(values[0] - target);
  for (let i = 1; i < values.length; i += 1) {
    const distance = Math.abs(values[i] - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = i;
    }
  }
  return best;
}

/** Ringkas nilai rupiah untuk label sumbu: 12500 -> "12,5rb". */
export function compactRupiah(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) {
    return `${(value / 1_000_000).toLocaleString("id-ID", { maximumFractionDigits: 1 })}jt`;
  }
  if (abs >= 1_000) {
    return `${(value / 1_000).toLocaleString("id-ID", { maximumFractionDigits: 1 })}rb`;
  }
  return value.toLocaleString("id-ID", { maximumFractionDigits: 0 });
}
