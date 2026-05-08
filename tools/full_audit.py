from __future__ import annotations

from pathlib import Path
import tempfile

import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.column_mapper import apply_datetime_split, guess_mapping
from app.core.epw_schema import EPW_HOURLY_COLUMNS, EPW_MISSING_VALUES, epw_header_lines
from app.core.epw_writer import build_processed_dataframe, dataframe_row_to_epw_line, sort_processed_chronologically, write_epw_file
from app.core.file_reader import load_tabular_file
from app.core.project_manifest import write_project_manifest
from app.core.pvsyst_writer import create_pvsyst_export_package, write_mef_template, write_sit_template
from app.core.unit_converter import UnitProfile, convert_pressure_series, convert_temperature_series, convert_wind_speed_series
from app.core.validator import has_blocking_errors, normalize_hours_for_epw, run_all_checks


def ok(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    root = ROOT
    sample = root / "sample_data" / "sample_station_data.csv"
    ok(sample.exists(), "sample data missing")

    # 1) EPW column order
    ref = [
        "Year","Month","Day","Hour","Minute","Data Source and Uncertainty Flags","Dry Bulb Temperature","Dew Point Temperature",
        "Relative Humidity","Atmospheric Station Pressure","Extraterrestrial Horizontal Radiation","Extraterrestrial Direct Normal Radiation",
        "Horizontal Infrared Radiation Intensity","Global Horizontal Radiation","Direct Normal Radiation","Diffuse Horizontal Radiation",
        "Global Horizontal Illuminance","Direct Normal Illuminance","Diffuse Horizontal Illuminance","Zenith Luminance","Wind Direction",
        "Wind Speed","Total Sky Cover","Opaque Sky Cover","Visibility","Ceiling Height","Present Weather Observation",
        "Present Weather Codes","Precipitable Water","Aerosol Optical Depth","Snow Depth","Days Since Last Snowfall","Albedo",
        "Liquid Precipitation Depth","Liquid Precipitation Quantity",
    ]
    ok(EPW_HOURLY_COLUMNS == ref, "EPW_HOURLY_COLUMNS mismatch")

    # 2) headers
    hdr = epw_header_lines(city="Samsun", state_region="SS", country="TUR", source="Custom", wmo_or_code="170300", latitude=41.3, longitude=36.2, timezone_offset=3.0, elevation_m=4.0, comments1="c1", comments2="c2")
    for k in ["LOCATION", "DESIGN CONDITIONS", "TYPICAL/EXTREME PERIODS", "GROUND TEMPERATURES", "HOLIDAYS/DAYLIGHT SAVINGS", "COMMENTS 1", "COMMENTS 2", "DATA PERIODS"]:
        ok(any(line.startswith(k) for line in hdr), f"missing header {k}")

    # 3) hour conversion
    h, shifted = normalize_hours_for_epw(pd.Series([0, 1, 23]))
    ok(shifted and list(h) == [1, 2, 24], "hour conversion 0-23 -> 1-24 failed")

    # 4) datetime split
    df_dt = pd.DataFrame({"datetime": ["2024-01-01 00:30:00"]})
    sp = apply_datetime_split(df_dt, "datetime")
    ok(int(sp.loc[0, "year"]) == 2024 and int(sp.loc[0, "hour"]) == 0 and int(sp.loc[0, "minute"]) == 30, "datetime split failed")

    # conversions
    ok(abs(float(convert_pressure_series(pd.Series([1013.25]), "hPa").iloc[0]) - 101325.0) < 1e-6, "hPa->Pa failed")
    ok(abs(float(convert_wind_speed_series(pd.Series([36.0]), "km/h").iloc[0]) - 10.0) < 1e-6, "km/h->m/s failed")
    ok(abs(float(convert_wind_speed_series(pd.Series([10.0]), "knot").iloc[0]) - 5.14444) < 1e-5, "knot->m/s failed")
    ok(abs(float(convert_temperature_series(pd.Series([273.15]), "K").iloc[0]) - 0.0) < 1e-6, "K->C failed")
    ok(abs(float(convert_temperature_series(pd.Series([32.0]), "F").iloc[0]) - 0.0) < 1e-6, "F->C failed")

    # sample end-to-end
    raw, _ = load_tabular_file(str(sample))
    mapping = guess_mapping(list(raw.columns))
    proc, meta = build_processed_dataframe(raw, mapping, UnitProfile(temperature="C", pressure="hPa", wind_speed="m/s", radiation="Wh/m2", albedo="0-1"))
    proc = sort_processed_chronologically(proc)

    # 8) radiation to EPW (numeric path)
    ok("global_horizontal_radiation" in proc.columns, "ghi internal missing")

    # 10) missing value fill row
    miss_row = pd.Series({k: None for k in [
        "year", "month", "day", "hour", "minute", "dry_bulb", "dew_point", "relative_humidity", "atmospheric_pressure", "wind_direction", "wind_speed"
    ]})
    line = dataframe_row_to_epw_line(miss_row).split(",")
    ok(line[5] == EPW_MISSING_VALUES["Data Source and Uncertainty Flags"], "missing flag code mismatch")

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        epw_path = write_epw_file(proc, tdp / "out.epw", city="Samsun", state_region="SS", country="TUR", source="Custom", wmo_or_code="170300", latitude=41.3, longitude=36.2, timezone_offset=3.0, elevation_m=4.0, comments1="c1", comments2="c2")
        ok(epw_path.exists(), "epw not written")

        # 11-14 PVsyst outputs + templates + manifest
        pkg = create_pvsyst_export_package(
            proc,
            {"station_name": "Samsun", "city": "Samsun", "country": "Turkey", "latitude": 41.3, "longitude": 36.2, "elevation": 4.0, "timezone": 3.0, "source": "Custom", "wmo": "170300", "data_period": "2024"},
            tdp,
            base_name="samsun_170300_2024",
            irradiance_unit="W/m2",
            source_input_file=sample.name,
            include_pvsyst_csv=True,
            include_sit=True,
            include_mef=True,
            include_processed_csv=True,
            include_report_txt=True,
            include_manifest=True,
        )
        for key in ["pvsyst_csv", "sit", "mef", "manifest"]:
            ok(Path(pkg[key]).exists(), f"{key} missing")

        # 11) PVsyst CSV columns
        pv_lines = Path(pkg["pvsyst_csv"]).read_text(encoding="utf-8").splitlines()
        header_line = next(x for x in pv_lines if x.startswith("Date,Time,"))
        expected_cols = "Date,Time,Global Horizontal Irradiance,Diffuse Horizontal Irradiance,Direct Normal Irradiance,Ambient Temperature,Wind Speed,Relative Humidity,Precipitation,Albedo"
        ok(header_line.strip() == expected_cols, "pvsyst csv columns mismatch")

        sit_txt = Path(pkg["sit"]).read_text(encoding="utf-8")
        ok("Latitude=" in sit_txt and "Longitude=" in sit_txt and "TimeZone=" in sit_txt, "sit template incomplete")

        mef_txt = Path(pkg["mef"]).read_text(encoding="utf-8")
        ok("[Columns]" in mef_txt and "DateFormat=YYYY-MM-DD" in mef_txt, "mef template incomplete")

        manifest_path = Path(pkg["manifest"])
        ok(manifest_path.suffix == ".pvsyst", "manifest extension mismatch")
        import json
        obj = json.loads(manifest_path.read_text(encoding="utf-8"))
        ok(isinstance(obj, dict) and obj.get("project") == "Station2EPW Desktop", "manifest json invalid")

        # 16) output selection flags respected by writer
        pkg2 = create_pvsyst_export_package(
            proc,
            {"station_name": "S", "city": "S", "country": "TR"},
            tdp,
            base_name="flags_test",
            include_pvsyst_csv=False,
            include_sit=False,
            include_mef=False,
            include_processed_csv=False,
            include_report_txt=False,
            include_manifest=False,
        )
        ok(pkg2["pvsyst_csv"] == "" and pkg2["sit"] == "" and pkg2["mef"] == "" and pkg2["manifest"] == "", "selection flags ignored")

    # 17)
    res = run_all_checks(proc)
    _ = has_blocking_errors(res)

    print("full_audit: PASS")


if __name__ == "__main__":
    main()
