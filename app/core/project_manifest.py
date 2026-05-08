"""Station2EPW proje manifest (.pvsyst) üretimi."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_project_manifest(
    *,
    output_path: str | Path,
    station_info: dict[str, Any],
    input_file: str,
    outputs: dict[str, str],
    source_name: str = "Custom Station Data",
    version: str = "1.0.0",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "project": "Station2EPW Desktop",
        "version": version,
        "station": {
            "name": station_info.get("station_name", ""),
            "city": station_info.get("city", ""),
            "country": station_info.get("country", ""),
            "station_code": station_info.get("wmo", ""),
            "latitude": _pf(station_info.get("latitude")),
            "longitude": _pf(station_info.get("longitude")),
            "timezone": _pf(station_info.get("timezone")),
            "altitude": _pf(station_info.get("elevation")),
            "data_period": station_info.get("data_period") or str(station_info.get("data_year", "")),
        },
        "source": {
            "input_file": input_file,
            "source_name": source_name,
        },
        "outputs": outputs,
        "notes": [
            ".pvsyst is a Station2EPW project manifest file, not a native PVsyst meteo file.",
            "PVsyst import settings should be verified inside PVsyst.",
        ],
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _pf(v: Any) -> float:
    try:
        return float(str(v).replace(",", "."))
    except Exception:
        return 0.0
