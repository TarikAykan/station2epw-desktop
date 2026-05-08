"""
Kolon adlarından EPW alanlarına otomatik tahmin ve eşleştirme sabitleri.
"""

from __future__ import annotations

import re
from typing import Mapping

from .epw_schema import DATETIME_FIELD_KEY, REQUIRED_MAPPING_FIELDS

# UI ve iş mantığı için dahili anahtarlar
FIELD_DEFINITIONS: list[tuple[str, str]] = [
    ("year", "Year"),
    ("month", "Month"),
    ("day", "Day"),
    ("hour", "Hour"),
    ("minute", "Minute"),
    (DATETIME_FIELD_KEY, "Datetime (tek kolon)"),
    ("dry_bulb", "Dry Bulb Temperature"),
    ("dew_point", "Dew Point Temperature"),
    ("relative_humidity", "Relative Humidity"),
    ("atmospheric_pressure", "Atmospheric Station Pressure"),
    ("wind_direction", "Wind Direction"),
    ("wind_speed", "Wind Speed"),
    ("global_horizontal_radiation", "Global Horizontal Radiation"),
    ("direct_normal_radiation", "Direct Normal Radiation"),
    ("diffuse_horizontal_radiation", "Diffuse Horizontal Radiation"),
    ("horizontal_infrared_radiation", "Horizontal Infrared Radiation Intensity"),
    ("extraterrestrial_horizontal_radiation", "Extraterrestrial Horizontal Radiation"),
    ("extraterrestrial_direct_normal_radiation", "Extraterrestrial Direct Normal Radiation"),
    ("total_sky_cover", "Total Sky Cover"),
    ("opaque_sky_cover", "Opaque Sky Cover"),
    ("visibility", "Visibility"),
    ("ceiling_height", "Ceiling Height"),
    ("present_weather_observation", "Present Weather Observation"),
    ("present_weather_codes", "Present Weather Codes"),
    ("precipitable_water", "Precipitable Water"),
    ("aerosol_optical_depth", "Aerosol Optical Depth"),
    ("snow_depth", "Snow Depth"),
    ("days_since_last_snowfall", "Days Since Last Snowfall"),
    ("albedo", "Albedo"),
    ("liquid_precipitation_depth", "Liquid Precipitation Depth"),
    ("liquid_precipitation_quantity", "Liquid Precipitation Quantity"),
    # PVsyst görünür etiketleri (aynı iç alanlara bağlanır)
    ("pvsyst_date", "PVsyst Date"),
    ("pvsyst_time", "PVsyst Time"),
    ("pvsyst_ghi", "PVsyst Global Horizontal Irradiance (GHI)"),
    ("pvsyst_dhi", "PVsyst Diffuse Horizontal Irradiance (DHI)"),
    ("pvsyst_dni", "PVsyst Direct Normal Irradiance (DNI)"),
    ("pvsyst_ambient_temperature", "PVsyst Ambient Temperature"),
    ("pvsyst_wind_speed", "PVsyst Wind Speed"),
    ("pvsyst_relative_humidity", "PVsyst Relative Humidity"),
    ("pvsyst_precipitation", "PVsyst Precipitation"),
    ("pvsyst_albedo", "PVsyst Albedo"),
]

# küçük harf anahtar kelime -> dahili alan anahtarı
KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["temperature", "temp", "t2m", "sicaklik", "sıcaklık", "drybulb", "dry_bulb", "t_air"], "dry_bulb"),
    (["dewpoint", "dew_point", "d2m", "cig", "çiğ", "dew"], "dew_point"),
    (["humidity", "rh", "nem", "relative_humidity"], "relative_humidity"),
    (["pressure", "pres", "basinc", "basınç", "hpa", "msl"], "atmospheric_pressure"),
    (["wind_speed", "ws", "ruzgar_hizi", "rüzgar_hızı", "windspeed"], "wind_speed"),
    (["wind_direction", "wd", "ruzgar_yonu", "rüzgar_yönü", "winddir"], "wind_direction"),
    (["ghi", "global_radiation", "global_horizontal"], "global_horizontal_radiation"),
    (["dni", "direct_normal"], "direct_normal_radiation"),
    (["dhi", "diffuse", "diffuse_horizontal"], "diffuse_horizontal_radiation"),
    (["cloud", "cloud_cover", "bulut", "sky_cover", "total_cloud"], "total_sky_cover"),
    (
        ["precipitation", "rain", "yagis", "yağış", "precip", "liquid_precip"],
        "liquid_precipitation_depth",
    ),
    (["datetime", "timestamp", "time", "date_time", "tarih"], DATETIME_FIELD_KEY),
    (["year", "yil", "yıl"], "year"),
    (["month", "ay"], "month"),
    (["day", "gun", "gün"], "day"),
    (["hour", "saat", "hr"], "hour"),
    (["minute", "min", "dakika"], "minute"),
    (["date"], "pvsyst_date"),
    (["time"], "pvsyst_time"),
]


