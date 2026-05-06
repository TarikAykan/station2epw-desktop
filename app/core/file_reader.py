"""
CSV ve Excel dosyalarını okuma: kodlama denemeleri, ayırıcı tahmini, ilk sayfa.
"""

from __future__ import annotations

import csv
from typing import Any

import chardet
import pandas as pd


ENCODING_CANDIDATES: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin-1")


def detect_encoding_sample(path: str, sample_bytes: int = 65536) -> str | None:
    """chardet ile tahmin; güven düşükse None."""
    try:
        with open(path, "rb") as f:
            raw = f.read(sample_bytes)
        if not raw:
            return None
        guess = chardet.detect(raw)
        enc = guess.get("encoding")
        conf = guess.get("confidence") or 0
        if enc and conf >= 0.6:
            return enc
    except OSError:
        return None
    return None


def sniff_delimiter(text_sample: str) -> str:
    """İlk satırlardan CSV ayırıcı tahmini."""
    try:
        dialect = csv.Sniffer().sniff(text_sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def read_csv_flexible(path: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    CSV okur: önce utf-8-sig / utf-8 / latin-1, sonra chardet.
    Dönüş: (DataFrame, meta: encoding, delimiter)
    """
    meta: dict[str, Any] = {"encoding": None, "delimiter": None, "errors": []}

    last_err: Exception | None = None
    for enc in ENCODING_CANDIDATES:
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                sample = f.read(65536)
                f.seek(0)
                delim = sniff_delimiter(sample)
                meta["encoding"] = enc
                meta["delimiter"] = delim
                df = pd.read_csv(f, sep=delim, encoding=enc, low_memory=False)
                return df, meta
        except Exception as e:
            last_err = e
            meta["errors"].append(str(e))

    guessed = detect_encoding_sample(path)
    if guessed:
        try:
            with open(path, "r", encoding=guessed, errors="replace") as f:
                sample = f.read(65536)
                f.seek(0)
                delim = sniff_delimiter(sample)
                meta["encoding"] = guessed
                meta["delimiter"] = delim
                df = pd.read_csv(f, sep=delim, encoding=guessed, low_memory=False)
                return df, meta
        except Exception as e:
            last_err = e
            meta["errors"].append(str(e))

    raise IOError(f"CSV okunamadı: {path}. Son hata: {last_err}")


def read_excel_first_sheet(path: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """İlk çalışma sayfasını okur."""
    meta: dict[str, Any] = {"sheet": 0}
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        name = xl.sheet_names[0]
        meta["sheet_name"] = name
        df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
        return df, meta
    except Exception as e:
        raise IOError(f"Excel dosyası okunamadı: {path}: {e}") from e


def load_tabular_file(path: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Uzantıya göre CSV veya XLSX yükler."""
    lower = path.lower()
    info: dict[str, Any] = {"path": path, "format": None}
    if lower.endswith((".xlsx", ".xlsm")):
        df, sub = read_excel_first_sheet(path)
        info["format"] = "excel"
        info.update(sub)
        return df, info
    if lower.endswith(".csv"):
        df, sub = read_csv_flexible(path)
        info["format"] = "csv"
        info.update(sub)
        return df, info
    raise ValueError("Desteklenen formatlar: .csv, .xlsx, .xlsm")


def dataframe_preview(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Önizleme için ilk n satır."""
    return df.head(n).copy()
