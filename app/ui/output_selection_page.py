"""Adım 6: Üretilecek çıktı türlerinin seçimi."""

from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget, QLabel


class OutputSelectionPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._boxes: dict[str, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Üretmek istediğiniz çıktı dosyalarını seçin:"))

        items = [
            ("epw", "EnergyPlus / CBE Clima EPW (.epw)"),
            ("pvsyst_csv", "PVsyst Import CSV (.csv)"),
            ("sit", "PVsyst Site File Template (.SIT)"),
            ("mef", "PVsyst Format Template (.MEF)"),
            ("processed_csv", "Processed Weather CSV (.csv)"),
            ("manifest_pvsyst", "Station2EPW Project Package (.pvsyst)"),
            ("quality_report", "Quality Control Report (.txt)"),
        ]
        for key, text in items:
            cb = QCheckBox(text)
            cb.stateChanged.connect(self.save_to_state)
            self._boxes[key] = cb
            layout.addWidget(cb)

        hint = QLabel(
            ".pvsyst dosyası Station2EPW proje manifestidir; PVsyst native MET dosyası değildir."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch(1)

        self.refresh_view()

    def save_to_state(self) -> None:
        opts = self.main_window.state.output_options
        for k, cb in self._boxes.items():
            opts[k] = cb.isChecked()

    def refresh_view(self) -> None:
        opts = self.main_window.state.output_options
        for k, cb in self._boxes.items():
            cb.setChecked(bool(opts.get(k, False)))
