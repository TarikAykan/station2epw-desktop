"""
Adım 2: İstasyon ve LOCATION üst bilgisi alanları.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class StationInfoPage(QWidget):
    """EPW LOCATION ve yorumlar için girdi formu."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)
        box = QGroupBox("İstasyon bilgileri")
        form = QFormLayout(box)

        self.city = QLineEdit()
        self.country = QLineEdit()
        self.station_name = QLineEdit()
        self.wmo = QLineEdit()
        self.latitude = QLineEdit()
        self.longitude = QLineEdit()
        self.timezone = QLineEdit()
        self.elevation = QLineEdit()
        self.data_year = QSpinBox()
        self.data_year.setRange(1900, 2100)
        self.data_year.setValue(2024)
        self.source = QLineEdit()
        self.description = QTextEdit()
        self.description.setMaximumHeight(90)

        form.addRow("Şehir *", self.city)
        form.addRow("Ülke *", self.country)
        form.addRow("İstasyon adı *", self.station_name)
        form.addRow("WMO / özel kod *", self.wmo)
        form.addRow("Enlem (°) *", self.latitude)
        form.addRow("Boylam (°) *", self.longitude)
        form.addRow("Saat dilimi *", self.timezone)
        form.addRow("Rakım (m) *", self.elevation)
        form.addRow("Veri yılı *", self.data_year)
        form.addRow("Veri kaynağı", self.source)
        form.addRow("Açıklama / notlar", self.description)

        layout.addWidget(box)
        layout.addStretch(1)

        self._load_from_state()

    def _load_from_state(self) -> None:
        s = self.main_window.state.station
        self.city.setText(str(s.get("city", "")))
        self.country.setText(str(s.get("country", "")))
        self.station_name.setText(str(s.get("station_name", "")))
        self.wmo.setText(str(s.get("wmo", "")))
        self.latitude.setText(str(s.get("latitude", "")))
        self.longitude.setText(str(s.get("longitude", "")))
        self.timezone.setText(str(s.get("timezone", "")))
        self.elevation.setText(str(s.get("elevation", "")))
        if "data_year" in s:
            self.data_year.setValue(int(s["data_year"]))
        self.source.setText(str(s.get("source", "")))
        self.description.setPlainText(str(s.get("description", "")))

    def save_to_state(self) -> None:
        self.main_window.state.station = {
            "city": self.city.text().strip(),
            "country": self.country.text().strip(),
            "station_name": self.station_name.text().strip(),
            "wmo": self.wmo.text().strip(),
            "latitude": self.latitude.text().strip(),
            "longitude": self.longitude.text().strip(),
            "timezone": self.timezone.text().strip(),
            "elevation": self.elevation.text().strip(),
            "data_year": self.data_year.value(),
            "source": self.source.text().strip(),
            "description": self.description.toPlainText().strip(),
        }

    def refresh_view(self) -> None:
        self._load_from_state()
