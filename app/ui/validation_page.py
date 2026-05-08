"""
Adım 5: Kalite kontrolleri ve durum tablosu.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ValidationPage(QWidget):
    """Kontrol sonuçları tablosu."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.btn_run = QPushButton("Kontrolleri çalıştır")
        self.btn_run.clicked.connect(self.run_checks)
        top.addWidget(self.btn_run)
        top.addStretch(1)
        layout.addLayout(top)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Kontrol adı", "Durum", "Açıklama", "Kritik"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        hint = QLabel(
            "Kritik hatalar EPW üretimini engeller. Uyarılar ise kullanıcı onayıyla sürdürülebilir "
            "(bu sürümde EPW oluşturma yine de kritik hata yoksa mümkündür)."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

    def run_checks(self) -> None:
        try:
            self.main_window.rebuild_processed_and_validate()
        except Exception as e:
            QMessageBox.critical(self, "İşlem hatası", str(e))
            return
        self.refresh_table()

    def refresh_table(self) -> None:
        epw_results = self.main_window.state.validation_results
        pvs_results = self.main_window.state.pvsyst_validation_results
        results = list(epw_results) + list(pvs_results)
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(r.name))
            st_item = QTableWidgetItem(r.status.upper())
            if r.status == "ok":
                st_item.setBackground(QColor("#d4edda"))
            elif r.status == "warning":
                st_item.setBackground(QColor("#fff3cd"))
            else:
                st_item.setBackground(QColor("#f8d7da"))
            self.table.setItem(i, 1, st_item)
            self.table.setItem(i, 2, QTableWidgetItem(r.description))
            crit = "Evet" if r.critical else "Hayır"
            self.table.setItem(i, 3, QTableWidgetItem(crit))
        self.table.resizeColumnsToContents()

        from app.core.pvsyst_validator import has_pvsyst_critical_errors
        from app.core.validator import has_blocking_errors

        blocked = has_blocking_errors(epw_results) or has_pvsyst_critical_errors(pvs_results)
        self.summary.setText(
            "Sonuç: Çıktı üretimi engelli (kritik hata var)." if blocked else "Sonuç: Kritik engel yok; uyarıları raporda inceleyin."
        )

    def refresh_view(self) -> None:
        self.refresh_table()
