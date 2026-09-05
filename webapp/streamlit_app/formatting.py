"""Utilitas format tampilan yang dipakai bersama antar halaman.

Dipisah dari `views/dashboard.py` supaya halaman detail komoditas bisa
memakai format harga, waktu, dan status tren yang sama tanpa duplikasi
maupun circular import.
"""

from __future__ import annotations

from datetime import datetime


def format_rupiah(nilai: float) -> str:
    return f"{nilai:,.0f}".replace(",", ".")


def format_waktu_pembaruan(diperbarui_pada: datetime) -> str:
    """Format waktu update jadi relatif ("3 jam lalu") kalau masih hari ini."""
    selisih_jam = (datetime.now() - diperbarui_pada).total_seconds() / 3600
    if selisih_jam < 1:
        return "Diperbarui baru saja"
    if selisih_jam < 24:
        return f"Diperbarui {int(selisih_jam)} jam lalu"
    return f"Diperbarui {diperbarui_pada.strftime('%d %b %Y, %H:%M')}"


def tren_status(harga_terbaru: float, harga_kemarin: float) -> tuple[str, str]:
    """(status, label) dibanding harga kemarin — status: "naik" | "turun" | "tetap".

    Pemetaan status ke kelas CSS diserahkan ke tiap halaman karena kontras
    warna beda-beda tergantung latar (kartu putih vs hero gelap/gradasi).
    """
    selisih = harga_terbaru - harga_kemarin
    if selisih > 0:
        persen = selisih / harga_kemarin * 100
        return "naik", f"▲ {persen:.1f}%"
    if selisih < 0:
        persen = abs(selisih) / harga_kemarin * 100
        return "turun", f"▼ {persen:.1f}%"
    return "tetap", "— tetap"
