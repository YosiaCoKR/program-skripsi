import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../../lib/auth";
import { Notice } from "../../components/ui";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to="/admin" replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate("/admin", { replace: true });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Gagal masuk.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="stack-5" style={{ width: "100%", maxWidth: 400 }}>
        <div className="stack-2" style={{ textAlign: "center" }}>
          <span className="brand-mark" style={{ fontSize: "var(--text-xl)" }}>
            PANGANIA
          </span>
          <span className="brand-sub">Panel Admin — Harga Pangan DIY</span>
        </div>

        <form className="login-card stack-4" onSubmit={handleSubmit}>
          <div className="stack-1">
            <h1 className="section-title">Masuk</h1>
            <p className="small muted">
              Panel ini hanya untuk pengelola sistem. Halaman publik dapat diakses tanpa
              masuk.
            </p>
          </div>

          {error ? (
            <Notice tone="critical" title="Gagal masuk">
              {error}
            </Notice>
          ) : null}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@pangania.id"
            />
          </div>

          <div className="field">
            <label htmlFor="password">Kata sandi</label>
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>

          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Memproses…" : "Masuk"}
          </button>

          <p className="xs muted">
            Setelah lima percobaan gagal, akses dikunci sementara selama lima menit.
          </p>
        </form>

        <Link to="/" className="xs muted" style={{ textAlign: "center" }}>
          ← Kembali ke halaman publik
        </Link>
      </div>
    </div>
  );
}
