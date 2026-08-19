import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { formatDateLong } from "../lib/format";
import type { MetaResponse } from "../lib/types";
import { useTheme } from "../lib/useTheme";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/prediksi", label: "Prediksi" },
  { to: "/eksplorasi", label: "Eksplorasi Data" },
  { to: "/peringatan", label: "Peringatan Dini" },
  { to: "/proyeksi", label: "Proyeksi" },
];

function ThemeToggle() {
  const { choice, cycle } = useTheme();
  const label =
    choice === "system"
      ? "Tema: sistem"
      : choice === "light"
        ? "Tema: terang"
        : "Tema: gelap";

  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm"
      onClick={cycle}
      title={label}
      aria-label={label}
    >
      {choice === "dark" ? (
        <svg
          width="15"
          height="15"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <path
            d="M13.2 9.6A5.6 5.6 0 016.4 2.8a5.6 5.6 0 106.8 6.8z"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinejoin="round"
          />
        </svg>
      ) : choice === "light" ? (
        <svg
          width="15"
          height="15"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="8"
            cy="8"
            r="3.1"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M8 1.4v1.5M8 13.1v1.5M1.4 8h1.5M13.1 8h1.5M3.3 3.3l1.1 1.1M11.6 11.6l1.1 1.1M12.7 3.3l-1.1 1.1M4.4 11.6l-1.1 1.1"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      ) : (
        <svg
          width="15"
          height="15"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden="true"
        >
          <rect
            x="1.8"
            y="3.2"
            width="12.4"
            height="8.4"
            rx="1.2"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          <path
            d="M5.4 14h5.2"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
          />
        </svg>
      )}
    </button>
  );
}

export function Layout() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user } = useAuth();
  const { data: meta } = useQuery({
    queryKey: ["meta"],
    queryFn: () => api.get<MetaResponse>("/api/meta"),
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="shell">
      <a className="skip-link" href="#konten">
        Lompat ke konten utama
      </a>

      <header className="masthead">
        <div className="container masthead-inner">
          <NavLink to="/" className="brand">
            <span className="brand-mark">PANGANIA</span>
            <span className="brand-sub">Harga Pangan DIY</span>
          </NavLink>

          <button
            type="button"
            className="mobile-menu-toggle"
            aria-expanded={mobileMenuOpen}
            aria-controls="navigasi-utama"
            aria-label={mobileMenuOpen ? "Tutup menu" : "Buka menu"}
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            <span aria-hidden="true" />
            <span aria-hidden="true" />
            <span aria-hidden="true" />
          </button>

          <nav
            id="navigasi-utama"
            className={`nav${mobileMenuOpen ? " is-open" : ""}`}
            aria-label="Navigasi utama"
          >
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `nav-link${isActive ? " active" : ""}`
                }
                onClick={() => setMobileMenuOpen(false)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div
            className={`row mobile-menu-actions${mobileMenuOpen ? " is-open" : ""}`}
            style={{ gap: "var(--space-2)" }}
          >
            <ThemeToggle />
            <NavLink
              to={user ? "/admin" : "/admin/login"}
              className="btn btn-sm"
              onClick={() => setMobileMenuOpen(false)}
            >
              {user ? "Panel Admin" : "Masuk"}
            </NavLink>
          </div>
        </div>
      </header>

      <main id="konten" className="page">
        <div className="container">
          <Outlet />
        </div>
      </main>

      <footer className="footer">
        <div className="container stack-2">
          <div className="row-between">
            <span>
              Sumber data: {meta?.data_source ?? "Bank Indonesia — PIHPS"} ·{" "}
              {meta?.region ?? "Provinsi DIY"}
            </span>
            <span className="num">
              Data terakhir: {formatDateLong(meta?.latest_data_date)}
            </span>
          </div>
          <p style={{ maxWidth: "78ch" }}>
            Prediksi pada sistem ini bersifat indikatif dan bukan jaminan harga.
            Sekitar {meta?.interpolated_pct ?? 30}% tanggal merupakan hasil
            interpolasi karena pasar tidak disurvei pada akhir pekan dan hari
            libur; titik tersebut ditandai khusus pada setiap grafik.
          </p>
          <p>
            Dikembangkan sebagai bagian penelitian skripsi Yosia Sipahutar —
            optimasi hyperparameter LightGBM menggunakan Genetic Algorithm.
          </p>
        </div>
      </footer>
    </div>
  );
}
