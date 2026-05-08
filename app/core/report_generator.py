"""İşlem özeti ve kullanıcı raporu metni üretimi."""

from __future__ import annotations

from typing import Any

from .column_mapper import FIELD_DEFINITIONS
from .unit_converter import UnitProfile, summarize_conversions
from .validator import CheckResult


def build_report_text(
    *,
    station_name: str,
    city: str,
    country: str,
    latitude: float,
    longitude: float,
    elevation_m: float,
    timezone: float,
    data_period: str,
    source_file: str,
    mapping: dict[str, str | None],
    units: UnitProfile,
    validation_results: list[CheckResult],
    pvsyst_validation_results: list[Any],
    total_records: int,
    missing_epw_fields: list[str],
    missing_pvsyst_fields: list[str],
    conversion_notes: list[str],
    processing_meta: dict[str, Any],
    output_paths: dict[str, str],
    missing_data_count_estimate: int | None = None,
) -> str:
    lines: list[str] = []
    lines.append("Station2EPW Desktop — EPW and PVsyst Weather Data Converter")
    lines.append("=" * 72)
    lines.append("")
    lines.append("İSTASYON")
    lines.append(f"  İstasyon adı : {station_name}")
    lines.append(f"  Şehir        : {city}")
    lines.append(f"  Ülke         : {country}")
    lines.append(f"  Enlem        : {latitude}")
    lines.append(f"  Boylam       : {longitude}")
    lines.append(f"  Rakım (m)    : {elevation_m}")
    lines.append(f"  Saat dilimi  : {timezone}")
    lines.append(f"  Veri dönemi  : {data_period}")
    lines.append("")

    lines.append("KAYNAK")
    lines.append(f"  Girdi dosyası: {source_file}")
    lines.append(f"  Toplam kayıt : {total_records}")
    if missing_data_count_estimate is not None:
        lines.append(f"  Tahmini eksik hücre: {missing_data_count_estimate}")
    lines.append("")

    lines.append("EŞLEŞTİRME")
    for key, label in FIELD_DEFINITIONS:
        col = mapping.get(key)
        lines.append(f"  {label}: {col or '(Yok / Missing)'}")
    lines.append("")

    lines.append("BİRİM DÖNÜŞÜMLERİ")
    for s in summarize_conversions(units):
        lines.append(f"  - {s}")
    for n in conversion_notes:
        lines.append(f"  - {n}")
    lines.append("")

    lines.append("İŞLEM META")
    lines.append(f"  Saat formatı dönüşümü: {processing_meta.get('hour_shift_applied')}")
    lines.append(f"  W/m² -> Wh/m² varsayımı: {processing_meta.get('radiation_wh_assumption')}")
    if processing_meta.get("datetime_parse_failures"):
        lines.append(f"  Parse edilemeyen datetime: {processing_meta.get('datetime_parse_failures')}")
    lines.append("")

    lines.append("EKSİK ALANLAR")
    lines.append("  EPW eksikleri:")
    if missing_epw_fields:
        for m in missing_epw_fields:
            lines.append(f"    - {m}")
    else:
        lines.append("    - Yok")
    lines.append("  PVsyst eksikleri:")
    if missing_pvsyst_fields:
        for m in missing_pvsyst_fields:
            lines.append(f"    - {m}")
    else:
        lines.append("    - Yok")
    lines.append("")

    lines.append("KALİTE KONTROL (GENEL)")
    for r in validation_results:
        lines.append(f"  [{r.status.upper()}] {r.name}: {r.description}")
    lines.append("")
    lines.append("KALİTE KONTROL (PVsyst)")
    for r in pvsyst_validation_results:
        lines.append(f"  [{str(r.status).upper()}] {r.name}: {r.description}")
    lines.append("")

    lines.append("ÇIKTILAR")
    key_order = [
        ("epw", "EPW"),
        ("pvsyst_csv", "PVsyst CSV"),
        ("sit", "SIT"),
        ("mef", "MEF"),
        ("manifest", ".pvsyst manifest"),
        ("processed_csv", "Processed CSV"),
        ("quality_report", "Rapor"),
    ]
    for key, title in key_order:
        lines.append(f"  {title}: {output_paths.get(key) or '(oluşturulmadı)'}")
    lines.append("")

    lines.append("BİLİNEN SINIRLILIKLAR")
    lines.append("  - .pvsyst dosyası Station2EPW proje manifestidir; native PVsyst MET dosyası değildir.")
    lines.append("  - PVsyst import için CSV + SIT + MEF kullanılmalı, PVsyst içinde import ayarları doğrulanmalıdır.")
    lines.append("  - İlk sürümde native .MET doğrudan üretilmez.")
    lines.append("")
    lines.append("Bu rapor Station2EPW Desktop tarafından otomatik üretilmiştir.")
    lines.append("Uygulama Tarık Aykan tarafından, betanova.tech çatısı altında geliştirilmiştir.")
    return "\n".join(lines)


def list_missing_mapped_epw_columns(mapping: dict[str, str | None]) -> list[str]:
    optional_internal = [
        "extraterrestrial_horizontal_radiation",
        "extraterrestrial_direct_normal_radiation",
        "horizontal_infrared_radiation",
        "global_horizontal_radiation",
        "direct_normal_radiation",
        "diffuse_horizontal_radiation",
        "global_horizontal_illuminance",
        "direct_normal_illuminance",
        "diffuse_horizontal_illuminance",
        "zenith_luminance",
        "total_sky_cover",
        "opaque_sky_cover",
        "visibility",
        "ceiling_height",
        "present_weather_observation",
        "present_weather_codes",
        "precipitable_water",
        "aerosol_optical_depth",
        "snow_depth",
        "days_since_last_snowfall",
        "albedo",
        "liquid_precipitation_depth",
        "liquid_precipitation_quantity",
    ]
    labels = dict(FIELD_DEFINITIONS)
    return [labels.get(k, k) for k in optional_internal if not mapping.get(k)]


def list_missing_mapped_pvsyst_columns(mapping: dict[str, str | None]) -> list[str]:
    req = [
        "pvsyst_ghi",
        "pvsyst_dhi",
        "pvsyst_dni",
        "pvsyst_ambient_temperature",
        "pvsyst_wind_speed",
        "pvsyst_relative_humidity",
        "pvsyst_precipitation",
        "pvsyst_albedo",
    ]
    labels = dict(FIELD_DEFINITIONS)
    return [labels.get(k, k) for k in req if not mapping.get(k)]


def estimate_missing_cells(processed_df, keys: list[str]) -> int:
    import pandas as pd

    total = 0
    for k in keys:
        if k not in processed_df.columns:
            total += len(processed_df)
            continue
        total += int(pd.to_numeric(processed_df[k], errors="coerce").isna().sum())
    return total
