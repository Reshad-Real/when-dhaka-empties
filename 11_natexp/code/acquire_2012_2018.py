"""Download the inputs that extend the record back to 2012, with the settings of the
2019-2025 files:

  ERA5 hourly meteorology, 2012-2018   Open-Meteo archive API, the same point, variables,
                                       local time zone and models=era5 as 02_data/acquire.py
                                       -> 02_data/raw/meteo_dhaka_hourly_2012_2018.csv
  US Embassy Dhaka hourly PM2.5,       AirNow embassy archive, the file names of
  2016-2018                            02_data/pull_ground_monitor.py
                                       -> 02_data/raw/ground/Dhaka_PM2.5_<year>_YTD.csv

Each file is downloaded into a new, empty folder (02_data/raw/download_2012_2018/), checked
(columns, rows, years) and only then copied to its place.  ACLED event records need a
signed-in myACLED account and are fetched separately by the user (fetch_acled.py).
Usage: python -I acquire_2012_2018.py <FYDP_D root>
"""
import os
import shutil
import sys
import time

import pandas as pd
import requests

LAT, LON = 23.8103, 90.4125
HOURLY = ["temperature_2m", "relative_humidity_2m", "dew_point_2m", "precipitation",
          "surface_pressure", "wind_speed_10m", "wind_direction_10m",
          "boundary_layer_height", "cloud_cover"]
EMBASSY = "https://files.airnowtech.org/airnow/EmbassyHistorical/Dhaka"


def get(url, params=None, tries=4):
    for k in range(tries):
        try:
            r = requests.get(url, params=params, timeout=180)
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            print("   attempt %d failed: %s" % (k + 1, type(e).__name__))
            time.sleep(5 * (k + 1))
    raise RuntimeError("download failed: %s" % url)


def main(root):
    raw = os.path.join(root, "02_data", "raw")
    dl = os.path.join(raw, "download_2012_2018")
    os.makedirs(dl, exist_ok=False)                     # a new, empty folder

    # ERA5
    frames = []
    for yr in range(2012, 2019):
        r = get("https://archive-api.open-meteo.com/v1/archive",
                dict(latitude=LAT, longitude=LON, start_date="%d-01-01" % yr, end_date="%d-12-31" % yr,
                     hourly=",".join(HOURLY), timezone="Asia/Dhaka", models="era5"))
        d = pd.DataFrame(r.json()["hourly"])
        assert list(d.columns) == ["time"] + HOURLY, d.columns
        frames.append(d)
        print("ERA5 %d: %d hours" % (yr, len(d)))
        time.sleep(1.5)
    met = pd.concat(frames, ignore_index=True)
    met["time"] = pd.to_datetime(met["time"])
    met = met.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    tmp = os.path.join(dl, "meteo_dhaka_hourly_2012_2018.csv")
    met.to_csv(tmp, index=False)
    assert met.time.min() == pd.Timestamp("2012-01-01") and met.time.max() == pd.Timestamp("2018-12-31 23:00")
    print("ERA5 missing values by variable:", met[HOURLY].isna().sum().to_dict())
    shutil.copy2(tmp, os.path.join(raw, "meteo_dhaka_hourly_2012_2018.csv"))

    # US Embassy
    ref = pd.read_csv(os.path.join(raw, "ground", "Dhaka_PM2.5_2019_YTD.csv"), nrows=5)
    for yr in (2016, 2017, 2018):
        name = "Dhaka_PM2.5_%d_YTD.csv" % yr
        r = get("%s/%d/%s" % (EMBASSY, yr, name))
        tmp = os.path.join(dl, name)
        open(tmp, "wb").write(r.content)
        d = pd.read_csv(tmp)
        assert list(d.columns) == list(ref.columns), (name, list(d.columns))
        print("Embassy %d: %d rows, %s" % (yr, len(d), sorted(set(d["Year"]))))
        dest = os.path.join(raw, "ground", name)
        assert not os.path.exists(dest), dest
        shutil.copy2(tmp, dest)
    print("done; downloads kept in", dl)


if __name__ == "__main__":
    main(sys.argv[1])
