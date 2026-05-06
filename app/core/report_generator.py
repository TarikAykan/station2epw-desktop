"""
İşlem özeti ve kullanıcı raporu metni üretimi.
"""

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
    data_year: int,
    source_file: str,
    mapping: dict[str, str | None],
    units: UnitProfile,
    validation_results: list[CheckResult],
    total_records: int,
    missing_epw_fields: list[str],
    default_values_used: list[str],
    conversion_notes: list[str],
    epw_output_path: str | None,
    processing_meta: dict[str, Any],
    missing_data_count_estimate: int | None = None,
) -> str:
    """Detaylı TXT raporu."""
    lines: list[str] = []
    lines.append("Station2EPW Desktop — İşlem Raporu")
    lines.append("=" * 60)
    lines.append("")
    lines.append("İSTASYON")
    lines.append(f"  İstasyon adı : {station_name}")
    lines.append(f"  Şehir        : {city}")
    lines.append(f"  Ülke         : {country}")
    lines.append(f"  Enlem        : {latitude}")
    lines.append(f"  Boylam       : {longitude}")
    lines.append(f"  Rakım (m)    : {elevation_m}")
    lines.append(f"  Veri yılı    : {data_year}")
    lines.append("")
    lines.append("KAYNAK")
    lines.append(f"  Dosya        : {source_file}")
    lines.append(f"  Kayıt sayısı : {total_records}")
    if missing_data_count_estimate is not None:
        lines.append(f"  Tahmini eksik hücre (ana alanlar): {missing_data_count_estimate}")
    lines.append("")
    lines.append("KOLON EŞLEŞTİRMESİ")
    for key, label in FIELD_DEFINITIONS:
        col = mapping.get(key)
        lines.append(f"  {label}: {col or '(ata yok)'}")
    lines.append("")
    lines.append("BİRİM DÖNÜŞÜMLERİ")
    for s in summarize_conversions(units):
        lines.append(f"  - {s}")
    for note in conversion_notes:
        lines.append(f"  - {note}")
    lines.append("")
    lines.append("İŞLEM META")
    lines.append(f"  Saat 0–23 → 1–24 dönüşümü uygulandı: {processing_meta.get('hour_shift_applied')}")
    lines.append(f"  W/m² → Wh/m² saatlik ortalama varsayımı: {processing_meta.get('radiation_wh_assumption')}")
    if processing_meta.get("datetime_parse_failures"):
        lines.append(f"  Parse edilemeyen datetime satırı: {processing_meta['datetime_parse_failures']}")
    lines.append("")
    lines.append("EKSİK EPW ALANLARI (varsayılan/missing kod ile dolduruldu)")
    if missing_epw_fields:
        for m in missing_epw_fields:
            lines.append(f"  - {m}")
    else:
        lines.append("  (tümü için kullanıcı verisi veya önerilen kodlar kullanıldı)")
    lines.append("")
    lines.append("KULLANILAN VARSAYILAN / MISSING DEĞERLER")
    if default_values_used:
        for d in default_values_used:
            lines.append(f"  - {d}")
    else:
        lines.append("  —")
    lines.append("")
    lines.append("KALİTE KONTROL")
    for r in validation_results:
        lines.append(f"  [{r.status.upper()}] {r.name}: {r.description}")
    lines.append("")
    lines.append("ÇIKTI")
    lines.append(f"  EPW dosyası: {epw_output_path or '(henüz oluşturulmadı)'}")
    lines.append("")
    lines.append("Bu rapor Station2EPW Desktop tarafından otomatik üretilmiştir.")
    return "\n".join(lines)


def list_missing_mapped_epw_columns(mapping: dict[str, str | None]) -> list[str]:
    """Kullanıcı tarafından sağlanmayan isteğe bağlı EPW alanları."""
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
    missing = []
    lbl = dict(FIELD_DEFINITIONS)
    for k in optional_internal:
        if not mapping.get(k):
            missing.append(lbl.get(k, k))
    return missing


def estimate_missing_cells(processed_df, keys: list[str]) -> int:
    """Basit eksik hücre sayısı tahmini."""
    import pandas as pd

    total = 0
    for k in keys:
        if k not in processed_df.columns:
            total += len(processed_df)
            continue
        total += int(pd.to_numeric(processed_df[k], errors="coerce").isna().sum())
    return total
