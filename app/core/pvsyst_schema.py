"""PVsyst alan adları ve gerekli sütunlar."""

from __future__ import annotations

PVSYST_REQUIRED_INTERNAL_FIELDS: list[str] = [
    "global_horizontal_radiation",
    "diffuse_horizontal_radiation",
    "direct_normal_radiation",
    "dry_bulb",
    "wind_speed",
]

PVSYST_RECOMMENDED_INTERNAL_FIELDS: list[str] = [
    "relative_humidity",
    "liquid_precipitation_depth",
    "albedo",
]

PVSYST_EXPORT_COLUMNS: list[str] = [
    "Date",
    "Time",
    "Global Horizontal Irradiance",
    "Diffuse Horizontal Irradiance",
    "Direct Normal Irradiance",
    "Ambient Temperature",
    "Wind Speed",
    "Relative Humidity",
    "Precipitation",
    "Albedo",
]

PVSYST_IRRADIANCE_UNITS = ("W/m2", "Wh/m2")
