import type { ReactNode } from "react";
import {
  directionClass,
  directionOf,
  formatDelta,
  formatPercent,
} from "../lib/format";
import { statusStyle } from "../lib/palette";
import type { AlertLevel } from "../lib/types";

/* ============================================================== ikon
   Ikon digambar sebagai SVG inline. PRD §7.2 melarang emoji sebagai ikon:
   emoji dirender berbeda di tiap sistem operasi dan tidak bisa mewarisi
   warna teks, sehingga merusak konsistensi visual dan kontras.
   ============================================================== */

interface IconProps {
  size?: number;
  className?: string;
}

export function IconCheck({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M5.2 8.2l2 2 3.6-4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function IconAlertCircle({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M8 4.6v4.2"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <circle cx="8" cy="11.3" r="0.9" fill="currentColor" />
    </svg>
  );
}

export function IconTriangle({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M8 2.2L14.5 13.5H1.5L8 2.2z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M8 6.4v3.1"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
      <circle cx="8" cy="11.6" r="0.85" fill="currentColor" />
    </svg>
  );
}

export function IconOctagon({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M5.4 1.8h5.2l3.6 3.6v5.2l-3.6 3.6H5.4L1.8 10.6V5.4L5.4 1.8z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M6 6l4 4M10 6l-4 4"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconDash({ size = 14, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle
        cx="8"
        cy="8"
        r="6.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="2 2"
      />
      <path
        d="M5.4 8h5.2"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function IconArrow({
  direction,
  size = 12,
}: {
  direction: "up" | "down" | "flat";
  size?: number;
}) {
  if (direction === "flat") {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 12 12"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M2 6h8"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  const up = direction === "up";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
    >
      <path
        d={up ? "M6 10V2M2.6 5.4L6 2l3.4 3.4" : "M6 2v8M2.6 6.6L6 10l3.4-3.4"}
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/* ============================================================== status */

const STATUS_ICONS: Record<AlertLevel, (props: IconProps) => ReactNode> = {
  normal: IconCheck,
  waspada: IconAlertCircle,
  warning: IconTriangle,
  kritis: IconOctagon,
  tidak_tersedia: IconDash,
};

/**
 * Badge status EWS.
 *
 * Selalu ikon + label teks. Warna saja tidak pernah menjadi satu-satunya
 * pembawa makna (PRD §7.4 & §7.5).
 */
export function StatusBadge({
  level,
  title,
}: {
  level: AlertLevel | string;
  title?: string;
}) {
  const style = statusStyle(level);
  const Icon = STATUS_ICONS[level as AlertLevel] ?? IconDash;
  return (
    <span
      className={`status ${style.className}`}
      title={title ?? style.description}
    >
      <Icon size={13} className="status-icon" />
      {style.label}
    </span>
  );
}

/* ============================================================== nilai */

export function DeltaValue({
  delta,
  deltaPct,
}: {
  delta: number | null | undefined;
  deltaPct: number | null | undefined;
}) {
  const direction = directionOf(delta);
  return (
    <span
      className={`row ${directionClass(direction)}`}
      style={{ gap: 4, fontWeight: 600 }}
    >
      <IconArrow direction={direction} />
      <span className="num small">{formatDelta(delta)}</span>
      <span className="num small" style={{ opacity: 0.75 }}>
        ({formatPercent(deltaPct, 2, true)})
      </span>
    </span>
  );
}

/* ============================================================== keadaan */

export function Loading({ label = "Memuat data…" }: { label?: string }) {
  return (
    <div className="stack-3 loading-state" role="status" aria-live="polite">
      <span className="sr-only">{label}</span>
      <div
        className="skeleton loading-line"
        style={{ height: 18, width: "38%" }}
      />
      <div className="skeleton loading-panel" style={{ height: 220 }} />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <strong style={{ color: "var(--ink-secondary)" }}>{title}</strong>
      {description ? <span className="small">{description}</span> : null}
      {action}
    </div>
  );
}

export function ErrorState({
  error,
  onRetry,
}: {
  error: unknown;
  onRetry?: () => void;
}) {
  const message =
    error instanceof Error ? error.message : "Terjadi kesalahan tak terduga.";
  return (
    <div className="notice notice-critical">
      <IconTriangle size={16} />
      <div className="stack-2">
        <strong>Gagal memuat data</strong>
        <span className="small">{message}</span>
        {onRetry ? (
          <button
            type="button"
            className="btn btn-sm"
            onClick={onRetry}
            style={{ alignSelf: "start" }}
          >
            Coba lagi
          </button>
        ) : null}
      </div>
    </div>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "warning" | "critical" | "success";
  title?: string;
  children: ReactNode;
}) {
  const Icon =
    tone === "critical"
      ? IconOctagon
      : tone === "warning"
        ? IconTriangle
        : IconAlertCircle;
  return (
    <div className={`notice notice-${tone}`}>
      <Icon size={16} />
      <div>
        {title ? <strong style={{ display: "block" }}>{title}</strong> : null}
        <span className="small">{children}</span>
      </div>
    </div>
  );
}

/* ============================================================== kontrol */

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  ariaLabel: string;
}) {
  return (
    <div className="segmented" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={String(option.value)}
          type="button"
          className={option.value === value ? "is-active" : ""}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function MetricGrid({
  metrics,
}: {
  metrics: { label: string; value: string; hint?: string }[];
}) {
  return (
    <div className="grid grid-3">
      {metrics.map((metric) => (
        <div key={metric.label} className="stack-1">
          <div className="eyebrow">{metric.label}</div>
          <div
            className="num"
            style={{ fontSize: "var(--text-md)", fontWeight: 600 }}
          >
            {metric.value}
          </div>
          {metric.hint ? <div className="xs muted">{metric.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}
