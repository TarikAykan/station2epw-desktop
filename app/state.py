"""
Uygulama durumu: yüklenen tablo, eşleştirme, birimler ve ara çıktılar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.core.unit_converter import UnitProfile
from app.core.validator import CheckResult


@dataclass
class AppState:
    raw_df: pd.DataFrame | None = None
    load_meta: dict[str, Any] = field(default_factory=dict)
    file_path: str | None = None

    station: dict[str, Any] = field(default_factory=dict)
    mapping: dict[str, str | None] = field(default_factory=dict)

    units: UnitProfile = field(default_factory=UnitProfile)

    processed_df: pd.DataFrame | None = None
    processing_meta: dict[str, Any] = field(default_factory=dict)
    validation_results: list[CheckResult] = field(default_factory=list)

    report_text: str = ""
    epw_output_path: str | None = None

    busy: bool = False
    active_worker: Any | None = None
