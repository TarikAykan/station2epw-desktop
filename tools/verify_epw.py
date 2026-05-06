#!/usr/bin/env python3
"""
EnergyPlus EPW çıktısı ve birim dönüşümleri için otomatik doğrulama.

Çalıştırma (proje kökü station2epw_desktop):
    python tools/verify_epw.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from app.core.column_mapper import guess_mapping, validate_mapping
from app.core.epw_schema import EPW_HOURLY_COLUMNS, epw_header_lines
from app.core.epw_writer import (
    build_processed_dataframe,
    dataframe_row_to_epw_line,
    sort_processed_chronologically,
    write_epw_file,
)
from app.core.file_reader import load_tabular_file
from app.core.unit_converter import (
    UnitProfile,
    convert_pressure_series,
    convert_radiation_series,
    convert_wind_speed_series,
)
from app.core.validator import normalize_hours_for_epw


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_hour_conversion() -> None:
    s = pd.Series([0, 12, 23])
    out, shifted = normalize_hours_for_epw(s)
    _assert(shifted is True, "0–23 için dönüşüm bayrağı True olmalı")
    _assert(list(out) == [1, 13, 24], f"Beklenen [1,13,24], gelen {list(out)}")

    s2 = pd.Series([1, 12, 24])
    out2, sh2 = normalize_hours_for_epw(s2)
    _assert(sh2 is False, "1–24 için kaydırma olmamalı")
    _assert(list(out2) == [1, 12, 24], f"Beklenen [1,12,24], gelen {list(out2)}")


def test_pressure_wind_radiation() -> None:
    p = convert_pressure_series(pd.Series([1013.25]), "hPa").iloc[0]
    _assert(abs(float(p) - 101325.0) < 0.01, f"hPa→Pa hatalı: {p}")

    ws_kmh = convert_wind_speed_series(pd.Series([36.0]), "km/h").iloc[0]
    _assert(abs(float(ws_kmh) - 10.0) < 1e-9, f"km/h→m/s hatalı: {ws_kmh}")

    ws_kt = convert_wind_speed_series(pd.Series([10.0]), "knot").iloc[0]
    _assert(abs(float(ws_kt) - 5.14444) < 1e-4, f"knot→m/s hatalı: {ws_kt}")

    rad, assumed = convert_radiation_series(pd.Series([500.0]), "W/m2")
    _assert(assumed is True, "W/m² için varsayım bayrağı")
    _assert(abs(float(rad.iloc[0]) - 500.0) < 1e-9, "W/m²→Wh/m² ×1 saat")

    rad2, assumed2 = convert_radiation_series(pd.Series([300.0]), "Wh/m2")
    _assert(assumed2 is False, "Wh/m² için varsayım olmamalı")
    _assert(abs(float(rad2.iloc[0]) - 300.0) < 1e-9, "Wh/m² değişmeden kalmalı")


def test_epw_column_order_matches_energyplus() -> None:
    """EnergyPlus Weather File Dictionary ile aynı sıra (PDF Table)."""
    ref = [
        "Year",
        "Month",
        "Day",
        "Hour",
        "Minute",
        "Data Source and Uncertainty Flags",
        "Dry Bulb Temperature",
        "Dew Point Temperature",
        "Relative Humidity",
        "Atmospheric Station Pressure",
        "Extraterrestrial Horizontal Radiation",
        "Extraterrestrial Direct Normal Radiation",
        "Horizontal Infrared Radiation Intensity",
        "Global Horizontal Radiation",
        "Direct Normal Radiation",
        "Diffuse Horizontal Radiation",
        "Global Horizontal Illuminance",
        "Direct Normal Illuminance",
        "Diffuse Horizontal Illuminance",
        "Zenith Luminance",
        "Wind Direction",
        "Wind Speed",
        "Total Sky Cover",
        "Opaque Sky Cover",
        "Visibility",
        "Ceiling Height",
        "Present Weather Observation",
        "Present Weather Codes",
        "Precipitable Water",
        "Aerosol Optical Depth",
        "Snow Depth",
        "Days Since Last Snowfall",
        "Albedo",
        "Liquid Precipitation Depth",
        "Liquid Precipitation Quantity",
    ]
    _assert(EPW_HOURLY_COLUMNS == ref, "EPW_HOURLY_COLUMNS sırası EnergyPlus sözlüğü ile uyuşmuyor")


def test_location_line_order() -> None:
    lines = epw_header_lines(
        city="X",
        state_region="Y",
        country="Z",
        source="S",
        wmo_or_code="123456",
        latitude=41.2,
        longitude=36.3,
        elevation_m=55.0,
        timezone_offset=3.0,
        comments1="c1",
        comments2="c2",
    )
    loc = lines[0].split(",")
    _assert(loc[0] == "LOCATION", "LOCATION başlığı")
    # N2..N5: lat, lon, TZ, elev (EnergyPlus IDD)
    _assert(abs(float(loc[6]) - 41.2) < 1e-9, "Latitude alanı")
    _assert(abs(float(loc[7]) - 36.3) < 1e-9, "Longitude alanı")
    _assert(abs(float(loc[8]) - 3.0) < 1e-9, "Time Zone alanı (9. alan, 0-based index 8)")
    _assert(abs(float(loc[9]) - 55.0) < 1e-9, "Elevation alanı")


def test_header_cbestyle() -> None:
    lines = epw_header_lines(
        city="T",
        state_region="-",
        country="TR",
        source="Src",
        wmo_or_code="000",
        latitude=1.0,
        longitude=2.0,
        elevation_m=10.0,
        timezone_offset=3.0,
        comments1="",
        comments2="",
    )
    joined = "\n".join(lines)
    _assert("GROUND TEMPERATURES,1,.5,,,,11.2" in joined, "GROUND TEMPERATURES (1 derinlik, 3 boş zemin alanı + aylar)")
    _assert("DATA PERIODS,1,1,Data," in joined, "DATA PERIODS ad alanı (Data)")


def test_end_to_end_sample_epw() -> None:
    sample = ROOT / "sample_data" / "sample_station_data.csv"
    _assert(sample.is_file(), f"Örnek dosya yok: {sample}")

    df, _ = load_tabular_file(str(sample))
    m = guess_mapping(list(df.columns))
    miss, _ = validate_mapping(m)
    _assert(len(miss) == 0, f"Eşleştirme eksik: {miss}")

    proc, meta = build_processed_dataframe(df, m, UnitProfile(pressure="hPa"))
    proc = sort_processed_chronologically(proc)

    # Basınç Pa bandı (örnek ~1013 hPa → ~101300 Pa)
    p0 = float(proc["atmospheric_pressure"].iloc[0])
    _assert(80000 < p0 < 110000, f"Basınç Pa beklenir, değer {p0}")

    out = ROOT / "_verify_out.epw"
    try:
        write_epw_file(
            proc,
            out,
            city="Test",
            state_region="-",
            country="TR",
            source="Verify",
            wmo_or_code="999999",
            latitude=41.2867,
            longitude=36.33,
            elevation_m=4.0,
            timezone_offset=3.0,
            comments1="verify",
            comments2="verify",
        )
        text = out.read_text(encoding="utf-8")
        lines = text.strip().splitlines()
        data_lines = [ln for ln in lines if ln and ln[0].isdigit()]
        _assert(len(data_lines) == len(proc), "Veri satırı sayısı")

        first = data_lines[0].split(",")
        _assert(len(first) == len(EPW_HOURLY_COLUMNS), f"Kolon sayısı {len(first)} != {len(EPW_HOURLY_COLUMNS)}")

        # Missing kodları (örnekte GHI/DNI yoksa 9999)
        line_obj = proc.iloc[0]
        rebuilt = dataframe_row_to_epw_line(line_obj)
        _assert(len(rebuilt.split(",")) == len(EPW_HOURLY_COLUMNS), "Satır birleştirme uzunluğu")

        loc_line = [ln for ln in lines if ln.startswith("LOCATION,")][0]
        parts = loc_line.split(",")
        _assert(abs(float(parts[8]) - 3.0) < 1e-9, "LOCATION timezone")
        _assert(abs(float(parts[9]) - 4.0) < 1e-9, "LOCATION elevation")
    finally:
        if out.exists():
            out.unlink()


def main() -> None:
    test_hour_conversion()
    test_pressure_wind_radiation()
    test_epw_column_order_matches_energyplus()
    test_location_line_order()
    test_header_cbestyle()
    test_end_to_end_sample_epw()
    print("verify_epw: OK (all checks passed).")


if __name__ == "__main__":
    main()
