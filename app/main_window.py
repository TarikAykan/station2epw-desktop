"""
Ana pencere: sol menülü sihirbaz ve ortak durum yönetimi.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from app.core.column_mapper import validate_mapping
from app.core.report_generator import (
    build_report_text,
    estimate_missing_cells,
    list_missing_mapped_epw_columns,
)
from app.core.validator import CheckResult, run_all_checks
from app.state import AppState
from app.ui.export_page import ExportPage
from app.ui.mapping_page import MappingPage
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
QListWidget {
    background-color: #0f172a;
    color: #e5e7eb;
    border: none;
    padding: 8px;
    outline: none;
}
QListWidget::item {
    padding: 10px 12px;
    margin: 2px 4px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 12px;
    background-color: #ffffff;
}
QPushButton {
    background-color: #1e3a8a;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:hover {
    background-color: #1d4ed8;
}
QPushButton:pressed {
    background-color: #1e40af;
}
QPushButton:disabled {
    background-color: #9ca3af;
}
QLineEdit, QComboBox, QSpinBox, QTextEdit {
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px;
    background-color: #ffffff;
}
QTableWidget {
    gridline-color: #e5e7eb;
    background-color: #ffffff;
    alternate-background-color: #f9fafb;
}
QLabel#hintLabel {
    color: #4b5563;
    font-size: 12px;
}
"""


