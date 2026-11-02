"""How far would the observed whole-city activity cuts move Dhaka's air if they lasted all year?

An illustrative ceiling, not a forecast.  The proportional PM2.5 changes estimated in
shutdowns.py (Eid, the 2020 general holiday, the 2023-24 blockade days) are applied to every
day of the US Embassy record, 2016-2024 (daily means from >= 18 valid hours).  Applying a
constant proportion to every day assumes the response observed in the event seasons holds in
all seasons; with a larger regional share in the dry season (NAQMP 2024-2030, section 5) this
is generous to the scenario.

Reported for the observed record and each scenario: the annual mean, the December-February
mean, the share of days above the national 24-hour PM2.5 standard (65 ug m-3, APCR 2022
Schedule 1) and in each AQI category (US EPA 2024 PM2.5 breakpoints, events_hourly.aqi_pm25),
the gap to the national annual standard (35 ug m-3) that would be closed, and the reduction
set against the NAQMP's 2030 target for the Greater Dhaka Area (30 ug m-3 lower,
population-weighted).

Writes out/limits.csv.
Usage: python -I limits.py <FYDP_D root>
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cams_shocks import embassy_hourly  # noqa: E402
from events_hourly import aqi_pm25  # noqa: E402

OUT = os.path.join(HERE, "..", "out")
STD_24H, STD_ANNUAL, NAQMP_GDA = 65.0, 35.0, 30.0
CATS = [("good", 0, 50), ("moderate", 50, 100), ("usg", 100, 150), ("unhealthy", 150, 200),
        ("very_unhealthy", 200, 300), ("hazardous", 300, 501)]


def summary(pm, name, ratio):
    a = aqi_pm25(pm.values)
    djf = pm[pm.index.month.isin([12, 1, 2])]
    annual = pm.groupby(pm.index.year).mean()
    row = dict(scenario=name, ratio=ratio, n_days=len(pm), mean=pm.mean(), annual_min=annual.min(),
               annual_max=annual.max(), djf_mean=djf.mean(), share_above_65=(pm > STD_24H).mean() * 100,
               share_djf_above_65=(djf > STD_24H).mean() * 100, mean_aqi=np.nanmean(a))
    for c, lo, hi in CATS:
        row["share_" + c] = ((a > lo) & (a <= hi)).mean() * 100 if lo else (a <= hi).mean() * 100
    row["share_good_moderate"] = (a <= 100).mean() * 100
    row["share_aqi_above_150"] = (a > 150).mean() * 100
    row["share_aqi_above_200"] = (a > 200).mean() * 100
    return row


def main(root):
    e = embassy_hourly(root, first_year=2016)
    e = e[e.time < "2025-01-01"].drop_duplicates("time")
    g = e.assign(date=e.time.dt.normalize()).groupby("date").PM25
    pm = g.mean().where(g.count() >= 18).dropna()
    L = pd.read_csv(os.path.join(OUT, "long_eid.csv"))
    P = pd.read_csv(os.path.join(OUT, "long_episodes.csv"))
    eid = L[(L.analysis == "all") & (L.outcome == "PM25")].iloc[0]
    hol = P[(P.episode == "2020 general holiday") & (P.outcome == "PM25")].iloc[0]
    blk = P[(P.episode == "2023-24 blockade programme") & (P.outcome == "PM25")].iloc[0]
    scen = [("observed", 0.0), ("eid", eid.b), ("eid_lo", eid.lo_boot), ("eid_hi", eid.hi_boot),
            ("holiday_2020", hol.b), ("blockade_2023", blk.b)]
    rows = [summary(pm * np.exp(b), name, np.exp(b)) for name, b in scen]
    R = pd.DataFrame(rows)
    obs = R.iloc[0]
    R["reduction"] = obs["mean"] - R["mean"]
    R["gap_closed_pct"] = 100 * R.reduction / (obs["mean"] - STD_ANNUAL)
    R["share_of_naqmp_gda_target"] = 100 * R.reduction / NAQMP_GDA
    R["djf_reduction"] = obs["djf_mean"] - R["djf_mean"]
    # extra good-or-moderate days per year, the NAQMP's second indicator (Table 6.2)
    R["good_moderate_days_gain"] = (R.share_good_moderate - obs["share_good_moderate"]) / 100 * 365.25
    R.to_csv(os.path.join(OUT, "limits.csv"), index=False)
    pd.set_option("display.width", 250)
    print(R.round(2).T.to_string())


if __name__ == "__main__":
    main(sys.argv[1])
