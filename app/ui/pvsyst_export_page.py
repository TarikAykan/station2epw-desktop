"""Adım 8: PVsyst uyumlu çıktılar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QComboBox, QVBoxLayout, QWidget

from app.core.pvsyst_writer import create_pvsyst_export_package
from app.core.pvsyst_validator import has_pvsyst_critical_errors
from app.core.validator import has_blocking_errors


class PvsystExportPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Çıktı klasörü"))
        self.dir_edit = QLineEdit()
        btn = QPushButton("Seç…")
        btn.clicked.connect(self._pick_dir)
        row1.addWidget(self.dir_edit, 1)
        row1.addWidget(btn)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("PVsyst irradiance birimi"))
        self.irr = QComboBox()
        self.irr.addItems(["W/m2", "Wh/m2"])
        self.irr.currentTextChanged.connect(self._save)
        row2.addWidget(self.irr)
        row2.addStretch(1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.btn_make = QPushButton("PVsyst çıktıları üret")
        self.btn_make.clicked.connect(self._run)
        self.btn_show = QPushButton("Klasörde göster")
        self.btn_show.clicked.connect(self._show_folder)
        row3.addWidget(self.btn_make)
        row3.addWidget(self.btn_show)
        layout.addLayout(row3)

        self.info = QLabel("")
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        note = QLabel(
            "For hourly averaged irradiance data, Wh/m² over one hour is numerically equivalent to W/m² average power for that hour."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

    def _save(self) -> None:
        self.main_window.state.pvsyst_irradiance_unit = self.irr.currentText()

    def refresh_view(self) -> None:
        st = self.main_window.state
        if not self.dir_edit.text().strip():
            self.dir_edit.setText(st.output_folder)
        self.irr.setCurrentText(st.pvsyst_irradiance_unit or "W/m2")

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Çıktı klasörü")
        if d:
            self.dir_edit.setText(d)
            self.main_window.state.output_folder = d

    def _base_name(self) -> str:
        s = self.main_window.state.station
        city = str(s.get("city", "city")).strip().replace(" ", "_").lower() or "city"
        code = str(s.get("wmo", s.get("station_name", "station"))).strip().replace(" ", "_").lower() or "station"
        period = str(s.get("data_period") or s.get("data_year") or "year")
        return f"{city}_{code}_{period}"

    def _run(self) -> None:
        mw = self.main_window
        st = mw.state
        mw.save_all_pages()
        try:
            mw.rebuild_processed_and_validate()
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
            return

        if has_blocking_errors(st.validation_results) or has_pvsyst_critical_errors(st.pvsyst_validation_results):
            QMessageBox.critical(self, "Engellendi", "Kritik kalite hataları var; PVsyst çıktıları üretilemedi.")
            return
        if st.processed_df is None:
            QMessageBox.warning(self, "Veri", "İşlenmiş veri yok.")
            return

        folder = self.dir_edit.text().strip() or st.output_folder
        if not folder:
            QMessageBox.warning(self, "Klasör", "Çıktı klasörü seçin.")
            return

        try:
            paths = create_pvsyst_export_package(
                st.processed_df,
                st.station,
                folder,
                base_name=self._base_name(),
                irradiance_unit=self.irr.currentText(),
                source_input_file=Path(st.file_path or "").name,
                include_pvsyst_csv=bool(st.output_options.get("pvsyst_csv", True)),
                include_sit=bool(st.output_options.get("sit", False)),
                include_mef=bool(st.output_options.get("mef", False)),
                include_processed_csv=bool(st.output_options.get("processed_csv", True)),
                include_report_txt=bool(st.output_options.get("quality_report", True)),
                include_manifest=bool(st.output_options.get("manifest_pvsyst", False)),
            )
        except Exception as e:
            QMessageBox.critical(self, "PVsyst Hatası", str(e))
            return

        st.pvsyst_output_paths = paths
        st.output_paths.update(paths)
        if not st.output_options.get("manifest_pvsyst", False) and st.output_paths.get("manifest"):
            try:
                Path(st.output_paths["manifest"]).unlink(missing_ok=True)
            except Exception:
                pass
            st.output_paths["manifest"] = ""

        if st.output_options.get("quality_report"):
            mw.refresh_report()
            rpt = Path(folder) / f"{self._base_name()}_report.txt"
            rpt.write_text(st.report_text, encoding="utf-8")
            st.output_paths["quality_report"] = str(rpt)

        mw.refresh_report()
        self.info.setText("PVsyst çıktıları oluşturuldu.\n" + "\n".join(f"- {k}: {v}" for k, v in paths.items() if v))
        QMessageBox.information(self, "Tamam", "PVsyst paket dosyaları üretildi.")

    def _show_folder(self) -> None:
        folder = self.dir_edit.text().strip() or self.main_window.state.output_folder
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