class MainWindow(QMainWindow):
    """Tek pencereli sihirbaz ana çatısı."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Station2EPW Desktop")
        self.resize(1120, 740)
        self.state = AppState()

        icon_path = Path(__file__).resolve().parent / "assets" / "app_icon.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)

        self.steps = QListWidget()
        self.steps.addItems(
            [
                "1. Dosya yükle",
                "2. İstasyon bilgileri",
                "3. Kolon eşleştirme",
                "4. Birim dönüşümü",
                "5. Veri kontrolü",
                "6. EPW oluştur",
                "7. Rapor",
            ]
        )
        self.steps.setFixedWidth(220)
        self.steps.currentRowChanged.connect(self._on_step_changed)

        self.stack = QStackedWidget()
        self.upload_page = UploadPage(self)
        self.station_page = StationInfoPage(self)
        self.mapping_page = MappingPage(self)
        self.unit_page = UnitPage(self)
        self.validation_page = ValidationPage(self)
        self.export_page = ExportPage(self)
        self.report_page = ReportPage(self)

        for w in (
            self.upload_page,
            self.station_page,
            self.mapping_page,
            self.unit_page,
            self.validation_page,
            self.export_page,
            self.report_page,
        ):
            self.stack.addWidget(w)

        layout.addWidget(self.steps)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)

        self._prev_step = 0
        self.steps.setCurrentRow(0)

    # --- Gezinme -------------------------------------------------------------
    def _save_step(self, idx: int) -> None:
        if idx == 1:
            self.station_page.save_to_state()
        elif idx == 2:
            self.mapping_page.save_to_state()
        elif idx == 3:
            self.unit_page.save_to_state()

    def _on_step_changed(self, idx: int) -> None:
        if idx < 0:
            return
        self._save_step(self._prev_step)
        self._prev_step = idx
        self.stack.setCurrentIndex(idx)
        w = self.stack.widget(idx)
        if hasattr(w, "refresh_view"):
            w.refresh_view()

    def save_all_pages(self) -> None:
        """İstasyon, eşleştirme ve birim sayfalarını diske değil belleğe yazar."""
        self.station_page.save_to_state()
        self.mapping_page.save_to_state()
        self.unit_page.save_to_state()

    def refresh_mapping_page_combos(self) -> None:
        self.mapping_page.refresh_combos()

    def set_busy(self, busy: bool) -> None:
        self.state.busy = busy
        self.steps.setEnabled(not busy)

    # --- İşlem hattı ---------------------------------------------------------
    def rebuild_processed_and_validate(self) -> None:
        """Eşleştirilmiş veriyi işler ve kalite kontrollerini çalıştırır."""
        from app.core.epw_writer import build_processed_dataframe, sort_processed_chronologically

        self.save_all_pages()
        st = self.state
        results: list[CheckResult] = []

        if st.raw_df is None:
            results.append(
                CheckResult(
                    name="Veri dosyası",
                    status="error",
                    description="Yüklü tablo yok.",
                    critical=True,
                )
            )
            st.processed_df = None
            st.processing_meta = {}
            st.validation_results = results
            self.refresh_report()
            return

        missing_labels, map_warnings = validate_mapping(st.mapping)
        for w in map_warnings:
            results.append(
                CheckResult(
                    name="Eşleştirme",
                    status="warning",
                    description=w,
                    critical=False,
                )
            )
        for m in missing_labels:
            results.append(
                CheckResult(
                    name="Eşleştirme",
                    status="error",
                    description=f"Zorunlu alan eksik: {m}",
                    critical=True,
                )
            )

        if missing_labels:
            st.processed_df = None
            st.processing_meta = {}
            st.validation_results = results
            self.refresh_report()
            return

        try:
            proc, meta = build_processed_dataframe(st.raw_df, st.mapping, st.units)
            proc = sort_processed_chronologically(proc)
        except Exception as e:
            results.append(
                CheckResult(
                    name="Veri işleme",
                    status="error",
                    description=str(e),
                    critical=True,
                )
            )
            st.processed_df = None
            st.processing_meta = {}
            st.validation_results = results
            self.refresh_report()
            return

        st.processed_df = proc
        st.processing_meta = meta

        n_bad_dt = int(meta.get("datetime_parse_failures", 0))
        if n_bad_dt > 0:
            results.append(
                CheckResult(
                    name="Datetime ayrıştırma",
                    status="error",
                    description=f"{n_bad_dt} satır datetime olarak çözülemedi.",
                    critical=True,
                )
            )

        if meta.get("hour_shift_applied"):
            results.append(
                CheckResult(
                    name="Saat biçimi",
                    status="warning",
                    description="Kaynak saatler 0–23 olarak algılandı; EPW için 1–24 formatına kaydırıldı.",
                    critical=False,
                )
            )

        if meta.get("radiation_wh_assumption"):
            results.append(
                CheckResult(
                    name="Radyasyon birimi",
                    status="warning",
                    description="W/m² girdileri Wh/m²'ye saatlik ortalama güç varsayımıyla çevrildi (×1 saat).",
                    critical=False,
                )
            )

        results.extend(run_all_checks(proc))
        st.validation_results = results
        self.refresh_report()

    def refresh_report(self) -> None:
        """Özet raporu state içinde günceller."""
        self.save_all_pages()
        st = self.state
        s = st.station

        def _pf(txt: object, default: float = 0.0) -> float:
            try:
                return float(str(txt).replace(",", "."))
            except Exception:
                return default

        missing_epw = list_missing_mapped_epw_columns(st.mapping)

        conv_notes: list[str] = []
        pm = st.processing_meta
        if pm.get("hour_shift_applied"):
            conv_notes.append("Saat 0–23 → EPW 1–24 dönüşümü uygulandı.")
        if pm.get("radiation_wh_assumption"):
            conv_notes.append("W/m² → Wh/m² için saatlik ortalama güç varsayımı kullanıldı.")

        default_msgs: list[str] = []
        if missing_epw:
            default_msgs.append(
                "Eşlenmemiş isteğe bağlı EPW alanları EnergyPlus önerilen missing kodları ile doldurulacaktır."
            )

        keys_met = [
            "dry_bulb",
            "dew_point",
            "relative_humidity",
            "atmospheric_pressure",
            "wind_direction",
            "wind_speed",
        ]
        missing_cells = None
        if st.processed_df is not None:
            missing_cells = estimate_missing_cells(st.processed_df, keys_met)

        src_name = ""
        if st.file_path:
            src_name = Path(st.file_path).name

        txt = build_report_text(
            station_name=str(s.get("station_name", "")),
            city=str(s.get("city", "")),
            country=str(s.get("country", "")),
            latitude=_pf(s.get("latitude")),
            longitude=_pf(s.get("longitude")),
            elevation_m=_pf(s.get("elevation")),
            data_year=int(s.get("data_year", 2024)),
            source_file=src_name,
            mapping=st.mapping,
            units=st.units,
            validation_results=st.validation_results,
            total_records=len(st.processed_df) if st.processed_df is not None else (len(st.raw_df) if st.raw_df is not None else 0),
            missing_epw_fields=missing_epw,
            default_values_used=default_msgs,
            conversion_notes=conv_notes,
            epw_output_path=st.epw_output_path,
            processing_meta=pm,
            missing_data_count_estimate=missing_cells,
        )
        st.report_text = txt
        self.report_page.refresh_view()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.state.busy:
            QMessageBox.warning(
                self,
                "İşlem sürüyor",
                "Dosya yüklemesi tamamlanmadan kapatmayın.",
            )
            event.ignore()
            return
        event.accept()
