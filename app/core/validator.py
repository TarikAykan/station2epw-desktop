"""
Veri kalite kontrolleri: eksik saat, tekrar, fiziksel aralıklar vb.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class CheckResult:
    name: str
    status: str  # ok | warning | error
    description: str
    critical: bool


def normalize_hours_for_epw(hour_series: pd.Series) -> tuple[pd.Series, bool]:
    """
    EPW 1–24 formatına getirir.
    Veri 0–23 ise +1 yapılır ve converted=True döner.
    Zaten 1–24 tam sayı ise dokunulmaz.
    """
    h = pd.to_numeric(hour_series, errors="coerce").astype("float64")
    valid = h.dropna()
    if len(valid) == 0:
        return h.fillna(1).astype(int).clip(1, 24), False
    vmin, vmax = float(valid.min()), float(valid.max())
    integral = bool(((valid % 1).abs() < 1e-9).all())

    # Yayın tipik: saat 1..24 (EPW)
    if integral and vmin >= 1.0 and vmax <= 24.0:
        return h.round().fillna(1).astype(int).clip(1, 24), False

    # Yayın tipik: saat 0..23 (pandas datetime dt.hour vb.)
    if integral and vmin >= 0.0 and vmax <= 23.0:
        return (h + 1.0).fillna(1).astype(int).clip(1, 24), True

    # Karışık veya ondalıklı saat: en yakın tam EPW saatine yuvarla (uyarı doğrulama katmanında)
    return h.round().fillna(1).astype(int).clip(1, 24), False


def run_all_checks(df: pd.DataFrame, total_rows_expected: int | None = 8760) -> list[CheckResult]:
    """İşlenmiş saatlik çerçeve üzerinde kontroller."""
    results: list[CheckResult] = []

    n = len(df)
    results.append(
        CheckResult(
            name="Dosya okuma",
            status="ok",
            description=f"İşlenecek kayıt sayısı: {n}",
            critical=False,
        )
    )

    results.append(
        CheckResult(
            name="Kayıt sayısı",
            status="ok" if n > 0 else "error",
            description="Veri satırı yok." if n == 0 else f"Toplam {n} satır.",
            critical=n == 0,
        )
    )

    if total_rows_expected is not None:
        if n == total_rows_expected:
            st = "ok"
            msg = f"Tam yıl saatlik veri ({total_rows_expected} saat)."
        elif n > 0:
            st = "warning"
            msg = (
                f"Beklenen {total_rows_expected} saat yerine {n} satır var; "
                "tam yıl EPW değil veya eksik saatler olabilir."
            )
        else:
            st = "error"
            msg = "Veri yok."
        results.append(
            CheckResult(
                name="8760 saat kontrolü",
                status=st,
                description=msg,
                critical=False,
            )
        )

    req_cols = ["year", "month", "day", "hour", "minute"]
    for c in req_cols:
        if c not in df.columns:
            results.append(
                CheckResult(
                    name=f"Zorunlu kolon: {c}",
                    status="error",
                    description="Eksik kolon.",
                    critical=True,
                )
            )

    if all(c in df.columns for c in req_cols):
        y = pd.to_numeric(df["year"], errors="coerce")
        mo = pd.to_numeric(df["month"], errors="coerce")
        d = pd.to_numeric(df["day"], errors="coerce")
        h = pd.to_numeric(df["hour"], errors="coerce")
        mi = pd.to_numeric(df["minute"], errors="coerce")

        complete = y.notna() & mo.notna() & d.notna() & h.notna() & mi.notna()
        bad_dates = int((~complete).sum())
        hour_oob = int(((h < 1) | (h > 24)).sum())

        if bad_dates or hour_oob:
            parts = []
            if bad_dates:
                parts.append(f"{bad_dates} satırda eksik zaman bileşeni")
            if hour_oob:
                parts.append(f"{hour_oob} satırda EPW saat aralığı dışı (1–24)")
            results.append(
                CheckResult(
                    name="Tarih/saat geçerliliği",
                    status="error",
                    description="; ".join(parts),
                    critical=True,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Tarih/saat geçerliliği",
                    status="ok",
                    description="EPW zaman bileşenleri tutarlı görünüyor.",
                    critical=False,
                )
            )

            keys_df = pd.DataFrame(
                {
                    "y": y.astype(int),
                    "mo": mo.astype(int),
                    "d": d.astype(int),
                    "h": h.astype(int),
                    "mi": mi.astype(int),
                }
            )
            midx = pd.MultiIndex.from_frame(keys_df)
            dup = int(midx.duplicated().sum())
            if dup:
                results.append(
                    CheckResult(
                        name="Tekrarlayan zaman damgası",
                        status="error",
                        description=f"{dup} tekrarlayan zaman kaydı bulundu.",
                        critical=True,
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Tekrarlayan zaman damgası",
                        status="ok",
                        description="Tekrarlayan zaman yok.",
                        critical=False,
                    )
                )

            sorted_keys = keys_df.sort_values(["y", "mo", "d", "h", "mi"]).reset_index(drop=True)
            mono = keys_df.reset_index(drop=True).equals(sorted_keys)
            if not mono:
                results.append(
                    CheckResult(
                        name="Zaman sırası",
                        status="warning",
                        description="Zaman sırası sürekli artmayabilir (satırları kronolojik sıralamanız önerilir).",
                        critical=False,
                    )
                )
            else:
                results.append(
                    CheckResult(
                        name="Zaman sırası",
                        status="ok",
                        description="Zaman sırası artan.",
                        critical=False,
                    )
                )

            if n > 1:

                def _epw_row_ts(row: pd.Series) -> pd.Timestamp:
                    yy, mm, dd = int(row.y), int(row.mo), int(row.d)
                    hh, mmi = int(row.h), int(row.mi)
                    if hh == 24:
                        # Günün son EPW saati — eksik saat ızgarası için gün sonunu ertesi gece yarısına eşleriz
                        return pd.Timestamp(year=yy, month=mm, day=dd) + pd.Timedelta(days=1)
                    return pd.Timestamp(year=yy, month=mm, day=dd) + pd.Timedelta(hours=hh - 1, minutes=mmi)

                try:
                    ts_idx = pd.DatetimeIndex(keys_df.apply(_epw_row_ts, axis=1))
                    full = pd.date_range(ts_idx.min(), ts_idx.max(), freq="h")
                    missing_hours = len(full.difference(ts_idx.unique()))
                    if missing_hours:
                        results.append(
                            CheckResult(
                                name="Eksik saatler",
                                status="warning",
                                description=f"Aralıkta yaklaşık {missing_hours} eksik saat gözleniyor.",
                                critical=False,
                            )
                        )
                    else:
                        results.append(
                            CheckResult(
                                name="Eksik saatler",
                                status="ok",
                                description="Seçilen aralıkta saatlik süreklilik tam görünüyor.",
                                critical=False,
                            )
                        )
                except Exception as ex:
                    results.append(
                        CheckResult(
                            name="Eksik saatler",
                            status="warning",
                            description=f"Kontrol yapılamadı: {ex}",
                            critical=False,
                        )
                    )

    def numeric_series(name: str) -> pd.Series | None:
        if name not in df.columns:
            return None
        return pd.to_numeric(df[name], errors="coerce")

    db = numeric_series("dry_bulb")
    if db is not None:
        invalid = ((db < -90) | (db > 70)).sum()
        miss = db.isna().sum()
        if invalid:
            results.append(
                CheckResult(
                    name="Kuru termometre sıcaklığı",
                    status="error",
                    description=f"{int(invalid)} değer fiziksel dışı (-90…70 °C dışı).",
                    critical=True,
                )
            )
        elif miss:
            results.append(
                CheckResult(
                    name="Kuru termometre sıcaklığı",
                    status="warning",
                    description=f"{int(miss)} eksik değer.",
                    critical=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Kuru termometre sıcaklığı",
                    status="ok",
                    description="Aralık ve eksiklik kontrolü geçti.",
                    critical=False,
                )
            )

    rh = numeric_series("relative_humidity")
    if rh is not None:
        invalid = ((rh < 0) | (rh > 100)).sum()
        miss = rh.isna().sum()
        if invalid:
            results.append(
                CheckResult(
                    name="Bağıl nem",
                    status="error",
                    description=f"{int(invalid)} değer 0–100 aralığı dışında.",
                    critical=True,
                )
            )
        elif miss:
            results.append(
                CheckResult(
                    name="Bağıl nem",
                    status="warning",
                    description=f"{int(miss)} eksik değer.",
                    critical=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Bağıl nem",
                    status="ok",
                    description="0–100 aralığında.",
                    critical=False,
                )
            )

    pr = numeric_series("atmospheric_pressure")
    if pr is not None:
        invalid = ((pr < 80000) | (pr > 110000)).sum()
        miss = pr.isna().sum()
        if invalid:
            results.append(
                CheckResult(
                    name="İstasyon basıncı",
                    status="warning",
                    description=f"{int(invalid)} değer 80–110 kPa (Pa cinsinden) bandının dışında.",
                    critical=False,
                )
            )
        elif miss:
            results.append(
                CheckResult(
                    name="İstasyon basıncı",
                    status="warning",
                    description=f"{int(miss)} eksik değer.",
                    critical=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="İstasyon basıncı",
                    status="ok",
                    description="Mantıklı basınç aralığında.",
                    critical=False,
                )
            )

    wd = numeric_series("wind_direction")
    if wd is not None:
        invalid = ((wd < 0) | (wd > 360)).sum()
        miss = wd.isna().sum()
        if invalid:
            results.append(
                CheckResult(
                    name="Rüzgar yönü",
                    status="error",
                    description=f"{int(invalid)} değer 0–360 aralığı dışında.",
                    critical=True,
                )
            )
        elif miss:
            results.append(
                CheckResult(
                    name="Rüzgar yönü",
                    status="warning",
                    description=f"{int(miss)} eksik değer.",
                    critical=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Rüzgar yönü",
                    status="ok",
                    description="Geçerli.",
                    critical=False,
                )
            )

    ws = numeric_series("wind_speed")
    if ws is not None:
        invalid_neg = (ws < 0).sum()
        miss = ws.isna().sum()
        if invalid_neg:
            results.append(
                CheckResult(
                    name="Rüzgar hızı",
                    status="error",
                    description=f"{int(invalid_neg)} negatif değer.",
                    critical=True,
                )
            )
        elif miss:
            results.append(
                CheckResult(
                    name="Rüzgar hızı",
                    status="warning",
                    description=f"{int(miss)} eksik değer.",
                    critical=False,
                )
            )
        else:
            results.append(
                CheckResult(
                    name="Rüzgar hızı",
                    status="ok",
                    description="Negatif değer yok.",
                    critical=False,
                )
            )

    for rad_name in (
        "global_horizontal_radiation",
        "direct_normal_radiation",
        "diffuse_horizontal_radiation",
    ):
        r = numeric_series(rad_name)
        if r is None:
            continue
        neg = (r < 0).sum()
        if neg:
            results.append(
                CheckResult(
                    name=f"{rad_name} negatif mi?",
                    status="warning",
                    description=f"{int(neg)} negatif radyasyon değeri.",
                    critical=False,
                )
            )

    tsc = numeric_series("total_sky_cover")
    if tsc is not None:
        invalid = ((tsc < 0) | (tsc > 10)).sum()
        if invalid:
            results.append(
                CheckResult(
                    name="Toplam bulutluluk",
                    status="warning",
                    description=f"{int(invalid)} değer 0–10 ölçeği dışında (EPW ondalık bulut).",
                    critical=False,
                )
            )

    # Eksik değer oranı (ana meteoroloji)
    key_met = [
        "dry_bulb",
        "dew_point",
        "relative_humidity",
        "atmospheric_pressure",
        "wind_direction",
        "wind_speed",
    ]
    ratios = []
    for k in key_met:
        if k not in df.columns:
            continue
        ser = pd.to_numeric(df[k], errors="coerce")
        ratio = float(ser.isna().mean()) if len(ser) else 0.0
        ratios.append(ratio)
    if ratios:
        mx = max(ratios)
        results.append(
            CheckResult(
                name="Eksik değer oranı (ana alanlar)",
                status="warning" if mx > 0.05 else "ok",
                description=f"Maksimum eksik oranı: {mx * 100:.2f}%",
                critical=False,
            )
        )

    return results


def has_blocking_errors(results: list[CheckResult]) -> bool:
    return any(r.status == "error" and r.critical for r in results)
