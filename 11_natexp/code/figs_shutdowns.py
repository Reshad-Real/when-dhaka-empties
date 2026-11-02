"""Figures of the Eid and disruption analysis (shutdowns.py, limits.py).

fig2_eid_profile.png   PM2.5, surface NOx and the TROPOMI NO2 column by day relative to Eid,
                       against days -30..-11 and +13..+30, pooled over stations, with
                       event-bootstrap 95% intervals (out/long_eid_trajectory.csv).
fig3_shocks.png        (a) each Eid's PM2.5 change (out/long_eid.csv, rows event_*), with the
                       pooled estimate and its event-bootstrap interval; (b) each prolonged
                       disruption's PM2.5 change with its 95% model interval and its
                       placebo-calibrated interval (out/long_episodes.csv), Eid for reference.
fig4_limits.png        (a) share of days in each AQI category at the US Embassy, 2016-2024,
                       observed and with every day reduced as on Eid or in the 2020 general
                       holiday; (b) monthly mean PM2.5, observed and with the Eid reduction,
                       against the national 24-hour and annual standards (out/limits.csv
                       for the ratios).
Drawn at the printed width (figstyle.py).
Usage: python -I figs_shutdowns.py <FYDP_D root>
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import figstyle as fs  # noqa: E402
from cams_shocks import embassy_hourly  # noqa: E402
from events_hourly import aqi_pm25  # noqa: E402

OUT = os.path.join(HERE, "..", "out")
INK, INK2, GRID = fs.INK, fs.INK2, fs.GRID
# validated categorical slots 1-3 (dataviz reference palette), as in fig5_events.py
BLUE, ORANGE, GREEN = "#2a78d6", "#eb6834", "#1baf7a"
# AQI category colours as published with the index (always labelled)
AQI_COL = ["#00e400", "#ffff00", "#ff7e00", "#ff0000", "#8f3f97", "#7e0023"]
AQI_LAB = ["Good", "Moderate", "Unhealthy for sensitive groups", "Unhealthy", "Very unhealthy", "Hazardous"]


def pct(b):
    return 100 * (np.exp(b) - 1)


def fig_profile(plt):
    T = pd.read_csv(os.path.join(OUT, "long_eid_trajectory.csv"))
    names = [("PM25", "(a) PM$_{2.5}$", BLUE), ("NOX", "(b) Surface NO$_x$", ORANGE),
             ("TROPOMI", "(c) TROPOMI NO$_2$ column", GREEN)]
    fig, ax = plt.subplots(1, 3, figsize=(fs.WIDTH, 2.6), sharey=True)
    for a, (o, title, col) in zip(ax, names):
        q = T[T.outcome == o].sort_values("rel")
        a.axvspan(-1.5, 3.5, color=GRID, lw=0, zorder=0)
        a.fill_between(q.rel, q.lo, q.hi, color=col, alpha=0.18, lw=0)
        a.plot(q.rel, q.pct, color=col, lw=1.6, marker="o", ms=2.6)
        a.axhline(0, color=INK2, lw=0.8)
        a.set_title(title, loc="left")
        a.set_xlabel("Day relative to Eid")
        a.set_xticks(range(-10, 13, 5))
        a.spines[["top", "right"]].set_visible(False)
        a.grid(axis="y", color=GRID, lw=0.6)
        k = int(q.k.iloc[0])
        a.text(0.98, 0.04, ("%d station%s" % (k, "s" if k > 1 else "")) if o != "TROPOMI" else "domain mean",
               transform=a.transAxes, ha="right", va="bottom", color=INK)
    ax[0].set_ylabel("Change against the baseline days (%)")
    fig.tight_layout(w_pad=0.8)
    fig.savefig(os.path.join(OUT, "fig2_eid_profile.png"))


def fig_shocks(plt):
    L = pd.read_csv(os.path.join(OUT, "long_eid.csv"))
    P = pd.read_csv(os.path.join(OUT, "long_episodes.csv"))
    ev = L[L.analysis.str.startswith("event_") & (L.outcome == "PM25")].copy()
    ev["date"] = pd.to_datetime(ev.analysis.str[6:])
    kind = pd.read_csv(os.path.join(HERE, "..", "..", "Traffic", "data_availability", "02_event_calendars",
                                    "eid_dates_2013_2024.csv"), parse_dates=["date"])
    ev = ev.merge(kind[["date", "festival"]], on="date")
    main = L[(L.analysis == "all") & (L.outcome == "PM25")].iloc[0]
    fig = plt.figure(figsize=(fs.WIDTH, 6.6))
    ax = [fig.add_axes([0.085, 0.645, 0.895, 0.315]), fig.add_axes([0.385, 0.075, 0.595, 0.475])]
    a = ax[0]
    x0, x1 = pd.Timestamp("2013-01-01"), pd.Timestamp("2025-01-01")
    a.fill_between([x0, x1], main.lo_boot_pct, main.hi_boot_pct, color=BLUE, alpha=0.12, lw=0)
    a.plot([x0, x1], [main.b_pct] * 2, color=BLUE, lw=1.2)
    a.text(pd.Timestamp("2019-11-01"), main.hi_boot_pct + 2, "pooled, %s%%" % ("%.1f" % main.b_pct).replace("-", "−"),
           va="bottom", ha="left", color=INK)
    for fest, mk in (("Eid-ul-Fitr", "o"), ("Eid-ul-Adha", "s")):
        q = ev[ev.festival == fest]
        a.scatter(q.date, pct(q.b), marker=mk, s=22, color=BLUE if mk == "o" else "white",
                  edgecolors=BLUE, lw=1.0, zorder=3, label=fest)
    a.axhline(0, color=INK2, lw=0.8)
    a.set_xlim(x0, x1)
    a.set_ylabel("PM$_{2.5}$ change, days $-$1..+3 (%)")
    a.set_title("(a) Each Eid, 2013–2024", loc="left")
    a.legend(frameon=False, loc="upper right", ncol=2)
    a.spines[["top", "right"]].set_visible(False)
    a.grid(axis="y", color=GRID, lw=0.6)

    b = ax[1]
    order = ["2013-14 pre-election blockades", "2015 nationwide blockade", "2018 road-safety protests",
             "2020 general holiday", "2021 strict lockdowns", "2023-24 blockade programme",
             "2024 uprising and curfew"]
    lab = {"2013-14 pre-election blockades": "2013-14 pre-election blockades (28 d)",
           "2015 nationwide blockade": "2015 nationwide blockade (90 d)",
           "2018 road-safety protests": "2018 road-safety protests (11 d)",
           "2020 general holiday": "2020 general holiday (66 d)",
           "2021 strict lockdowns": "2021 strict lockdowns (55 d)",
           "2023-24 blockade programme": "2023-24 blockade and hartal days (44 d)",
           "2024 uprising and curfew": "2024 uprising and curfew (19 d)"}
    Q = P[P.outcome == "PM25"].set_index("episode").reindex(order)
    y = np.arange(len(order)) + 1
    b.errorbar(Q.b_pct, y + 0.12, xerr=[Q.b_pct - Q.lo_pct, Q.hi_pct - Q.b_pct], fmt="o", color=BLUE,
               ms=4.5, capsize=2, lw=1.2, label="95% model interval")
    ok = Q.lo_cal_pct.notna()
    eb = b.errorbar(Q.b_pct[ok], y[ok.values] - 0.12, xerr=[(Q.b_pct - Q.lo_cal_pct)[ok], (Q.hi_cal_pct - Q.b_pct)[ok]],
                    fmt="none", ecolor=INK2, capsize=2, lw=1.0, label="with placebo spread")
    eb[2][0].set_linestyle((0, (3, 2)))
    b.errorbar([main.b_pct], [0], xerr=[[main.b_pct - main.lo_boot_pct], [main.hi_boot_pct - main.b_pct]],
               fmt="D", color=BLUE, ms=4.5, capsize=2, lw=1.2)
    b.axvline(0, color=INK2, lw=0.8)
    b.set_yticks(np.r_[0, y])
    b.set_yticklabels(["Eid, pooled (22 events)"] + [lab[o] for o in order])
    b.invert_yaxis()
    b.set_xlabel("PM$_{2.5}$ change (%)")
    b.set_title("(b) Prolonged disruptions", loc="left")
    b.legend(frameon=False, loc="lower right")
    b.spines[["top", "right"]].set_visible(False)
    b.grid(axis="x", color=GRID, lw=0.6)
    fig.savefig(os.path.join(OUT, "fig3_shocks.png"))


def fig_limits(plt, root):
    Lm = pd.read_csv(os.path.join(OUT, "limits.csv")).set_index("scenario")
    e = embassy_hourly(root, first_year=2016)
    e = e[e.time < "2025-01-01"].drop_duplicates("time")
    g = e.assign(date=e.time.dt.normalize()).groupby("date").PM25
    pm = g.mean().where(g.count() >= 18).dropna()
    fig, ax = plt.subplots(1, 2, figsize=(fs.WIDTH, 3.1), gridspec_kw={"width_ratios": [1.15, 1]})
    a = ax[0]
    rows = [("observed", "Observed"), ("eid", "Eid every day"), ("holiday_2020", "2020 holiday\nevery day")]
    edges = [0, 50, 100, 150, 200, 300, 501]
    for i, (sc, name) in enumerate(rows):
        aq = aqi_pm25((pm * Lm.loc[sc, "ratio"]).values)
        left = 0.0
        for j in range(6):
            lo, hi = edges[j], edges[j + 1]
            share = 100 * (((aq > lo) & (aq <= hi)).mean() if lo else (aq <= hi).mean())
            a.barh(i, share, left=left, color=AQI_COL[j], edgecolor="white", lw=1.0, height=0.62)
            if share >= 6:
                a.text(left + share / 2, i, "%.0f" % share, ha="center", va="center",
                       color="white" if j >= 3 else INK)
            left += share
    a.set_yticks(range(len(rows)))
    a.set_yticklabels([r[1] for r in rows])
    a.invert_yaxis()
    a.set_xlim(0, 100)
    a.set_xlabel("Share of days, US Embassy 2016–2024 (%)")
    a.set_title("(a) Daily PM$_{2.5}$ AQI category", loc="left")
    from matplotlib.patches import Patch
    a.legend(handles=[Patch(color=c, label=l) for c, l in zip(AQI_COL, AQI_LAB)], frameon=False,
             loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2)
    a.spines[["top", "right"]].set_visible(False)

    b = ax[1]
    m = pm.groupby(pm.index.month).mean()
    r = Lm.loc["eid", "ratio"]
    b.plot(m.index, m.values, color=INK2, lw=1.6, marker="o", ms=3, label="Observed")
    b.plot(m.index, m.values * r, color=BLUE, lw=1.6, marker="o", ms=3, label="Eid every day")
    b.fill_between(m.index, m.values * Lm.loc["eid_lo", "ratio"], m.values * Lm.loc["eid_hi", "ratio"],
                   color=BLUE, alpha=0.15, lw=0)
    for v, t in ((65, "65 (24 h)"), (35, "35 (annual)")):
        b.axhline(v, color=INK2, lw=0.8, ls=(0, (3, 2)))
        b.text(0.7, v + 2, t, va="bottom", ha="left", color=INK)
    b.set_xticks(range(1, 13))
    b.set_xticklabels("JFMAMJJASOND")
    b.set_xlabel("Month")
    b.set_ylabel("Monthly mean PM$_{2.5}$ ($\\mu$g m$^{-3}$)")
    b.set_title("(b) Seasonal cycle", loc="left")
    b.set_ylim(0, None)
    b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.55, 1.0))
    b.spines[["top", "right"]].set_visible(False)
    b.grid(axis="y", color=GRID, lw=0.6)
    fig.tight_layout(w_pad=1.2)
    fig.savefig(os.path.join(OUT, "fig4_limits.png"))


def main(root):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fs.apply(plt)
    fig_profile(plt)
    fig_shocks(plt)
    fig_limits(plt, root)
    print("wrote fig2_eid_profile.png, fig3_shocks.png, fig4_limits.png")


if __name__ == "__main__":
    main(sys.argv[1])
