"""
Adım 3: EPW alanları ile kaynak kolonların eşleştirilmesi.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.core.column_mapper import FIELD_DEFINITIONS


MISSING_LABEL = "Yok / Missing"


class MappingPage(QWidget):
    """Her EPW alanı için combobox ile kolon seçimi."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self._combos: dict[str, QComboBox] = {}

        root = QVBoxLayout(self)

        info = QLabel(
            "Zaman için tek bir datetime kolonu seçebilir veya Year–Minute alanlarını ayrı eşleştirebilirsiniz.\n"
            "Datetime seçildiğinde ayrı yıl/ay/gün eşleştirmeleri yok sayılır."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        grid = QGridLayout(holder)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        r = 0
        for key, label in FIELD_DEFINITIONS:
            lab = QLabel(label)
            cb = QComboBox()
            cb.setMinimumWidth(260)
            self._combos[key] = cb
            grid.addWidget(lab, r, 0)
            grid.addWidget(cb, r, 1)
            cb.currentIndexChanged.connect(lambda _i, k=key: self._on_change(k))
            r += 1

        self.refresh_combos()

    def _on_change(self, _key: str) -> None:
        """Durumu güncel tut."""
        self.save_to_state()

    def refresh_combos(self) -> None:
        st = self.main_window.state
        cols = list(st.raw_df.columns) if st.raw_df is not None else []
        items = [MISSING_LABEL] + [str(c) for c in cols]

        current_map = dict(st.mapping)
        for key, cb in self._combos.items():
            cb.blockSignals(True)
            cb.clear()
            for it in items:
                cb.addItem(it)
            sel = current_map.get(key)
            if sel and sel in cols:
                cb.setCurrentText(str(sel))
            else:
                cb.setCurrentIndex(0)
            cb.blockSignals(False)

        self.save_to_state()

    def save_to_state(self) -> None:
        mapping: dict[str, str | None] = {}
        for key, cb in self._combos.items():
            txt = cb.currentText()
            mapping[key] = None if txt == MISSING_LABEL else txt
        self.main_window.state.mapping = mapping

    def refresh_view(self) -> None:
        self.refresh_combos()