def normalize_column_name(name: str) -> str:
    s = str(name).strip().lower()
    s = re.sub(r"\s+", "_", s)
    return s


def guess_mapping(columns: list[str]) -> dict[str, str | None]:
    """
    Verilen kolon listesi için her dahili alana en olası kolonu önerir.
    Çakışmada ilk eşleşen kazanır; bir kolon yalnızca bir hedefe atanır.
    """
    result: dict[str, str | None] = {key: None for key, _ in FIELD_DEFINITIONS}
    used: set[str] = set()
    norm_map = {normalize_column_name(c): c for c in columns}

    scored: list[tuple[int, str, str]] = []
    for col in columns:
        n = normalize_column_name(col)
        parts = set(n.split("_"))
        for keywords, field_key in KEYWORD_RULES:
            for kw in keywords:
                matched = False
                prio = 0
                if kw == n:
                    matched = True
                    prio = 100
                elif kw in parts:
                    matched = True
                    prio = 90 - len(kw)
                elif n.startswith(kw + "_") or n.endswith("_" + kw):
                    matched = True
                    prio = 85 - len(kw)
                elif len(kw) >= 4 and kw in n:
                    matched = True
                    prio = 70 - len(kw)
                if matched:
                    scored.append((prio, col, field_key))
                    break

    scored.sort(key=lambda x: (-x[0], x[1]))

    for _prio, col, field_key in scored:
        if col in used:
            continue
        if result.get(field_key):
            continue
        result[field_key] = col
        used.add(col)

    # PVsyst alanları için EPW eşlerini otomatik yansıt
    mirror_map = {
        "pvsyst_ghi": "global_horizontal_radiation",
        "pvsyst_dhi": "diffuse_horizontal_radiation",
        "pvsyst_dni": "direct_normal_radiation",
        "pvsyst_ambient_temperature": "dry_bulb",
        "pvsyst_wind_speed": "wind_speed",
        "pvsyst_relative_humidity": "relative_humidity",
        "pvsyst_precipitation": "liquid_precipitation_depth",
        "pvsyst_albedo": "albedo",
    }
    for pvs_key, epw_key in mirror_map.items():
        if not result.get(pvs_key):
            result[pvs_key] = result.get(epw_key)

    if not result.get("pvsyst_date"):
        # Ayrı date kolonu yoksa datetime veya zaman bileşenlerinden üretilecek
        result["pvsyst_date"] = result.get(DATETIME_FIELD_KEY)
    if not result.get("pvsyst_time"):
        result["pvsyst_time"] = result.get(DATETIME_FIELD_KEY)

    return result


def validate_mapping(mapping: Mapping[str, str | None]) -> tuple[list[str], list[str]]:
    """
    datetime seçiliyse yıl/ay/gün/saat/dakika zorunlu olmayabilir.
    Aksi halde year, month, day, hour, minute ve meteoroloji alanları zorunlu.
    Dönüş: (eksik_zorunlu_listesi, uyarı_mesajları)
    """
    warnings: list[str] = []
    missing: list[str] = []

    dt_col = mapping.get(DATETIME_FIELD_KEY)
    if dt_col:
        # zaman bileşenleri datetime'dan üretilecek
        for k in ("year", "month", "day", "hour", "minute"):
            if mapping.get(k):
                warnings.append(f"'{k}' hem datetime hem ayrı kolon seçili; datetime önceliklidir.")
        skip = {"year", "month", "day", "hour", "minute"}
        req = [k for k in REQUIRED_MAPPING_FIELDS if k not in skip]
    else:
        req = list(REQUIRED_MAPPING_FIELDS)

    labels = dict(FIELD_DEFINITIONS)
    for key in req:
        if not mapping.get(key):
            missing.append(labels.get(key, key))

    return missing, warnings


def apply_datetime_split(df, datetime_column: str):
    """
    DataFrame'e year, month, day, hour, minute kolonları ekler (datetime_column parse).
    """
    import pandas as pd

    s = pd.to_datetime(df[datetime_column], errors="coerce", utc=False)
    out = df.copy()
    out["_parsed_dt"] = s
    out["year"] = s.dt.year
    out["month"] = s.dt.month
    out["day"] = s.dt.day
    out["hour"] = s.dt.hour
    mn = s.dt.minute.fillna(0)
    out["minute"] = mn.round().clip(0, 59).astype(int)
    return out
