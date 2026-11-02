"""What happens to Dhaka's PM2.5 when the city empties: Eid and the prolonged disruptions of
2013-2024.

Record       Dhaka-region PM2.5 stations that pass the screens of screens.py, from 2013; the
             US Embassy monitor from 2016; ERA5 meteorology for 2012-2025 (Open-Meteo archive,
             the settings of 02_data/acquire.py).  NOx and CO at the stations whose analyzers
             pass the same screens serve as activity checks.
Strike days  ACLED hartal, blockade and strike days in the 110 km box: 2019-2024 from the
             deposit calendar; 2012-2018 derived here, with the same filter, from the ACLED
             records when they are on this computer (fetch_acled.py).
Eid          the stacked design of events_checks.py on the Eids of 2013-2024.  Each window runs
             -15..+18 days, treatment -1..+3, with window and day-of-week fixed effects and
             ERA5 meteorology; strike and disruption days are dropped, and an Eid whose
             treatment days fall in a disruption is not used.  Event bootstrap (B = 1000)
             with the station weights of the main fit; leave one event out; Eid-ul-Fitr and
             Eid-ul-Adha; monsoon (June-September) and other months; 2013-2018 and 2019-2024;
             event-time trajectory against days -30..-11 and +13..+30.
Disruptions  each episode of disruption_episodes.csv against what year, calendar month, day of
             week and meteorology predict on the whole 2013-2024 record, with Eid days, strike
             days and the other episodes dropped.  Placebo: the same calendar days moved to
             every other year without a disruption on them; the spread of the placebo
             estimates is added to the sampling error (as for the 2020 lockdown in
             events_checks.py).

TROPOMI tropospheric NO2 (domain mean, 2019 on) is a further activity check for both designs,
and Google's national mobility (2020-2022) for the pandemic episodes.

Writes out/long_eid.csv, out/long_eid_trajectory.csv, out/long_episodes.csv,
out/long_episode_placebos.csv, out/long_episode_mobility.csv, out/long_station_check.csv and,
when the ACLED records are present, Traffic/data_availability/02_event_calendars/hartal_event_days_2012_2018_DERIVED.csv.
Usage: python -I shutdowns.py <FYDP_D root>
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cams_pooled import DHAKA  # noqa: E402
from cams_shocks import embassy_hourly, met_daily, tropomi_daily  # noqa: E402
from events_checks import eid_fit, eid_stack, eid_X, point_fe, pooled  # noqa: E402
from events_hourly import METC, add_met, aqi_pm25, ols_fe  # noqa: E402
from screens import gas_allowed, screens  # noqa: E402

DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "..", "out")
RNG = np.random.default_rng(20261102)
B_EVENTS = 1000
B_TRAJ = 500
START, END = pd.Timestamp("2013-01-01"), pd.Timestamp("2024-12-31")
MET_FILES = ("meteo_dhaka_hourly_2012_2018.csv", "meteo_dhaka_hourly_filled.csv")
BOX = dict(south=23.284, west=89.860, north=24.276, east=90.940)     # Traffic/gates/gates_blocked.py
WORDS = ("hartal", "blockade", "oborodh", "strike")
MONSOON = (6, 7, 8, 9)
OUTCOMES = {"PM25": ("PM25", lambda s: np.log(s.y.values)),
            "PM25_ugm3": ("PM25", lambda s: s.y.values),
            "AQI": ("PM25", lambda s: aqi_pm25(s.y.values)),
            "NOX": ("NOX", lambda s: np.log(s.y.values)),
            "CO": ("CO", lambda s: np.log(s.y.values)),
            "TROPOMI": ("TROPOMI", lambda s: np.log(s.y.values))}
LOGS = ("PM25", "NOX", "CO", "TROPOMI")


def pct(b):
    return 100 * (np.exp(b) - 1)


def evdir(root):
    return os.path.join(root, "Traffic", "data_availability", "02_event_calendars")


# ----------------------------------------------------------------------------- calendars
def strike_days(root):
    """ACLED strike-like days in the box.  Returns (set of dates, years covered)."""
    ev = evdir(root)
    days = set(pd.read_csv(os.path.join(ev, "hartal_event_days_DERIVED.csv"), parse_dates=["date"]).date)
    derived = os.path.join(ev, "hartal_event_days_2012_2018_DERIVED.csv")
    raw = os.path.join(root, "Traffic", "gates", "out", "acled_bangladesh_2012_2024.json")
    if os.path.exists(raw):
        byday = {}
        for r in json.loads(open(raw, encoding="utf-8").read()):
            try:
                lat, lon = float(r["latitude"]), float(r["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (BOX["south"] <= lat <= BOX["north"] and BOX["west"] <= lon <= BOX["east"]):
                continue
            txt = " ".join(str(r.get(k, "")) for k in ("sub_event_type", "notes", "event_type")).lower()
            d = str(r.get("event_date", ""))[:10]
            if any(w in txt for w in WORDS) and "2012-01-01" <= d < "2019-01-01":
                byday.setdefault(d, []).append("riot" in str(r.get("event_type", "")).lower())
        pd.DataFrame([dict(date=d, n_events=len(v), n_riot_coded=sum(v), riot_share=round(sum(v) / len(v), 3))
                      for d, v in sorted(byday.items())]).to_csv(derived, index=False)
    if os.path.exists(derived):
        days |= set(pd.read_csv(derived, parse_dates=["date"]).date)
        return days, "2012-2024"
    return days, "2019-2024"


def episodes(root, strikes):
    """{episode: dict(kind, start, end, days)} from disruption_episodes.csv."""
    E = pd.read_csv(os.path.join(evdir(root), "disruption_episodes.csv"), parse_dates=["start", "end"])
    out = {}
    for r in E.itertuples():
        if r.days.startswith("ACLED"):
            ds = {d for d in strikes if r.start <= d <= r.end}
        else:
            ds = set()
            for part in r.days.split(";"):
                a, b = part.split("..")
                ds |= set(pd.date_range(a, b))
        out[r.episode] = dict(kind=r.kind, start=r.start, end=r.end, days=ds)
    return out


def eid_calendar(root):
    ev = pd.read_csv(os.path.join(evdir(root), "eid_dates_2013_2024.csv"), parse_dates=["date"])
    return ev.sort_values("date").reset_index(drop=True)


# ----------------------------------------------------------------------------- data
def station_frames(root, metd, eid_days, strikes, epi_of):
    """{tracer: {station: daily frame}} with the flags the designs need."""
    ok_pm, gas_ok, flat = screens()
    cams = pd.read_csv(os.path.join(DATA, "cams_hourly_qc.csv.gz"), parse_dates=["time"])
    cams = cams[(cams.time >= START) & (cams.time < END + pd.Timedelta(days=1)) & cams.station.isin(DHAKA)]
    emb = embassy_hourly(root, first_year=2016)
    emb = emb[(emb.time >= START) & (emb.time < END + pd.Timedelta(days=1))]
    allh = pd.concat([cams[["station", "time", "PM25", "NOX", "CO"]], emb], ignore_index=True)
    frames = {}
    for st, h in allh.groupby("station"):
        h = h.drop_duplicates("time").assign(date=lambda x: x.time.dt.normalize())
        for tracer in ("PM25", "NOX", "CO"):
            if tracer == "PM25" and not (st == "US Embassy" or st in ok_pm):
                continue
            if tracer != "PM25" and (st == "US Embassy" or not gas_allowed(st, tracer, "Dhaka", gas_ok, flat)):
                continue
            g = h.groupby("date")[tracer]
            d = g.mean().where(g.count() >= 18).dropna()
            d = d[d > 0]
            if len(d) < 300:
                continue
            s = add_met(d.to_frame("y").join(metd, how="inner").dropna(
                subset=["y", "lvc", "T", "rh", "pr", "wd_s", "wd_c"]))
            frames.setdefault(tracer, {})[st] = flags(s, eid_days, strikes, epi_of)
    tr = tropomi_daily(root).loc["2019-01-01":END]
    frames["TROPOMI"] = {"domain": flags(add_met(tr.to_frame("y").join(metd, how="inner").dropna()),
                                         eid_days, strikes, epi_of)}
    return frames


def flags(s, eid_days, strikes, epi_of):
    s["dow"] = s.index.dayofweek
    s["year"] = s.index.year
    s["month"] = s.index.month
    s["eid"] = s.index.isin(list(eid_days)).astype(int)
    s["hart"] = s.index.isin(list(strikes)).astype(int)
    s["epi"] = [epi_of.get(t, "") for t in s.index]
    s["covid"] = (s.epi != "").astype(int)     # eid_stack drops covid == 1 and hart == 1
    return s.sort_index()


def station_check(frames):
    """Daily log-PM2.5 correlation of each CAMS station with the Embassy, 2016-2018 and 2019-2024."""
    pm = frames["PM25"]
    if "US Embassy" not in pm:
        return pd.DataFrame()
    e = np.log(pm["US Embassy"].y)
    rows = []
    for st, s in pm.items():
        rows.append(dict(station=st, period="all", n_days=len(s), first=s.index.min().date(),
                         last=s.index.max().date(),
                         gases=";".join(g for g in ("NOX", "CO") if st in frames.get(g, {}))))
        if st == "US Embassy":
            continue
        j = pd.concat([np.log(s.y), e], axis=1, join="inner").dropna()
        j.columns = ["x", "e"]
        for lab, a, b in (("2016-2018", "2016-01-01", "2018-12-31"), ("2019-2024", "2019-01-01", "2024-12-31")):
            jj = j.loc[a:b]
            if len(jj) > 100:
                rows.append(dict(station=st, period=lab, n_days=len(jj), r_log=jj.x.corr(jj.e),
                                 ratio=float(np.exp((jj.x - jj.e).mean()))))
        rows.append(dict(station=st, period="days 2013-2015", n_days=int(s.loc["2013-01-01":"2015-12-31"].shape[0])))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- Eid
def pieces(s, events, yfun, treat=(-1, 3), comp=((-15, 18),), rels=None):
    """Within-window demeaned cross-products of each event's window, so that a resample of the
    events is fitted by summing them.  Returns {event: (A, c, n_treat, n)}."""
    out = {}
    for t in set(events):
        W = eid_stack(s, [t], treat=treat, comp=comp)
        if len(W) < 2:
            continue
        if rels is None:
            Z = np.column_stack([W.treat.values, eid_X(W)])
        else:
            Z = np.column_stack([(W.rel == r).astype(float).values for r in rels] + [eid_X(W)])
        y = np.asarray(yfun(W), float)
        Zd, yd = Z - Z.mean(0), y - y.mean()
        out[t] = (Zd.T @ Zd, Zd.T @ yd, float(W.treat.sum()), len(W))
    return out


def solve(pc, events, ncoef=1, min_treat=10, min_n=60):
    got = [pc[t] for t in events if t in pc]
    if not got:
        return None
    A = sum(g[0] for g in got)
    c = sum(g[1] for g in got)
    if sum(g[2] for g in got) < min_treat or sum(g[3] for g in got) < min_n:
        return None
    return np.linalg.lstsq(A, c, rcond=None)[0][:ncoef]


def seen(frames, events):
    """Events with at least one observed treatment day at some station."""
    return sum(any(((s.index >= t - pd.Timedelta(days=1)) & (s.index <= t + pd.Timedelta(days=3))
                    & (s.hart == 0) & (s.covid == 0)).any() for s in frames.values()) for t in events)


def eid_row(frames, events, yfun, boot=True, **kw):
    fits = {x: eid_fit(s, events, yfun, **kw) for x, s in frames.items()}
    fits = {x: f for x, f in fits.items() if f}
    if not fits:
        return None
    pb, pse, k, w, i2 = pooled(fits)
    row = dict(b=pb, lo=pb - 1.96 * pse, hi=pb + 1.96 * pse, k=k, I2=i2, n_events=seen(frames, events),
               stations=";".join(sorted(fits)))
    if boot and len(events) >= 3:
        pc = {x: pieces(frames[x], events, yfun, **kw) for x in fits}
        arr = np.array(events, dtype="datetime64[ns]")
        draws = []
        for _ in range(B_EVENTS):
            ev = [pd.Timestamp(e) for e in RNG.choice(arr, len(arr), replace=True)]
            bs = {x: solve(pc[x], ev) for x in fits}
            bs = {x: float(v[0]) for x, v in bs.items() if v is not None}
            if bs:
                draws.append(sum(w[x] * v for x, v in bs.items()) / sum(w[x] for x in bs))
        row.update(lo_boot=np.percentile(draws, 2.5), hi_boot=np.percentile(draws, 97.5), n_draws=len(draws))
    return row


def eid_analysis(frames, eid):
    usable = list(eid.date)
    kind = dict(zip(eid.date, eid.festival))
    subsets = {"all": usable,
               "fitr": [t for t in usable if "Fitr" in kind[t]],
               "adha": [t for t in usable if "Fitr" not in kind[t]],
               "monsoon": [t for t in usable if t.month in MONSOON],
               "other_months": [t for t in usable if t.month not in MONSOON],
               "2013_2018": [t for t in usable if t.year <= 2018],
               "2019_2024": [t for t in usable if t.year >= 2019]}
    rows = []
    for oname, (tracer, yfun) in OUTCOMES.items():
        fr = frames.get(tracer, {})
        for lab, ev in subsets.items():
            if lab != "all" and oname not in LOGS:
                continue
            r = eid_row(fr, ev, yfun)
            if r:
                rows.append(dict(analysis=lab, outcome=oname, **r))
        if oname != "PM25":
            continue
        for t in usable:
            r = eid_row(fr, [e for e in usable if e != t], yfun, boot=False)
            if r:
                rows.append(dict(analysis="loo_" + t.strftime("%Y-%m-%d"), outcome=oname, **r))
        for lab, kw in {"treat_0_4": dict(treat=(0, 4)),
                        "comp_clean": dict(comp=((-30, -8), (12, 30)))}.items():
            r = eid_row(fr, usable, yfun, boot=False, **kw)
            if r:
                rows.append(dict(analysis=lab, outcome=oname, **r))
        # each event on its own, for the event-level figure: the station estimates (at least
        # three observed treatment days) averaged with the weights of the main fit
        fits = {x: eid_fit(s, usable, yfun) for x, s in fr.items()}
        w = pooled({x: f for x, f in fits.items() if f})[3]
        pc = {x: pieces(fr[x], usable, yfun) for x in w}
        for t in usable:
            bs = {x: solve(pc[x], [t], min_treat=3, min_n=20) for x in w}
            bs = {x: float(v[0]) for x, v in bs.items() if v is not None}
            if bs:
                rows.append(dict(analysis="event_" + t.strftime("%Y-%m-%d"), outcome=oname,
                                 b=sum(w[x] * v for x, v in bs.items()) / sum(w[x] for x in bs),
                                 k=len(bs), n_events=1, stations=";".join(sorted(bs))))
    R = pd.DataFrame(rows)
    logs = R.outcome.isin(LOGS)
    for c in ("b", "lo", "hi", "lo_boot", "hi_boot"):
        R[c + "_pct"] = np.where(logs, pct(R[c]), np.nan)
    return R


def trajectories(frames, eid, rels=range(-10, 13)):
    usable = list(eid.date)
    rels = list(rels)
    arr = np.array(usable, dtype="datetime64[ns]")
    rows = []
    for oname in LOGS:
        tracer, yfun = OUTCOMES[oname]
        fr = frames.get(tracer, {})
        pc = {x: pieces(s, usable, yfun, treat=(-10, 12), comp=((-30, -11), (13, 30)), rels=rels)
              for x, s in fr.items()}
        base = {x: solve(p, usable, ncoef=len(rels), min_n=200) for x, p in pc.items()}
        base = {x: v for x, v in base.items() if v is not None}
        if not base:
            continue
        pt = np.mean(list(base.values()), axis=0)
        draws = []
        for _ in range(B_TRAJ):
            ev = [pd.Timestamp(e) for e in RNG.choice(arr, len(arr), replace=True)]
            bs = [solve(pc[x], ev, ncoef=len(rels), min_n=200) for x in base]
            bs = [v for v in bs if v is not None]
            if bs:
                draws.append(np.mean(bs, axis=0))
        draws = np.array(draws)
        for i, r in enumerate(rels):
            rows.append(dict(outcome=oname, rel=r, pct=pct(pt[i]), lo=pct(np.percentile(draws[:, i], 2.5)),
                             hi=pct(np.percentile(draws[:, i], 97.5)), k=len(base), n_draws=len(draws)))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- disruptions
def epi_frame(s, ind_days, drop_days):
    w = s[(s.eid == 0) & ~s.index.isin(list(drop_days))].copy()
    w = w[(w.hart == 0) | w.index.isin(list(ind_days))]
    w["ind"] = w.index.isin(list(ind_days)).astype(float)
    return w


def epi_X(w):
    return np.column_stack([w[METC].values] + [(w.dow == d).astype(float).values for d in range(1, 7)]
                           + [(w.month == m).astype(float).values for m in range(2, 13)])


def epi_fit(s, ind_days, drop_days, yfun, point=False):
    w = epi_frame(s, ind_days, drop_days)
    yrs = set(pd.DatetimeIndex(sorted(ind_days)).year)
    same = w.year.isin(yrs)
    if w.ind.sum() < 10 or (same & (w.ind == 0)).sum() < 60 or (~same).sum() < 300:
        return None
    if point:
        return point_fe(yfun(w), w.ind.values, epi_X(w), w.year.values)
    return ols_fe(yfun(w), w.ind.values, epi_X(w), w.year.values)


def shift_years(days, k):
    return {d + pd.DateOffset(years=k) for d in days}


def episode_analysis(frames, epis):
    all_epi = set().union(*[e["days"] for e in epis.values()])
    rows, prow = [], []
    for name, e in epis.items():
        days = e["days"]
        other = all_epi - days
        y0 = min(days).year
        for oname, (tracer, yfun) in OUTCOMES.items():
            fr = frames.get(tracer, {})
            fits = {x: epi_fit(s, days, other, yfun) for x, s in fr.items()}
            fits = {x: f for x, f in fits.items() if f}
            if not fits:
                continue
            pb, pse, k, w, i2 = pooled(fits)
            plac = {}
            for yr in range(START.year, END.year + 1):
                k_ = yr - y0
                if k_ == 0:
                    continue
                sh = {d for d in shift_years(days, k_) if START <= d <= END}
                if len(sh) < 0.8 * len(days) or sh & all_epi:
                    continue
                f = {x: epi_fit(s, sh, all_epi, yfun, point=True) for x, s in fr.items() if x in fits}
                f = {x: v for x, v in f.items() if v is not None}
                if len(f) >= max(1, (k + 1) // 2):
                    plac[yr] = sum(w[x] * v for x, v in f.items()) / sum(w[x] for x in f)
                    prow.append(dict(episode=name, outcome=oname, placebo_year=yr, b=plac[yr], k=len(f)))
            sd = float(np.std(list(plac.values()), ddof=1)) if len(plac) >= 3 else np.nan
            tot = np.sqrt(pse ** 2 + sd ** 2) if np.isfinite(sd) else np.nan
            n_obs = int(max(epi_frame(s, days, other).ind.sum() for x, s in fr.items() if x in fits))
            rows.append(dict(episode=name, kind=e["kind"], start=e["start"].date(), end=e["end"].date(),
                             n_days=len(days), n_obs_days=n_obs, outcome=oname, b=pb, se=pse,
                             lo=pb - 1.96 * pse, hi=pb + 1.96 * pse, I2=i2, k=k, stations=";".join(sorted(fits)),
                             n_placebo=len(plac), placebo_sd=sd, placebo_mean=np.mean(list(plac.values())) if plac else np.nan,
                             lo_cal=pb - 1.96 * tot, hi_cal=pb + 1.96 * tot))
    R = pd.DataFrame(rows)
    logs = R.outcome.isin(LOGS)
    for c in ("b", "lo", "hi", "lo_cal", "hi_cal", "placebo_mean"):
        R[c + "_pct"] = np.where(logs, pct(R[c]), np.nan)
    return R, pd.DataFrame(prow)


def mobility_check(root, epis, eid_days, strikes):
    """Google mobility (national, 2020-02-15 to 2022-10-15) on each episode's days: the mean
    percent change from Google's January-February 2020 baseline, and its difference from the
    other days of the same year (Eid, strike and episode days left out)."""
    import glob
    fs = sorted(glob.glob(os.path.join(root, "02_data", "raw", "google_mobility", "*_BD_*.csv")))
    if not fs:
        return pd.DataFrame()
    cols = {"transit_stations_percent_change_from_baseline": "transit",
            "workplaces_percent_change_from_baseline": "workplaces",
            "residential_percent_change_from_baseline": "residential"}
    m = pd.concat([pd.read_csv(f, parse_dates=["date"]) for f in fs], ignore_index=True)
    m = m[m.sub_region_1.isna()].set_index("date").sort_index()[list(cols)].rename(columns=cols)
    all_epi = set().union(*[e["days"] for e in epis.values()])
    rows = []
    for name, e in epis.items():
        d = sorted(x for x in e["days"] if x in m.index)
        if len(d) < 5:
            continue
        yrs = {x.year for x in d}
        rest = m[m.index.year.isin(list(yrs)) & ~m.index.isin(list(all_epi | set(eid_days) | set(strikes)))]
        row = dict(episode=name, n_days=len(d))
        for c in cols.values():
            row[c] = m.loc[d, c].mean()
            row[c + "_vs_rest_of_year"] = m.loc[d, c].mean() - rest[c].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def main(root):
    metd, _ = met_daily(root, MET_FILES)
    strikes, strike_years = strike_days(root)
    epis = episodes(root, strikes)
    epi_of = {}
    for name, e in epis.items():
        for d in e["days"]:
            epi_of.setdefault(d, name)
    eid = eid_calendar(root)
    eid = eid[(eid.date >= START) & (eid.date <= END)]
    eid_days = {t + pd.Timedelta(days=k) for t in eid.date for k in range(-1, 4)}
    # an Eid whose treatment days fall in a disruption is not usable
    bad = [t for t in eid.date if any((t + pd.Timedelta(days=k)) in epi_of for k in range(-1, 4))]
    usable = eid[~eid.date.isin(bad)]
    print("strike days from ACLED cover", strike_years, "| Eids:", len(eid), "usable:", len(usable),
          "| not usable:", [t.strftime("%Y-%m-%d") for t in bad])
    frames = station_frames(root, metd, eid_days, strikes, epi_of)
    print({k: sorted(v) for k, v in frames.items()})
    C = station_check(frames)
    C.to_csv(os.path.join(OUT, "long_station_check.csv"), index=False)
    pd.set_option("display.width", 250)
    print(C.round(3).to_string(index=False))

    E = eid_analysis(frames, usable)
    E["strike_calendar"] = strike_years
    E.to_csv(os.path.join(OUT, "long_eid.csv"), index=False)
    print(E.drop(columns=["stations"]).round(3).to_string(index=False))
    T = trajectories(frames, usable)
    T.to_csv(os.path.join(OUT, "long_eid_trajectory.csv"), index=False)
    print(T.round(1).to_string(index=False))

    P, PL = episode_analysis(frames, epis)
    P["strike_calendar"] = strike_years
    P.to_csv(os.path.join(OUT, "long_episodes.csv"), index=False)
    PL.to_csv(os.path.join(OUT, "long_episode_placebos.csv"), index=False)
    print(P.drop(columns=["stations", "kind"]).round(3).to_string(index=False))
    M = mobility_check(root, epis, eid_days, strikes)
    M.to_csv(os.path.join(OUT, "long_episode_mobility.csv"), index=False)
    print(M.round(1).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
