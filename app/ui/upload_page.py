"""
Adım 1: Dosya yükleme ve önizleme (arka planda okuma ile UI donması azaltılır).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.column_mapper import guess_mapping
from app.core.file_reader import dataframe_preview, load_tabular_file


class FileLoadWorker(QObject):
    finished_ok = Signal(object, object)
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path

    @Slot()
    def run(self) -> None:
        try:
            df, meta = load_tabular_file(self._path)
            self.finished_ok.emit(df, meta)
        except Exception as e:
            self.failed.emit(str(e))


class UploadPage(QWidget):
    """CSV/XLSX seçimi ve ilk satır önizlemesi."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._thread: QThread | None = None
        self._worker: FileLoadWorker | None = None

        root = QVBoxLayout(self)

        box = QGroupBox("Veri dosyası")
        hl = QHBoxLayout(box)
        self.path_label = QLabel("Dosya seçilmedi")
        self.path_label.setWordWrap(True)
        btn = QPushButton("Dosya seç…")
        btn.clicked.connect(self._pick_file)
        hl.addWidget(btn, 0)
        hl.addWidget(self.path_label, 1)
        root.addWidget(box)

        info_row = QHBoxLayout()
        self.rows_label = QLabel("Satır: —")
        self.cols_label = QLabel("Kolon: —")
        self.fmt_label = QLabel("Biçim: —")
        info_row.addWidget(self.rows_label)
        info_row.addWidget(self.cols_label)
        info_row.addWidget(self.fmt_label)
        info_row.addStretch(1)
        root.addLayout(info_row)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        hint = QLabel(
            "UTF-8 / UTF-8-SIG / Latin-1 ve chardet ile kodlama denemesi yapılır. "
            "CSV ayırıcısı otomatik tahmin edilir. Excel’de ilk çalışma sayfası okunur."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hintLabel")
        root.addWidget(hint)

    def _pick_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "İstasyon veri dosyası",
            "",
            "Desteklenen (*.csv *.xlsx *.xlsm);;CSV (*.csv);;Excel (*.xlsx *.xlsm)",
        )
        if not path:
            return
        self._start_load(path)

    def _start_load(self, path: str) -> None:
        st = self.main_window.state
        if st.busy:
            QMessageBox.warning(self, "Meşgul", "Başka bir dosya yükleniyor.")
            return
        st.busy = True
        self.main_window.set_busy(True)
        self.path_label.setText(f"Yükleniyor… ({Path(path).name})")

        self._cleanup_thread()
        self._thread = QThread()
        self._worker = FileLoadWorker(path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished_ok.connect(self._on_loaded)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished_ok.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()
        st.active_worker = self._thread

    @Slot(object, object)
    def _on_loaded(self, df, meta) -> None:
        st = self.main_window.state
        st.busy = False
        self.main_window.set_busy(False)
        st.active_worker = None
        st.raw_df = df
        st.load_meta = meta
        st.file_path = str(meta.get("path", ""))
        st.mapping = guess_mapping(list(df.columns))
        st.processed_df = None
        st.validation_results = []
        st.epw_output_path = None

        self.path_label.setText(Path(st.file_path).name if st.file_path else "")
        self.rows_label.setText(f"Satır: {len(df):,}")
        self.cols_label.setText(f"Kolon: {len(df.columns)}")
        fmt = meta.get("format", "")
        extra = ""
        if fmt == "csv":
            extra = f", kodlama={meta.get('encoding')}, ayraç={repr(meta.get('delimiter'))}"
        elif fmt == "excel":
            extra = f", sayfa={meta.get('sheet_name', 0)}"
        self.fmt_label.setText(f"Biçim: {fmt}{extra}")

        preview = dataframe_preview(df, 20)
        self.table.clear()
        self.table.setColumnCount(len(preview.columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in preview.columns])
        self.table.setRowCount(len(preview))
        for i in range(len(preview)):
            for j, col in enumerate(preview.columns):
                val = preview.iloc[i, j]
                txt = "" if val is None or (isinstance(val, float) and str(val) == "nan") else str(val)
                self.table.setItem(i, j, QTableWidgetItem(txt))
        self.table.resizeColumnsToContents()

        self.main_window.refresh_mapping_page_combos()
        QMessageBox.information(self, "Tamam", "Dosya başarıyla yüklendi.")

    @Slot(str)
    def _on_failed(self, msg: str) -> None:
        st = self.main_window.state
        st.busy = False
        self.main_window.set_busy(False)
        st.active_worker = None
        self.path_label.setText("Dosya seçilmedi")
        QMessageBox.critical(self, "Okuma hatası", msg)

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(3000)
        self._thread = None
        self._worker = None

    def refresh_view(self) -> None:
        """Dosya zaten yüklüyse tabloyu yeniden çizer."""
        st = self.main_window.state
        if st.raw_df is None:
            return
        preview = dataframe_preview(st.raw_df, 20)
        self.table.setColumnCount(len(preview.columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in preview.columns])
        self.table.setRowCount(len(preview))
        for i in range(len(preview)):
            for j, col in enumerate(preview.columns):
                val = preview.iloc[i, j]
                txt = "" if val is None or (isinstance(val, float) and str(val) == "nan") else str(val)
                self.table.setItem(i, j, QTableWidgetItem(txt))
