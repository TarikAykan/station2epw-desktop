"""Ana pencere: 9 adımlı sihirbaz, EPW + PVsyst çıktı yönetimi."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QStackedWidget, QWidget

from app.core.column_mapper import validate_mapping
from app.core.pvsyst_validator import run_pvsyst_checks
from app.core.report_generator import build_report_text, estimate_missing_cells, list_missing_mapped_epw_columns, list_missing_mapped_pvsyst_columns
from app.core.validator import CheckResult, run_all_checks
from app.state import AppState
from app.ui.epw_export_page import EpwExportPage
from app.ui.mapping_page import MappingPage
from app.ui.output_selection_page import OutputSelectionPage
from app.ui.pvsyst_export_page import PvsystExportPage
from app.ui.report_page import ReportPage
from app.ui.station_info_page import StationInfoPage
from app.ui.unit_page import UnitPage
from app.ui.upload_page import UploadPage
from app.ui.validation_page import ValidationPage

APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f3f4f6;
    color: #111827;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QListWidget { background-color: #0f172a; color: #e5e7eb; border: none; padding: 8px; outline: none; }
QListWidget::item { padding: 10px 12px; margin: 2px 4px; border-radius: 6px; }
QListWidget::item:selected { background-color: #1d4ed8; color: #ffffff; }
QGroupBox { font-weight: 600; border: 1px solid #d1d5db; border-radius: 8px; margin-top: 10px; padding-top: 12px; background-color: #ffffff; }
QPushButton { background-color: #1e3a8a; color: #ffffff; border: none; border-radius: 6px; padding: 8px 14px; }
QPushButton:hover { background-color: #1d4ed8; }
QPushButton:disabled { background-color: #9ca3af; }
QLineEdit, QComboBox, QSpinBox, QTextEdit { border: 1px solid #d1d5db; border-radius: 6px; padding: 6px; background-color: #ffffff; }
QTableWidget { gridline-color: #e5e7eb; background-color: #ffffff; alternate-background-color: #f9fafb; }
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Station2EPW Desktop — EPW and PVsyst Weather Data Converter")
        self.resize(1220, 780)
        self.state = AppState()

        icon_path = Path(__file__).resolve().parent / "assets" / "app_icon.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        layout = QHBoxLayout(central)

        self.steps = QListWidget()
        self.steps.addItems(
            [
                "1. Dosya Yükle",
                "2. İstasyon Bilgileri",
                "3. Kolon Eşleştirme",
                "4. Birim Dönüşümü",
                "5. Veri Kontrol",
                "6. Çıktı Seçimi",
                "7. EPW Oluştur",
                "8. PVsyst Çıktıları",
                "9. Rapor",
            ]
        )
        self.steps.setFixedWidth(250)
        self.steps.currentRowChanged.connect(self._on_step_changed)

        self.stack = QStackedWidget()
        self.upload_page = UploadPage(self)
        self.station_page = StationInfoPage(self)
        self.mapping_page = MappingPage(self)
        self.unit_page = UnitPage(self)
        self.validation_page = ValidationPage(self)
        self.output_selection_page = OutputSelectionPage(self)
        self.epw_export_page = EpwExportPage(self)
        self.pvsyst_export_page = PvsystExportPage(self)
        self.report_page = ReportPage(self)

        for w in (
            self.upload_page,
            self.station_page,
            self.mapping_page,
            self.unit_page,
            self.validation_page,
            self.output_selection_page,
            self.epw_export_page,
            self.pvsyst_export_page,
            self.report_page,
        ):
            self.stack.addWidget(w)

        layout.addWidget(self.steps)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)

        self._prev_step = 0
        self.steps.setCurrentRow(0)

    def _save_step(self, idx: int) -> None:
        if idx == 1:
            self.station_page.save_to_state()
        elif idx == 2:
            self.mapping_page.save_to_state()
        elif idx == 3:
            self.unit_page.save_to_state()
        elif idx == 5:
            self.output_selection_page.save_to_state()

    def _on_step_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._save_step(self._prev_step)
        self._prev_step = idx
        self.stack.setCurrentIndex(idx)
        page = self.stack.widget(idx)
        if hasattr(page, "refresh_view"):
            page.refresh_view()

    def save_all_pages(self) -> None:
        self.station_page.save_to_state()
        self.mapping_page.save_to_state()
        self.unit_page.save_to_state()
        self.output_selection_page.save_to_state()

    def refresh_mapping_page_combos(self) -> None:
        self.mapping_page.refresh_combos()

    def set_busy(self, busy: bool) -> None:
        self.state.busy = busy
        self.steps.setEnabled(not busy)

    def rebuild_processed_and_validate(self) -> None:
        from app.core.epw_writer import build_processed_dataframe, sort_processed_chronologically

        self.save_all_pages()
        st = self.state
        results: list[CheckResult] = []

        if st.raw_df is None:
            results.append(CheckResult("Veri dosyası", "error", "Yüklü tablo yok.", True))
            st.processed_df = None
            st.validation_results = results
            st.pvsyst_validation_results = []
            self.refresh_report()
            return

        missing_labels, map_warnings = validate_mapping(st.mapping)
        for w in map_warnings:
            results.append(CheckResult("Eşleştirme", "warning", w, False))
        for m in missing_labels:
            results.append(CheckResult("Eşleştirme", "error", f"Zorunlu alan eksik: {m}", True))
        if missing_labels:
            st.processed_df = None
            st.validation_results = results
            st.pvsyst_validation_results = []
            self.refresh_report()
            return

        try:
            proc, meta = build_processed_dataframe(st.raw_df, st.mapping, st.units)
            proc = sort_processed_chronologically(proc)
        except Exception as e:
            st.processed_df = None
            results.append(CheckResult("Veri işleme", "error", str(e), True))
            st.validation_results = results
            st.pvsyst_validation_results = []
            self.refresh_report()
            return

        st.processed_df = proc
        st.processing_meta = meta

        if int(meta.get("datetime_parse_failures", 0)) > 0:
            results.append(CheckResult("Datetime ayrıştırma", "error", f"{meta['datetime_parse_failures']} satır parse edilemedi.", True))
        if meta.get("hour_shift_applied"):
            results.append(CheckResult("Saat biçimi", "warning", "Saat 0–23 -> EPW 1–24 dönüştürüldü.", False))
        if meta.get("radiation_wh_assumption"):
            results.append(CheckResult("Radyasyon birimi", "warning", "W/m² -> Wh/m² saatlik ortalama varsayımı uygulandı.", False))

        results.extend(run_all_checks(proc))
        st.validation_results = results
        st.pvsyst_validation_results = run_pvsyst_checks(proc)

        # DHI/DNI eksikse PVsyst kalite uyarısı
        names = {r.name: r for r in st.pvsyst_validation_results}
        missing_comp = []
        for key in ("DHI var mı", "DNI var mı"):
            rr = names.get(key)
            if rr and rr.status != "ok":
                missing_comp.append(key.split()[0])
        if missing_comp:
            st.pvsyst_validation_results.append(
                type(st.pvsyst_validation_results[0])(
                    name="PVsyst bileşen eksikliği",
                    status="warning",
                    description="PVsyst simulation quality may be limited because diffuse or direct irradiance components are missing.",
                    critical=False,
                )
            )

        self.refresh_report()

    def refresh_report(self) -> None:
        self.save_all_pages()
        st = self.state
        s = st.station

        def _pf(v: object, default: float = 0.0) -> float:
            try:
                return float(str(v).replace(",", "."))
            except Exception:
                return default

        missing_epw = list_missing_mapped_epw_columns(st.mapping)
        missing_pvs = list_missing_mapped_pvsyst_columns(st.mapping)
        notes: list[str] = []
        if st.processing_meta.get("hour_shift_applied"):
            notes.append("Hour 0–23 -> 1–24 dönüşümü uygulandı.")
        if st.processing_meta.get("radiation_wh_assumption"):
            notes.append("For hourly averaged irradiance data, Wh/m² over one hour is numerically equivalent to W/m² average power for that hour.")

        src_name = Path(st.file_path).name if st.file_path else ""
        missing_cells = estimate_missing_cells(st.processed_df, ["dry_bulb", "relative_humidity", "wind_speed"]) if st.processed_df is not None else None

        st.report_text = build_report_text(
            station_name=str(s.get("station_name", "")),
            city=str(s.get("city", "")),
            country=str(s.get("country", "")),
            latitude=_pf(s.get("latitude")),
            longitude=_pf(s.get("longitude")),
            elevation_m=_pf(s.get("elevation")),
            timezone=_pf(s.get("timezone")),
            data_period=str(s.get("data_period") or s.get("data_year") or ""),
            source_file=src_name,
            mapping=st.mapping,
            units=st.units,
            validation_results=st.validation_results,
            pvsyst_validation_results=st.pvsyst_validation_results,
            total_records=len(st.processed_df) if st.processed_df is not None else (len(st.raw_df) if st.raw_df is not None else 0),
            missing_epw_fields=missing_epw,
            missing_pvsyst_fields=missing_pvs,
            conversion_notes=notes,
            processing_meta=st.processing_meta,
            output_paths=st.output_paths,
            missing_data_count_estimate=missing_cells,
        )
        self.report_page.refresh_view()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.state.busy:
            QMessageBox.warning(self, "İşlem sürüyor", "Aktif işlem varken kapatmayın.")
            event.ignore()
            return
        event.accept()
