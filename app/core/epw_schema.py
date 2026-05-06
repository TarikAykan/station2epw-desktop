"""
EnergyPlus EPW format şeması: saatlik veri kolon sırası ve eksik değer kodları.

EnergyPlus dokümantasyonundaki resmi EPW saatlik veri kolonları sabit liste olarak tutulur.
"""

from typing import Any

# EPW saatlik veri satırındaki alanların sırası (EnergyPlus ile uyumlu)
EPW_HOURLY_COLUMNS: list[str] = [
    "Year",
    "Month",
    "Day",
    "Hour",
    "Minute",
    "Data Source and Uncertainty Flags",
    "Dry Bulb Temperature",
    "Dew Point Temperature",
    "Relative Humidity",
    "Atmospheric Station Pressure",
    "Extraterrestrial Horizontal Radiation",
    "Extraterrestrial Direct Normal Radiation",
    "Horizontal Infrared Radiation Intensity",
    "Global Horizontal Radiation",
    "Direct Normal Radiation",
    "Diffuse Horizontal Radiation",
    "Global Horizontal Illuminance",
    "Direct Normal Illuminance",
    "Diffuse Horizontal Illuminance",
    "Zenith Luminance",
    "Wind Direction",
    "Wind Speed",
    "Total Sky Cover",
    "Opaque Sky Cover",
    "Visibility",
    "Ceiling Height",
    "Present Weather Observation",
    "Present Weather Codes",
    "Precipitable Water",
    "Aerosol Optical Depth",
    "Snow Depth",
    "Days Since Last Snowfall",
    "Albedo",
    "Liquid Precipitation Depth",
    "Liquid Precipitation Quantity",
]

# EPW içinde kullanılan eksik / varsayılan kodlar (EnergyPlus önerileriyle uyumlu)
EPW_MISSING_VALUES: dict[str, Any] = {
    "Data Source and Uncertainty Flags": "?9?9?9?9?9?9?9?9?9",
    "Dry Bulb Temperature": 99.9,
    "Dew Point Temperature": 99.9,
    "Relative Humidity": 999,
    "Atmospheric Station Pressure": 999999,
    "Extraterrestrial Horizontal Radiation": 9999,
    "Extraterrestrial Direct Normal Radiation": 9999,
    "Horizontal Infrared Radiation Intensity": 9999,
    "Global Horizontal Radiation": 9999,
    "Direct Normal Radiation": 9999,
    "Diffuse Horizontal Radiation": 9999,
    "Global Horizontal Illuminance": 999999,
    "Direct Normal Illuminance": 999999,
    "Diffuse Horizontal Illuminance": 999999,
    "Zenith Luminance": 9999,
    "Wind Direction": 999,
    "Wind Speed": 999,
    "Total Sky Cover": 99,
    "Opaque Sky Cover": 99,
    "Visibility": 9999,
    "Ceiling Height": 99999,
    "Present Weather Observation": 9,
    "Present Weather Codes": 999999999,
    "Precipitable Water": 999,
    "Aerosol Optical Depth": 0.999,
    "Snow Depth": 999,
    "Days Since Last Snowfall": 99,
    "Albedo": 999,
    "Liquid Precipitation Depth": 999,
    "Liquid Precipitation Quantity": 99,
}

# Zorunlu eşleştirme alanları (tarih/saat ve ana meteoroloji)
REQUIRED_MAPPING_FIELDS: list[str] = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "dry_bulb",
    "dew_point",
    "relative_humidity",
    "atmospheric_pressure",
    "wind_direction",
    "wind_speed",
]

# Tek datetime kolonu bu anahtar ile seçilir; parçalanır
DATETIME_FIELD_KEY = "datetime"


def epw_header_lines(
    city: str,
    state_region: str,
    country: str,
    source: str,
    wmo_or_code: str,
    latitude: float,
    longitude: float,
    elevation_m: float,
    timezone_offset: float,
    comments1: str,
    comments2: str,
) -> list[str]:
    """
    EPW üst bilgi satırları (LOCATION … DATA PERIODS).
    İlk sürümde tasarım koşulları ve tipik dönemler sıfır kayıt ile minimal tutulur.
    """
    # EnergyPlus sırası (Weather File Format): City … WMO, Latitude, Longitude, Time Zone, Elevation {m}
    loc = ",".join(
        [
            "LOCATION",
            _csv_escape(city),
            _csv_escape(state_region),
            _csv_escape(country),
            _csv_escape(source),
            _csv_escape(str(wmo_or_code)),
            f"{latitude}",
            f"{longitude}",
            f"{timezone_offset}",
            f"{elevation_m}",
        ]
    )
    lines = [
        loc,
        "DESIGN CONDITIONS,0",
        "TYPICAL/EXTREME PERIODS,0",
        # Tek derinlik (.5 m), zemin özellikleri boş, 12 aylık ortalama °C (Chicago EPW yapısıyla uyumlu)
        "GROUND TEMPERATURES,1,.5,,,,11.2,12.4,13.6,15.0,17.5,20.0,23.0,24.5,23.5,20.5,16.5,13.0",
        "HOLIDAYS/DAYLIGHT SAVINGS,No,0,0,0",
        f"COMMENTS 1,{_csv_escape(comments1)}",
        f"COMMENTS 2,{_csv_escape(comments2)}",
        # Ad, haftanın günü, başlangıç/bitiş (TMY3 örnekleri: DATA PERIODS,1,1,Data,Sunday, 1/ 1,12/31)
        "DATA PERIODS,1,1,Data,Sunday,1/1,12/31",
    ]
    return lines


def _csv_escape(text: str) -> str:
    """Virgül içeren metinleri tırnak içine alır."""
    if text is None:
        return ""
    s = str(text).replace('"', '""')
    if "," in s or "\n" in s:
        return f'"{s}"'
    return s
