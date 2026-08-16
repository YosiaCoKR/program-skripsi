import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/useTheme";
import { Loading } from "./ui";

const ADMIN_NAV = [
  { to: "/admin", label: "Beranda", end: true },
  { to: "/admin/input-harga", label: "Input Harga" },
  { to: "/admin/riwayat", label: "Riwayat & Koreksi" },
  { to: "/admin/forecast", label: "Monitor Forecast" },
  { to: "/admin/model", label: "Manajemen Model" },
  { to: "/admin/ews", label: "Konfigurasi EWS" },
];

export function AdminLayout() {
  const { user, loading, logout } = useAuth();
  const { choice, cycle } = useTheme();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="container" style={{ paddingTop: "var(--space-7)" }}>
        <Loading label="Memeriksa sesi…" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/admin/login" replace />;
  }

  const handleLogout = async () => {
    await logout();
    navigate("/admin/login", { replace: true });
  };

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="stack-2">
          <NavLink to="/" className="brand" style={{ flexDirection: "column", alignItems: "flex-start", gap: 0 }}>
            <span className="brand-mark">PANGANIA</span>
            <span className="brand-sub">Panel Admin</span>
          </NavLink>
        </div>

        <nav className="admin-nav" aria-label="Navigasi admin">
          {ADMIN_NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "active" : "")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="stack-3" style={{ marginTop: "auto" }}>
          <hr className="rule" />
          <div className="stack-1">
            <span className="small" style={{ fontWeight: 600 }}>
              {user.name}
            </span>
            <span className="xs muted">{user.email}</span>
          </div>
          <div className="row" style={{ gap: "var(--space-2)" }}>
            <button type="button" className="btn btn-sm" onClick={cycle}>
              Tema: {choice === "system" ? "sistem" : choice === "light" ? "terang" : "gelap"}
            </button>
          </div>
          <div className="row" style={{ gap: "var(--space-2)" }}>
            <NavLink to="/" className="btn btn-sm btn-ghost">
              Lihat situs
            </NavLink>
            <button type="button" className="btn btn-sm" onClick={handleLogout}>
              Keluar
            </button>
          </div>
        </div>
      </aside>

      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}
