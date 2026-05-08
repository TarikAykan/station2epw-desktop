"""PVsyst odaklı kalite kontrolleri."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class PvsystCheck:
    name: str
    status: str  # ok | warning | error
    description: str
    critical: bool = False


def run_pvsyst_checks(df: pd.DataFrame) -> list[PvsystCheck]:
    res: list[PvsystCheck] = []

    def nser(col: str) -> pd.Series | None:
        if col not in df.columns:
            return None
        return pd.to_numeric(df[col], errors="coerce")

    n = len(df)
    if n in (8760, 8784):
        res.append(PvsystCheck("8760/8784 saat", "ok", f"{n} satır."))
    else:
        res.append(PvsystCheck("8760/8784 saat", "warning", f"{n} satır; tam yıl olmayabilir."))

    required = {
        "GHI": "global_horizontal_radiation",
        "DHI": "diffuse_horizontal_radiation",
        "DNI": "direct_normal_radiation",
        "Ambient Temperature": "dry_bulb",
        "Wind Speed": "wind_speed",
    }
    for name, key in required.items():
        if key in df.columns and not pd.to_numeric(df[key], errors="coerce").isna().all():
            res.append(PvsystCheck(f"{name} var mı", "ok", "Alan mevcut."))
        else:
            res.append(PvsystCheck(f"{name} var mı", "warning", "Alan eksik veya tamamen boş."))

    ghi = nser("global_horizontal_radiation")
    dhi = nser("diffuse_horizontal_radiation")
    dni = nser("direct_normal_radiation")

    if ghi is not None:
        neg = int((ghi < 0).sum())
        res.append(PvsystCheck("GHI negatif", "error" if neg else "ok", f"Negatif kayıt: {neg}", critical=neg > 0))
    if dhi is not None:
        gt = int(((dhi > ghi) & ghi.notna()).sum()) if ghi is not None else 0
        res.append(PvsystCheck("DHI > GHI", "warning" if gt else "ok", f"Satır sayısı: {gt}"))
    if dni is not None:
        neg = int((dni < 0).sum())
        res.append(PvsystCheck("DNI negatif", "error" if neg else "ok", f"Negatif kayıt: {neg}", critical=neg > 0))

    alb = nser("albedo")
    if alb is not None:
        bad = int(((alb < 0) | (alb > 1)).sum())
        res.append(PvsystCheck("Albedo 0-1", "warning" if bad else "ok", f"Aralık dışı kayıt: {bad}"))

    # Gece için kaba kontrol (hour 1..24 kabulü)
    if "hour" in df.columns and ghi is not None:
        h = pd.to_numeric(df["hour"], errors="coerce")
        night = (h <= 6) | (h >= 20)
        high_night = int((night & (ghi > 150)).sum())
        res.append(PvsystCheck("Gece yüksek radyasyon", "warning" if high_night else "ok", f"Şüpheli kayıt: {high_night}"))

    if "year" in df.columns and "month" in df.columns and "day" in df.columns and "hour" in df.columns:
        keys = df[["year", "month", "day", "hour"]].copy()
        sorted_keys = keys.sort_values(["year", "month", "day", "hour"]).reset_index(drop=True)
        mono = keys.reset_index(drop=True).equals(sorted_keys)
        res.append(PvsystCheck("Zaman sırası", "ok" if mono else "warning", "Artan" if mono else "Artış bozulmuş."))

    return res


def has_pvsyst_critical_errors(results: list[PvsystCheck]) -> bool:
    return any(r.status == "error" and r.critical for r in results)
