"""
Adım 4: Birim seçimleri ve EPW hedef birim özetleri.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.unit_converter import UnitProfile


class UnitPage(QWidget):
    """Kaynak birimler → EPW birimleri."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window

        layout = QVBoxLayout(self)
        box = QGroupBox("Birim dönüşümü")
        form = QFormLayout(box)

        self.temp = QComboBox()
        self.temp.addItems(["°C (zaten)", "K", "°F"])

        self.pressure = QComboBox()
        self.pressure.addItems(["Pa", "hPa", "kPa"])

        self.wind = QComboBox()
        self.wind.addItems(["m/s", "km/h", "knot"])

        self.rad = QComboBox()
        self.rad.addItems(["Wh/m²", "W/m²"])

        form.addRow("Sıcaklık", self.temp)
        form.addRow("Basınç", self.pressure)
        form.addRow("Rüzgar hızı", self.wind)
        form.addRow("Radyasyon (saatlik)", self.rad)

        layout.addWidget(box)

        note = QLabel(
            "Hedef EPW birimleri: sıcaklık °C, basınç Pa, rüzgar m/s, radyasyon Wh/m² (saatlik).\n"
            "W/m² girdiğinizde saatlik ortalama güçten Wh/m² üretilir (×1 saat); raporda belirtilir."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch(1)

        self._load_from_state()

        self.temp.currentIndexChanged.connect(self._save)
        self.pressure.currentIndexChanged.connect(self._save)
        self.wind.currentIndexChanged.connect(self._save)
        self.rad.currentIndexChanged.connect(self._save)

    def _map_temp(self, idx: int) -> str:
        return ["C", "K", "F"][idx]

    def _map_pressure(self, idx: int) -> str:
        return ["Pa", "hPa", "kPa"][idx]

    def _map_wind(self, idx: int) -> str:
        return ["m/s", "km/h", "knot"][idx]

    def _map_rad(self, idx: int) -> str:
        return ["Wh/m2", "W/m2"][idx]

    def _load_from_state(self) -> None:
        u = self.main_window.state.units
        # geri yükleme için kabaca metin eşlemesi
        t_idx = {"C": 0, "K": 1, "F": 2}.get(u.temperature.upper().replace("°", ""), 0)
        self.temp.setCurrentIndex(t_idx)
        p_idx = {"PA": 0, "HPA": 1, "KPA": 2}.get(u.pressure.upper().replace(" ", ""), 0)
        self.pressure.setCurrentIndex(p_idx)
        w_idx = {"M/S": 0, "KM/H": 1, "KNOT": 2}.get(u.wind_speed.upper().replace(" ", ""), 0)
        self.wind.setCurrentIndex(w_idx)
        r_idx = 0 if "wh" in u.radiation.lower() else 1
        self.rad.setCurrentIndex(r_idx)

    def _save(self) -> None:
        self.main_window.state.units = UnitProfile(
            temperature=self._map_temp(self.temp.currentIndex()),
            pressure=self._map_pressure(self.pressure.currentIndex()),
            wind_speed=self._map_wind(self.wind.currentIndex()),
            radiation=self._map_rad(self.rad.currentIndex()),
        )

    def save_to_state(self) -> None:
        self._save()

    def refresh_view(self) -> None:
        self._load_from_state()
