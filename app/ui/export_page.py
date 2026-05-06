"""
Adım 6: EPW ve isteğe bağlı işlenmiş CSV çıktısı.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.epw_writer import export_processed_csv, write_epw_file
from app.core.validator import has_blocking_errors


class ExportPage(QWidget):
    """Çıktı klasörü ve dosya adı; EPW yazımı."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Çıktı klasörü"))
        self.dir_edit = QLineEdit()
        browse_dir = QPushButton("Seç…")
        browse_dir.clicked.connect(self._pick_dir)
        row1.addWidget(self.dir_edit, 1)
        row1.addWidget(browse_dir)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Dosya adı"))
        self.name_edit = QLineEdit()
        row2.addWidget(self.name_edit, 1)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.btn_epw = QPushButton("EPW dosyası oluştur")
        self.btn_epw.clicked.connect(self._write_epw)
        self.btn_csv = QPushButton("İşlenmiş veriyi CSV olarak kaydet")
        self.btn_csv.clicked.connect(self._write_csv)
        row3.addWidget(self.btn_epw)
        row3.addWidget(self.btn_csv)
        layout.addLayout(row3)

        self.out_label = QLabel("")
        self.out_label.setWordWrap(True)

        row4 = QHBoxLayout()
        self.btn_show = QPushButton("Klasörde göster")
        self.btn_show.clicked.connect(self._show_folder)
        row4.addWidget(self.btn_show)
        row4.addStretch(1)
        layout.addLayout(row4)

        layout.addWidget(self.out_label)
        layout.addStretch(1)

    def _pick_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Çıktı klasörü")
        if d:
            self.dir_edit.setText(d)

    def suggest_filename(self) -> str:
        st = self.main_window.state
        s = st.station
        city = str(s.get("city", "city")).replace(" ", "_")
        name = str(s.get("station_name", "station")).replace(" ", "_")
        year = s.get("data_year", "year")
        return f"{city}_{name}_{year}.epw"

    def refresh_view(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setText(self.suggest_filename())
        st = self.main_window.state
        self.out_label.setText(f"Son EPW:\n{st.epw_output_path}" if st.epw_output_path else "")

    def _write_epw(self) -> None:
        mw = self.main_window
        st = mw.state
        if st.raw_df is None:
            QMessageBox.warning(self, "Eksik veri", "Önce bir dosya yükleyin.")
            return
        try:
            mw.rebuild_processed_and_validate()
        except Exception as e:
            QMessageBox.critical(self, "İşlem hatası", str(e))
            return

        if has_blocking_errors(st.validation_results):
            QMessageBox.critical(self, "Üretim engellendi", "Kalite kontrolünde kritik hatalar var.")
            return
        if st.processed_df is None:
            QMessageBox.critical(self, "Veri yok", "İşlenmiş veri oluşturulamadı.")
            return

        folder = self.dir_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Klasör", "Çıktı klasörü seçin.")
            return
        fname = self.name_edit.text().strip()
        if not fname.lower().endswith(".epw"):
            fname += ".epw"
        out = Path(folder) / fname

        s = st.station

        def _parse_float(txt: str, title: str) -> float:
            try:
                return float(str(txt).replace(",", "."))
            except Exception as exc:
                raise ValueError(f"{title} sayısal değil.") from exc

        try:
            lat = _parse_float(s.get("latitude", ""), "Enlem")
            lon = _parse_float(s.get("longitude", ""), "Boylam")
            elev = _parse_float(s.get("elevation", ""), "Rakım")
            tz = _parse_float(s.get("timezone", ""), "Saat dilimi")
        except ValueError as e:
            QMessageBox.warning(self, "İstasyon bilgisi", str(e))
            return

        comments1 = s.get("description") or "Station2EPW Desktop ile üretildi."
        comments2 = f"Kaynak dosya: {Path(st.file_path or '').name}; İstasyon: {s.get('station_name','')}"

        try:
            path = write_epw_file(
                st.processed_df,
                out,
                city=s.get("city", ""),
                state_region="-",
                country=s.get("country", ""),
                source=s.get("source") or "Station2EPW",
                wmo_or_code=str(s.get("wmo", "")),
                latitude=lat,
                longitude=lon,
                elevation_m=elev,
                timezone_offset=tz,
                comments1=str(comments1),
                comments2=str(comments2),
            )
        except Exception as e:
            QMessageBox.critical(self, "Yazma hatası", str(e))
            return

        st.epw_output_path = str(path)
        self.out_label.setText(f"Oluşturulan EPW:\n{path}")
        mw.refresh_report()
        QMessageBox.information(self, "Tamam", f"EPW oluşturuldu:\n{path}")

    def _write_csv(self) -> None:
        mw = self.main_window
        st = mw.state
        if st.raw_df is None:
            QMessageBox.warning(self, "Eksik veri", "Önce bir dosya yüklenmeli.")
            return
        try:
            mw.rebuild_processed_and_validate()
        except Exception as e:
            QMessageBox.critical(self, "İşlem hatası", str(e))
            return
        if st.processed_df is None:
            QMessageBox.warning(self, "Veri yok", "Önce eşleştirme ve doğrulama adımlarını tamamlayın.")
            return

        folder = self.dir_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "Klasör", "Çıktı klasörü seçin.")
            return
        base = Path(self.name_edit.text().strip() or self.suggest_filename()).stem + "_processed.csv"
        path = export_processed_csv(st.processed_df, Path(folder) / base)
        QMessageBox.information(self, "CSV", f"Kaydedildi:\n{path}")

    def _show_folder(self) -> None:
        st = self.main_window.state
        p = st.epw_output_path
        if not p:
            QMessageBox.information(self, "Bilgi", "Önce bir EPW oluşturun.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(p).parent)))
