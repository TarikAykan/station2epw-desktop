"""
Meteorolojik birimleri EPW'nin beklediği birimlere dönüştürme.

Çıktı birimleri:
- Sıcaklık: °C
- Basınç: Pa
- Rüzgar: m/s
- Radyasyon: Wh/m² (saatlik integral; W/m² için saatlik ortalama varsayımı)
- Yağış: mm
"""

from __future__ import annotations

import pandas as pd


class UnitProfile:
    """Kullanıcı seçimleri."""

    def __init__(
        self,
        temperature: str = "C",
        pressure: str = "Pa",
        wind_speed: str = "m/s",
        radiation: str = "Wh/m2",
        albedo: str = "0-1",
    ):
        self.temperature = temperature  # C, K, F
        self.pressure = pressure  # Pa, hPa, kPa
        self.wind_speed = wind_speed  # m/s, km/h, knot
        self.radiation = radiation  # Wh/m2, W/m2
        self.albedo = albedo  # 0-1, %


def convert_temperature_series(s: pd.Series, from_unit: str) -> pd.Series:
    u = from_unit.upper()
    x = pd.to_numeric(s, errors="coerce")
    if u in ("C", "°C", "CELSIUS"):
        return x
    if u in ("K", "KELVIN"):
        return x - 273.15
    if u in ("F", "°F", "FAHRENHEIT"):
        return (x - 32.0) * 5.0 / 9.0
    return x


def convert_pressure_series(s: pd.Series, from_unit: str) -> pd.Series:
    u = from_unit.lower().replace(" ", "")
    x = pd.to_numeric(s, errors="coerce")
    if u in ("pa",):
        return x
    if u in ("hpa", "mbar", "millibar"):
        return x * 100.0
    if u in ("kpa",):
        return x * 1000.0
    return x


def convert_wind_speed_series(s: pd.Series, from_unit: str) -> pd.Series:
    u = from_unit.lower().replace(" ", "")
    x = pd.to_numeric(s, errors="coerce")
    if u in ("m/s", "ms", "ms-1"):
        return x
    if u in ("km/h", "kmh", "kmh-1"):
        return x / 3.6
    if u in ("knot", "knots", "kt"):
        return x * 0.514444
    return x


def convert_radiation_series(s: pd.Series, from_unit: str) -> tuple[pd.Series, bool]:
    """
    Wh/m² hedefler.
    W/m² ise saatlik ortalama güç varsayımı: Wh = W * 1 saat.
    Dönüş: (seri, w_per_m2_assumption_applied)
    """
    u = from_unit.lower().replace(" ", "")
    x = pd.to_numeric(s, errors="coerce")
    if u in ("wh/m2", "wh/m²", "whm2", "wh/m**2"):
        return x, False
    if u in ("w/m2", "w/m²", "wm2", "w/m**2"):
        # Saatlik veri: ortalama güç * 1h = Wh/m²
        return x * 1.0, True
    return x, False


def convert_albedo_series(s: pd.Series, from_unit: str) -> pd.Series:
    """
    Albedo'yu 0-1 ölçeğine çevirir.
    '%' seçilirse 100'e bölünür.
    """
    u = from_unit.strip().lower().replace(" ", "")
    x = pd.to_numeric(s, errors="coerce")
    if u in ("%", "percent", "pct"):
        return x / 100.0
    return x


def summarize_conversions(profile: UnitProfile) -> list[str]:
    """Rapor için insan okunur özet satırları."""
    lines = [
        f"Sıcaklık kaynağı: {profile.temperature} → °C",
        f"Basınç kaynağı: {profile.pressure} → Pa",
        f"Rüzgar hızı kaynağı: {profile.wind_speed} → m/s",
        f"Radyasyon kaynağı: {profile.radiation} → Wh/m²",
        f"Albedo kaynağı: {profile.albedo} → 0-1",
    ]
    norm = profile.radiation.lower().replace(" ", "").replace("²", "2").replace("**", "")
    if norm in ("w/m2", "wm2"):
        lines.append(
            "Not: W/m² → Wh/m² için saatlik ortalama güç varsayıldı (×1 saat). Bu varsayım raporda yer alır."
        )
    return lines
