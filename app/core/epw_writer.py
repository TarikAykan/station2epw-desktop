"""
İşlenmiş tablodan EPW saatlik satırları ve dosya yazımı.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .column_mapper import DATETIME_FIELD_KEY, apply_datetime_split
from .epw_schema import EPW_HOURLY_COLUMNS, EPW_MISSING_VALUES, epw_header_lines
from .unit_converter import UnitProfile, convert_pressure_series, convert_radiation_series, convert_temperature_series, convert_wind_speed_series
from .validator import normalize_hours_for_epw

# Dahili kolon adı -> EPW tam adı
INTERNAL_TO_EPW: dict[str, str] = {
    "year": "Year",
    "month": "Month",
    "day": "Day",
    "hour": "Hour",
    "minute": "Minute",
    "dry_bulb": "Dry Bulb Temperature",
    "dew_point": "Dew Point Temperature",
    "relative_humidity": "Relative Humidity",
    "atmospheric_pressure": "Atmospheric Station Pressure",
    "extraterrestrial_horizontal_radiation": "Extraterrestrial Horizontal Radiation",
    "extraterrestrial_direct_normal_radiation": "Extraterrestrial Direct Normal Radiation",
    "horizontal_infrared_radiation": "Horizontal Infrared Radiation Intensity",
    "global_horizontal_radiation": "Global Horizontal Radiation",
    "direct_normal_radiation": "Direct Normal Radiation",
    "diffuse_horizontal_radiation": "Diffuse Horizontal Radiation",
    "global_horizontal_illuminance": "Global Horizontal Illuminance",
    "direct_normal_illuminance": "Direct Normal Illuminance",
    "diffuse_horizontal_illuminance": "Diffuse Horizontal Illuminance",
    "zenith_luminance": "Zenith Luminance",
    "wind_direction": "Wind Direction",
    "wind_speed": "Wind Speed",
    "total_sky_cover": "Total Sky Cover",
    "opaque_sky_cover": "Opaque Sky Cover",
    "visibility": "Visibility",
    "ceiling_height": "Ceiling Height",
    "present_weather_observation": "Present Weather Observation",
    "present_weather_codes": "Present Weather Codes",
    "precipitable_water": "Precipitable Water",
    "aerosol_optical_depth": "Aerosol Optical Depth",
    "snow_depth": "Snow Depth",
    "days_since_last_snowfall": "Days Since Last Snowfall",
    "albedo": "Albedo",
    "liquid_precipitation_depth": "Liquid Precipitation Depth",
    "liquid_precipitation_quantity": "Liquid Precipitation Quantity",
}


def _series_from_mapping(df: pd.DataFrame, col_name: str | None) -> pd.Series:
    if not col_name or col_name not in df.columns:
        return pd.Series(np.nan, index=df.index)
    return df[col_name]


def build_processed_dataframe(
    raw_df: pd.DataFrame,
    mapping: dict[str, str | None],
    units: UnitProfile,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Ham tabloyu EPW yazımına uygun dahili kolonlara dönüştürür.
    Dönüş meta: hour_shift_applied, radiation_wh_assumption, datetime_parse_failures
    """
    meta: dict[str, Any] = {
        "hour_shift_applied": False,
        "radiation_wh_assumption": False,
        "datetime_parse_failures": 0,
    }

    df = raw_df.copy()
    if mapping.get(DATETIME_FIELD_KEY):
        col = mapping[DATETIME_FIELD_KEY]
        assert col is not None
        df = apply_datetime_split(df, col)
        meta["datetime_parse_failures"] = int(df["_parsed_dt"].isna().sum())

    rows = {}

    time_keys = ["year", "month", "day", "hour", "minute"]
    if mapping.get(DATETIME_FIELD_KEY):
        for tk in time_keys:
            rows[tk] = pd.to_numeric(df[tk], errors="coerce")
    else:
        for tk in time_keys:
            mcol = mapping.get(tk)
            rows[tk] = pd.to_numeric(_series_from_mapping(df, mcol), errors="coerce")

    rows["minute"] = rows["minute"].fillna(0)

    # Meteoroloji ve diğer alanlar
    met_keys = [k for k in INTERNAL_TO_EPW if k not in time_keys]
    for mk in met_keys:
        mcol = mapping.get(mk)
        rows[mk] = pd.to_numeric(_series_from_mapping(df, mcol), errors="coerce")

    out = pd.DataFrame(rows, index=df.index)

    # Birim dönüşümleri
    out["dry_bulb"] = convert_temperature_series(out["dry_bulb"], units.temperature)
    out["dew_point"] = convert_temperature_series(out["dew_point"], units.temperature)
    out["atmospheric_pressure"] = convert_pressure_series(out["atmospheric_pressure"], units.pressure)
    out["wind_speed"] = convert_wind_speed_series(out["wind_speed"], units.wind_speed)

    rad_fields = [
        "global_horizontal_radiation",
        "direct_normal_radiation",
        "diffuse_horizontal_radiation",
        "extraterrestrial_horizontal_radiation",
        "extraterrestrial_direct_normal_radiation",
        "horizontal_infrared_radiation",
    ]
    for rf in rad_fields:
        s_conv, assumed = convert_radiation_series(out[rf], units.radiation)
        out[rf] = s_conv
        meta["radiation_wh_assumption"] = meta["radiation_wh_assumption"] or assumed

    # EPW saat formatı
    h_norm, shifted = normalize_hours_for_epw(out["hour"])
    out["hour"] = h_norm
    meta["hour_shift_applied"] = shifted

    return out, meta


