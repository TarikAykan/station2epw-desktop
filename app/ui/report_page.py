"""
Adım 7: Özet rapor ve TXT dışa aktarım.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ReportPage(QWidget):
    """İşlem raporu görüntüleme."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Raporu yenile")
        self.btn_refresh.clicked.connect(lambda: self.main_window.refresh_report())
        self.btn_save = QPushButton("TXT olarak kaydet…")
        self.btn_save.clicked.connect(self._save_txt)
        bar.addWidget(self.btn_refresh)
        bar.addWidget(self.btn_save)
        bar.addStretch(1)
        layout.addLayout(bar)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)

    def refresh_view(self) -> None:
        self.text.setPlainText(self.main_window.state.report_text)

    def _save_txt(self) -> None:
        txt = self.text.toPlainText()
        if not txt.strip():
            QMessageBox.information(self, "Boş", "Önce raporu oluşturun.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Raporu kaydet", "station2epw_report.txt", "Metin (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(txt, encoding="utf-8")
            QMessageBox.information(self, "Tamam", f"Kaydedildi:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))