def _fmt_int_cell(value: Any, default: str = "99") -> str:
    """Year/month/day/hour/minute için tamsayı çıktısı."""
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return str(int(round(float(value))))
    except (TypeError, ValueError):
        return default


def _fmt_value(epw_field: str, value: Any) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return str(EPW_MISSING_VALUES[epw_field])
    miss = EPW_MISSING_VALUES[epw_field]
    if epw_field == "Data Source and Uncertainty Flags":
        return str(miss)
    if isinstance(miss, int) and miss >= 999 and epw_field not in ("Aerosol Optical Depth",):
        try:
            v = float(value)
            if math.isnan(v):
                return str(miss)
        except (TypeError, ValueError):
            return str(miss)
    if epw_field == "Aerosol Optical Depth":
        try:
            v = float(value)
            if math.isnan(v):
                return str(miss)
            return f"{v:.3f}"
        except (TypeError, ValueError):
            return str(miss)

    # Yaygın biçimlendirme
    if epw_field in ("Dry Bulb Temperature", "Dew Point Temperature"):
        return f"{float(value):.2f}"
    if epw_field == "Relative Humidity":
        return str(int(round(float(value))))
    if epw_field == "Atmospheric Station Pressure":
        return str(int(round(float(value))))
    if "Radiation" in epw_field or epw_field == "Zenith Luminance":
        return str(int(round(float(value))))
    if "Illuminance" in epw_field:
        return str(int(round(float(value))))
    if epw_field in ("Wind Direction", "Wind Speed"):
        return f"{float(value):.2f}"
    if epw_field in ("Total Sky Cover", "Opaque Sky Cover"):
        return f"{float(value):.1f}"
    if epw_field in ("Visibility", "Ceiling Height"):
        return str(int(round(float(value))))
    if epw_field in ("Precipitable Water",):
        return f"{float(value):.3f}"
    if epw_field in ("Snow Depth", "Albedo", "Liquid Precipitation Depth"):
        return f"{float(value):.1f}"
    if epw_field in ("Days Since Last Snowfall", "Liquid Precipitation Quantity"):
        return str(int(round(float(value))))
    if epw_field in ("Present Weather Observation",):
        return str(int(round(float(value))))
    if epw_field in ("Present Weather Codes",):
        return str(int(round(float(value))))

    return str(value)


def dataframe_row_to_epw_line(row: pd.Series) -> str:
    """Tek satırı EPW CSV formatına çevirir."""
    parts: list[str] = []
    parts.append(_fmt_int_cell(row.get("year"), "9999"))
    parts.append(_fmt_int_cell(row.get("month")))
    parts.append(_fmt_int_cell(row.get("day")))
    parts.append(_fmt_int_cell(row.get("hour")))
    parts.append(_fmt_int_cell(row.get("minute"), "0"))
    parts.append(str(EPW_MISSING_VALUES["Data Source and Uncertainty Flags"]))

    for col in EPW_HOURLY_COLUMNS[6:]:
        internal = None
        for k, v in INTERNAL_TO_EPW.items():
            if v == col:
                internal = k
                break
        if internal is None:
            parts.append(str(EPW_MISSING_VALUES[col]))
            continue
        val = row.get(internal)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            parts.append(str(EPW_MISSING_VALUES[col]))
        else:
            parts.append(_fmt_value(col, val))
    return ",".join(parts)


def write_epw_file(
    processed: pd.DataFrame,
    output_path: str | Path,
    *,
    city: str,
    state_region: str,
    country: str,
    source: str,
    wmo_or_code: str,
    latitude: float,
    longitude: float,
    elevation_m: float,
    timezone_offset: float,
    comments1: str,
    comments2: str,
) -> Path:
    """Tam EPW dosyasını yazar."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    header = epw_header_lines(
        city=city,
        state_region=state_region,
        country=country,
        source=source,
        wmo_or_code=wmo_or_code,
        latitude=latitude,
        longitude=longitude,
        elevation_m=elevation_m,
        timezone_offset=timezone_offset,
        comments1=comments1,
        comments2=comments2,
    )

    lines = header[:]
    for _, row in processed.iterrows():
        lines.append(dataframe_row_to_epw_line(row))

    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def sort_processed_chronologically(df: pd.DataFrame) -> pd.DataFrame:
    """EPW yazımından önce zaman sırasına göre sıralar."""
    cols = ["year", "month", "day", "hour", "minute"]
    if not all(c in df.columns for c in cols):
        return df
    return df.sort_values(cols).reset_index(drop=True)


def export_processed_csv(processed: pd.DataFrame, output_path: str | Path) -> Path:
    """İşlenmiş dahili kolonları CSV olarak kaydeder."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(path, index=False, encoding="utf-8-sig")
    return path
