"""Re-derive every amber number (\\pn{...}) in paper/working/manuscript.tex from 11_natexp/out and
report any mismatch, and any amber number no claim accounts for.

How it works
------------
Every preliminary number in the manuscript is wrapped in \\pn{...}.  A claim names an
anchor (a short piece of manuscript text that occurs exactly once) and the values of the
next N amber numbers after it, each computed from the result files.  The checker

  * finds each anchor (it must occur exactly once),
  * takes the next N \\pn{} occurrences after it, in order,
  * parses each printed value (signs, $-$, thousands separators, "a--b" ranges) and
    compares it with the derived value rounded half-up to the printed number of decimals
    (or within an explicit tolerance for "about" numbers),
  * reports every \\pn{} that no claim consumed, and every \\pn{} consumed twice.

Exit status is non-zero on any mismatch, unmatched anchor or uncovered number, so the
script can gate a build.

Usage:  python -I verify_claims.py              check
        python -I verify_claims.py --inventory  list every amber number with context
"""
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
TEX = os.environ.get("VERIFY_TEX", os.path.join(HERE, "..", "paper", "working", "manuscript.tex"))
# the highlights are a file for the journal and live with the others in paper/submission
HIGHLIGHTS = os.path.join(HERE, "..", "paper", "submission", "highlights.txt")
ROOT = os.path.join(HERE, "..", "..")

PN = re.compile(r"\\pn\{((?:[^{}]|\{[^{}]*\})*)\}")


# ------------------------------------------------------------------ parsing the text
def amber(text):
    out = []
    for m in PN.finditer(text):
        line_start = text.rfind(chr(10), 0, m.start()) + 1
        if text[line_start:m.start()].lstrip().startswith("%"):
            continue                       # inside a LaTeX comment
        if not re.search(r"[0-9]", m.group(1)):
            continue                       # e.g. the banner's colour sample
        out.append((m.start(), m.group(1)))
    return out


def parse_printed(raw):
    """Printed amber content -> (kind, values, decimals).  kind: 'num' or 'range'."""
    t = raw.replace("$", "").replace("{", "").replace("}", "").replace(",", "").strip()
    t = t.replace("\u2212", "-")
    if "--" in t:
        a, b = t.split("--")
        return "range", [float(a), float(b)], [dec(a), dec(b)]
    return "num", [float(t)], [dec(t)]


def dec(s):
    s = s.strip().lstrip("+-")
    return len(s.split(".")[1]) if "." in s else 0


def round_half_up(x, d):
    q = Decimal(1).scaleb(-d)
    return float(Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP))


# ------------------------------------------------------------------ result files
def csv(name):
    return pd.read_csv(os.path.join(OUT, name))


class R:
    """Lazy accessors for the result files used by the claims."""

    def __init__(self):
        self.mob = csv("mobility_shocks.csv").set_index("shock")
        self.act = csv("shock_activity.csv")
        self.bd = csv("robust_bootstrap_days.csv")
        self.bh = csv("robust_bh_bootstrap.csv")
        self.bl = csv("robust_bootstrap_blocklen.csv")
        self.pool = csv("robust_pooled.csv")
        self.hp = csv("hourly_profiles.csv")
        self.share = csv("pm_share_by_hour.csv")
        self.wcheck = csv("weighting_check.csv")
        self.ev = csv("events_pooled.csv")
        self.evst = csv("events_station_units.csv")
        self.aqi = csv("aqi_by_shock.csv").set_index("event")
        self.scen = csv("aqi_scenarios.csv").set_index("scenario")
        self.qc = csv("cams_qc_report.csv").set_index("rule")
        self.val = csv("cams_validation.csv").set_index("station")
        self.eidc = csv("eid_checks.csv")
        self.etraj = csv("eid_trajectory.csv")
        self.lock = csv("lockdown_checks.csv")
        self.etr = csv("events_tracers.csv")
        self.rec = csv("reconstruct.csv")
        self.dec = csv("decompose.csv")
        self.hb = csv("hourly_boot.csv")
        self.cap = csv("aqi_cap.csv")
        self.mech = csv("mechanism.csv")
        self.dom = csv("aqi_dominance.csv")
        self.ann = csv("aqi_annualization.csv")
        self.gap = csv("gapfill_errors.csv").set_index("subset")
        self.strike = csv("strike_local.csv")
        self.flat = csv("flatline_diagnostics.csv")
        self.miss = csv("missingness_dow.csv")
        self.clock = csv("clock_check.csv").set_index("station")
        self.eev = csv("eid_by_event.csv")
        self.stw = csv("boot_stability_weekly.csv")
        self.sth = csv("boot_stability_hourly.csv")
        # the Eid and disruption analysis (shutdowns.py, limits.py)
        self.leid = csv("long_eid.csv")
        self.ltr = csv("long_eid_trajectory.csv")
        self.lep = csv("long_episodes.csv")
        self.lmb = csv("long_episode_mobility.csv").set_index("episode")
        self.lsc = csv("long_station_check.csv")
        self.lmt = csv("limits.csv").set_index("scenario")
        pl = csv("long_episode_placebos.csv")
        self.lplac = 100 * (np.exp(pl[pl.outcome == "PM25"].b) - 1)    # placebo estimates, percent

    def le(self, analysis, outcome, field):
        q = self.leid[(self.leid.analysis == analysis) & (self.leid.outcome == outcome)]
        assert len(q) == 1, (analysis, outcome)
        return float(q[field].iloc[0])

    def le_rows(self, prefix, outcome):
        return self.leid[self.leid.analysis.str.startswith(prefix) & (self.leid.outcome == outcome)]

    def levents(self):
        q = self.le_rows("event_", "PM25")
        return 100 * (np.exp(q.b) - 1)

    def ltraj(self, outcome, rel):
        q = self.ltr[(self.ltr.outcome == outcome) & (self.ltr.rel == rel)]
        return float(q.pct.iloc[0])

    def lp(self, episode, outcome, field):
        q = self.lep[(self.lep.episode == episode) & (self.lep.outcome == outcome)]
        assert len(q) == 1, (episode, outcome)
        return float(q[field].iloc[0])

    def lmob(self, episode, col):
        return float(self.lmb.loc[episode, col])

    def lim(self, scenario, field):
        return float(self.lmt.loc[scenario, field])

    # -- Monte Carlo stability of the bootstrap (boot_stability.py)
    STAB_BLOCKS = ("afternoon 12-17", "evening 18-23", "daily")

    def stab_range(self, region, block, field):
        """(min, max) of a Friday PM2.5 field over the six runs."""
        q = self.stw[(self.stw.region == region) & (self.stw.block == block)][field]
        assert len(q) == 6, (region, block)
        return float(q.min()), float(q.max())

    def stab_maxdev(self, runs=None):
        """Largest move of an interval endpoint from the published run, in percentage points,
        over both regions and the afternoon, evening and daily Friday PM2.5 intervals."""
        W = self.stw[self.stw.block.isin(self.STAB_BLOCKS)]
        P = W[W.run == "published"].set_index(["region", "block"])
        W = W[W.run != "published"] if runs is None else W[W.run.isin(runs)]
        return max(max(abs(r.lo_pct - P.loc[(r.region, r.block), "lo_pct"]),
                       abs(r.hi_pct - P.loc[(r.region, r.block), "hi_pct"])) for r in W.itertuples())

    def stab_crit(self):
        """(min, max) of the simultaneous-band critical values over all curves and runs."""
        c = self.sth.groupby(["run", "region", "tracer"]).crit.first()
        return float(c.min()), float(c.max())

    def stab_common_hours(self, region, tracer, day="Fri"):
        """Clock hours at which the simultaneous band excludes zero in every one of the six runs."""
        q = self.sth[(self.sth.region == region) & (self.sth.tracer == tracer) & (self.sth.day == day)]
        sets = [set(g[g.sim_excludes_zero].hour) for _, g in q.groupby("run")]
        assert len(sets) == 6, (region, tracer, day)
        return sorted(int(h) for h in set.intersection(*sets))

    # -- helpers
    def mobility(self, shock_prefix, col):
        rows = self.mob[self.mob.index.str.startswith(shock_prefix)]
        return rows[col]

    def activity(self, shock, outcome, region, field="pct"):
        q = self.act[(self.act.shock == shock) & (self.act.outcome == outcome) & (self.act.region == region)]
        assert len(q) == 1, (shock, outcome, region, len(q))
        return float(q[field].iloc[0])

    def boot(self, region, tracer, block, day="Fri", field="pct"):
        """Joint-date bootstrap table (robust_bootstrap_days.csv)."""
        q = self.bd[(self.bd.region == region) & (self.bd.tracer == tracer) & (self.bd.block == block)
                    & (self.bd.day == day)]
        assert len(q) == 1, (region, tracer, block, day)
        return float(q[field].iloc[0])

    def bootaqi(self, region, day, field="b_point"):
        return self.boot(region, "AQI", "daily", day, field)

    def q_bh(self, region, tracer, block, day="Fri"):
        q = self.bh[(self.bh.region == region) & (self.bh.tracer == tracer) & (self.bh.block == block)
                    & (self.bh.day == day)]
        assert len(q) == 1
        return float(q.q_boot.iloc[0])

    def pooled(self, variant, region, tracer, day, block, field="pct"):
        q = self.pool[(self.pool.variant == variant) & (self.pool.region == region) & (self.pool.tracer == tracer)
                      & (self.pool.day == day) & (self.pool.block == block)]
        assert len(q) == 1, (variant, region, tracer, day, block, len(q))
        return float(q[field].iloc[0])

    def hourly(self, region, tracer, day, hours, field="pct"):
        q = self.hp[(self.hp.region == region) & (self.hp.tracer == tracer) & (self.hp.day == day)
                    & self.hp.hour.isin(list(hours))]
        return q.set_index("hour")[field].reindex(list(hours))

    def placebo_range(self, region, block):
        q = self.pool[(self.pool.variant == "main") & (self.pool.region == region) & (self.pool.tracer == "PM25")
                      & (self.pool.block == block) & self.pool.day.isin(["Sun", "Mon", "Tue", "Wed"])]
        return float(q.pct.min()), float(q.pct.max())

    def event(self, event, unit, field="pct"):
        q = self.ev[(self.ev.event == event) & (self.ev.unit.astype(str) == str(unit))]
        assert len(q) == 1, (event, unit)
        return float(q[field].iloc[0])

    def event_hours(self, event):
        q = self.ev[(self.ev.event == event) & self.ev.unit.astype(str).str.isdigit()]
        return q.pct

    def event_station(self, event, station):
        q = self.evst[(self.evst.event == event) & (self.evst.station == station) & (self.evst.unit == "daily")]
        assert len(q) == 1, (event, station)
        return float(100 * (np.exp(q.b.iloc[0]) - 1))

    def eid(self, analysis, outcome="PM25", field=None):
        q = self.eidc[(self.eidc.analysis == analysis) & (self.eidc.outcome == outcome)]
        assert len(q) == 1, (analysis, outcome)
        f = field or ("b_pct" if outcome == "PM25" else "b")
        return float(q[f].iloc[0])

    def lk(self, analysis, outcome="PM25", field=None):
        q = self.lock[(self.lock.analysis == analysis) & (self.lock.outcome == outcome)]
        assert len(q) == 1, (analysis, outcome)
        f = field or ("b_pct" if outcome == "PM25" else "b")
        return float(q[f].iloc[0])

    def tracer_ev(self, shock, outcome, region, field):
        q = self.etr[(self.etr.shock == shock) & (self.etr.outcome == outcome) & (self.etr.region == region)]
        assert len(q) == 1, (shock, outcome, region)
        return float(q[field].iloc[0])

    def traj(self, group, rels):
        q = self.etraj[(self.etraj.group == group) & self.etraj.rel.isin(list(rels))]
        return q.set_index("rel").pct

    def recon(self, region, season, field, scale="log"):
        q = self.rec[(self.rec.region == region) & (self.rec.season == season) & (self.rec.scale == scale)]
        assert len(q) == 1, (region, season, scale)
        return float(q[field].iloc[0])

    def decomp(self, region, field, season="all", scale="log"):
        q = self.dec[(self.dec.region == region) & (self.dec.season == season) & (self.dec.scale == scale)]
        assert len(q) == 1, (region, season, scale)
        return float(q[field].iloc[0])

    def hours(self, region, tracer, day, band="sim"):
        """Clock hours at which the bootstrap interval excludes zero: band 'sim' (simultaneous)
        or 'pw' (pointwise)."""
        q = self.hb[(self.hb.region == region) & (self.hb.tracer == tracer) & (self.hb.day == day)]
        lo, hi = ("sim_lo", "sim_hi") if band == "sim" else ("lo", "hi")
        return sorted(int(h) for h, a, b in zip(q.hour, q[lo], q[hi]) if b < 0 or a > 0)

    def capped(self, shock, version, field):
        q = self.cap[(self.cap.shock == shock) & (self.cap.version == version)]
        assert len(q) == 1, (shock, version)
        return float(q[field].iloc[0])

    def mechanism(self, test, region, block, field="est"):
        q = self.mech[(self.mech.test == test) & (self.mech.region == region) & (self.mech.block == block)]
        assert len(q) == 1, (test, region, block)
        return float(q[field].iloc[0])

    def blh_exact(self, season, hours):
        """Median ERA5 boundary-layer height over all hours of a block and season, 2019-2025,
        recomputed from the raw file exactly as blh_weighting.py prints it."""
        if not hasattr(self, "_met"):
            m = pd.read_csv(os.path.join(ROOT, "02_data", "raw", "meteo_dhaka_hourly_filled.csv"),
                            parse_dates=["time"])
            m = m[(m.time >= "2019-01-01") & (m.time < "2026-01-01")]
            seas = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Pre-monsoon", 4: "Pre-monsoon",
                    5: "Pre-monsoon", 6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
                    10: "Post-monsoon", 11: "Post-monsoon"}
            m["season"] = m.time.dt.month.map(seas)
            m["hour"] = m.time.dt.hour
            self._met = m
        m = self._met
        return float(m[(m.season == season) & m.hour.isin(list(hours))].boundary_layer_height.median())

    def block_share(self, season, block_hours):
        q = self.share[(self.share.season == season) & self.share.hour.isin(list(block_hours))]
        return 100 * float(q.share.sum())

    def weighting(self, variant, region, field):
        q = self.wcheck[(self.wcheck.variant == variant) & (self.wcheck.region == region)]
        return float(q[field].iloc[0])


# ------------------------------------------------------------------ expected values
# Each value is one of:
#   number                 compared at the printed precision (half-up)
#   ("abs", number)        compared as a magnitude (the text says "x percent lower")
#   ("about", number, tol) compared within an absolute tolerance (no longer used: every
#                          number in the manuscript is printed exactly)
#   ("range", lo, hi)      a printed "a--b" range
#   ("bound_above", x)     the printed number is an upper bound ("q < 0.001")
def claims(r):
    """The amber numbers of manuscript.tex, in the order they appear."""
    A = lambda v: ("abs", v)
    C = []

    def add(name, anchor, values):
        C.append((name, anchor, values))

    le, lp, lim = r.le, r.lp, r.lim
    eid = lambda o, f="b_pct": le("all", o, f)
    traj = r.ltraj
    ev = r.levents()

    # ---------------------------------------------------------------- abstract
    add("abstract", "We use the occasions on which the city emptied",
        [int(eid("PM25", "n_events")), A(eid("TROPOMI")), A(eid("PM25")), A(eid("PM25", "hi_boot_pct")),
         A(eid("PM25", "lo_boot_pct")), A(eid("PM25_ugm3", "b")),
         A(lp("2020 general holiday", "PM25", "b_pct")), A(lp("2023-24 blockade programme", "PM25", "b_pct")),
         lim("observed", "mean"), lim("eid", "mean"), lim("eid", "share_djf_above_65")])

    # ---------------------------------------------------------------- introduction
    add("Embassy level (Introduction)", "At the United States Embassy monitor in Dhaka, daily",
        [lim("observed", "mean"), lim("observed", "mean") / 35.0, lim("observed", "share_above_65"),
         lim("observed", "djf_mean"), lim("observed", "share_djf_above_65")])

    # ---------------------------------------------------------------- data and methods
    r16 = r.lsc[(r.lsc.period == "2016-2018") & r.lsc.station.isin(["BARC", "Darussalam", "Gazipur", "Narayanganj"])]
    add("agreement 2016-2018", "Gazipur and Narayanganj correlated with the Embassy",
        [("range", r16.r_log.min(), r16.r_log.max())])
    add("usable Eids (Methods)", "two days before a strict lockdown began. That leaves",
        [int(eid("PM25", "n_events"))])

    # ---------------------------------------------------------------- results: activity
    nox04 = [traj("NOX", d) for d in range(0, 5)]
    add("Eid activity", "Over days $-1$ to $+3$ the",
        [A(eid("TROPOMI")), A(eid("TROPOMI", "hi_boot_pct")), A(eid("TROPOMI", "lo_boot_pct")),
         int(eid("TROPOMI", "n_events")), A(eid("NOX")), A(eid("NOX", "hi_boot_pct")), A(eid("NOX", "lo_boot_pct")),
         int(eid("NOX", "k")), int(eid("NOX", "n_events")), A(max(nox04)), A(min(nox04)),
         eid("CO"), eid("CO", "lo_boot_pct"), eid("CO", "hi_boot_pct")])
    add("episode activity", "The pandemic general holiday of 2020 also reduced activity",
        [A(lp("2020 general holiday", "TROPOMI", "b_pct")), A(r.lmob("2020 general holiday", "workplaces")),
         A(r.lmob("2020 general holiday", "transit")),
         A(lp("2023-24 blockade programme", "TROPOMI", "b_pct")),
         A(lp("2023-24 blockade programme", "TROPOMI", "hi_cal_pct")),
         A(lp("2023-24 blockade programme", "TROPOMI", "lo_cal_pct")),
         lp("2021 strict lockdowns", "TROPOMI", "b_pct"), lp("2021 strict lockdowns", "TROPOMI", "lo_pct"),
         lp("2021 strict lockdowns", "TROPOMI", "hi_pct"), A(r.lmob("2021 strict lockdowns", "workplaces")),
         lp("2013-14 pre-election blockades", "NOX", "b_pct"), lp("2015 nationwide blockade", "NOX", "b_pct")])

    # ---------------------------------------------------------------- results: Eid
    core = [traj("PM25", d) for d in range(0, 4)]
    late = [traj("PM25", d) for d in range(4, 10)]
    add("Eid PM2.5", r"falls when the city empties}\label{sec:eid}",
        [int(eid("PM25", "n_events")), A(eid("PM25")), A(eid("PM25", "hi_boot_pct")), A(eid("PM25", "lo_boot_pct")),
         int(eid("PM25", "k")), A(eid("PM25_ugm3", "b")), A(eid("PM25_ugm3", "hi_boot")), A(eid("PM25_ugm3", "lo_boot")),
         A(eid("AQI", "b")), A(eid("AQI", "hi_boot")), A(eid("AQI", "lo_boot")),
         A(max(core)), A(min(core)), A(max(late)), A(min(late)),
         A(le("comp_clean", "PM25", "b_pct")), A(le("comp_clean", "PM25", "hi_pct")), A(le("comp_clean", "PM25", "lo_pct"))])
    add("Eid figure caption", "the shaded band marks days", [int(eid("PM25", "n_events"))])
    loo = r.le_rows("loo_", "PM25").b_pct
    add("Eid consistency", r"Table~\ref{S-tab:s-long-eid}).",
        [int((ev < 0).sum()), len(ev), A(loo.max()), A(loo.min()),
         A(le("fitr", "PM25", "b_pct")), A(le("adha", "PM25", "b_pct")),
         A(le("monsoon", "PM25", "b_pct")), int(le("monsoon", "PM25", "n_events")),
         A(le("other_months", "PM25", "b_pct")), int(le("other_months", "PM25", "n_events")),
         A(le("2013_2018", "PM25", "b_pct")), A(le("2019_2024", "PM25", "b_pct"))])

    # ---------------------------------------------------------------- results: disruptions
    H, B = "2020 general holiday", "2023-24 blockade programme"
    add("episodes", "During the 2020 general holiday",
        [A(lp(H, "PM25", "b_pct")), A(lp(H, "PM25", "hi_cal_pct")), A(lp(H, "PM25", "lo_cal_pct")),
         A(lp(B, "PM25", "b_pct")), A(lp(B, "PM25", "hi_cal_pct")), A(lp(B, "PM25", "lo_cal_pct")),
         A(lp(B, "PM25_ugm3", "b")), A(lp(B, "PM25_ugm3", "hi_cal")), A(lp(B, "PM25_ugm3", "lo_cal")),
         A(lp(B, "AQI", "b")),
         lp("2021 strict lockdowns", "PM25", "b_pct"), lp("2024 uprising and curfew", "PM25", "b_pct"),
         lp("2013-14 pre-election blockades", "PM25", "b_pct"), lp("2013-14 pre-election blockades", "PM25", "lo_cal_pct"),
         lp("2013-14 pre-election blockades", "PM25", "hi_cal_pct"),
         lp("2015 nationwide blockade", "PM25", "b_pct"), lp("2015 nationwide blockade", "PM25", "lo_cal_pct"),
         lp("2015 nationwide blockade", "PM25", "hi_cal_pct"), int(lp("2015 nationwide blockade", "PM25", "n_days")),
         A(lp("2018 road-safety protests", "PM25", "b_pct")), A(lp("2018 road-safety protests", "PM25", "lo_cal_pct")),
         A(lp("2018 road-safety protests", "PM25", "hi_cal_pct"))])
    add("placebo spread", "Three features of these estimates limit what they can show.",
        [r.lplac.min(), r.lplac.max(), len(r.lplac), int((r.lplac.abs() > 20).sum())])

    # ---------------------------------------------------------------- results: weekly (Part B of the supplement)
    EVE, AFT = "evening 18-23", "afternoon 12-17"
    add("weekly", "On Fridays in 2019--2024, activity at the Dhaka-region monitors",
        [A(r.boot("Dhaka", "PM25", EVE)), A(r.boot("Dhaka", "PM25", EVE, field="hi_pct")),
         A(r.boot("Dhaka", "PM25", EVE, field="lo_pct")),
         A(r.boot("Dhaka", "PM25", AFT)), A(r.boot("Dhaka", "PM25", AFT, field="hi_pct")),
         A(r.boot("Dhaka", "PM25", AFT, field="lo_pct"))]
        + [r.boot("Dhaka", "PM25", "daily", field=f) for f in ("pct", "lo_pct", "hi_pct")])

    # ---------------------------------------------------------------- results: ceiling
    add("ceiling", "If every day from March 2016 to December 2024 had been as quiet as at Eid",
        [lim("eid", "mean"), lim("eid_lo", "mean"), lim("eid_hi", "mean"), lim("observed", "mean"),
         lim("eid", "mean") / 35.0, lim("eid", "reduction"), lim("eid_hi", "reduction"), lim("eid_lo", "reduction"),
         lim("eid", "gap_closed_pct"), lim("observed", "djf_mean"), lim("eid", "djf_mean"),
         lim("eid", "share_djf_above_65"), lim("observed", "share_djf_above_65"),
         lim("observed", "share_above_65"), lim("eid", "share_above_65"),
         lim("observed", "share_aqi_above_200"), lim("eid", "share_aqi_above_200"),
         lim("holiday_2020", "mean"), lim("eid", "good_moderate_days_gain")])

    # ---------------------------------------------------------------- policy
    add("policy: winter day", "Eid-scale shutdown would leave about", [lim("eid", "djf_mean")])
    add("policy: target", "permanently as quiet as at Eid would lower the Embassy mean by about",
        [lim("eid", "reduction")])
    add("policy: indicators", "An Eid-scale reduction every day would add about",
        [lim("eid", "good_moderate_days_gain"), lim("eid", "share_djf_above_65")])
    add("policy table", r"Section~3.4, action 1.11) & Eid lowered daily",
        [A(eid("PM25")), A(lp(H, "PM25", "b_pct")), lim("eid", "djf_mean"), lim("eid", "reduction"),
         lim("eid_hi", "reduction"), lim("eid_lo", "reduction"), lim("eid", "share_djf_above_65"),
         lim("eid", "good_moderate_days_gain")])

    # ---------------------------------------------------------------- limitations and conclusions
    add("limitations", "the placebo spread\nmeasures. Only",
        [int(le("other_months", "PM25", "n_events")), int(eid("PM25", "n_events"))])
    add("conclusions", "When Dhaka empties at Eid, its",
        [A(eid("PM25")), A(eid("PM25_ugm3", "b"))])
    return C


def supp_claims(r):
    """Claims for the numbers in supplementary.tex prose (its tables are generated)."""
    C = []
    add = lambda name, anchor, values: C.append((name, anchor, values))
    rep = csv("cams_parse_report.csv")
    f12 = rep[rep.file.str.contains("2012") & rep.station.notna()].set_index("station").dropped_no_date
    tot = int(rep[rep.file.str.contains("2012") & rep.station.isna()].dropped_no_date.iloc[0])
    six = ["Rajshahi", "Khulna", "Sangsad", "Rangpur", "Narsingdi", "Barishal"]
    add("S1 dropped blocks", "in time and were dropped:",
        [int(f12[s]) for s in six] + [tot - int(sum(f12[s] for s in six)), tot])
    q = pd.read_csv(os.path.join(HERE, "..", "data", "cams_hourly_qc.csv.gz"),
                    usecols=["station", "time", "PM25"], parse_dates=["time"])
    q19 = q[q.time >= "2019-01-01"]
    daily = q19.assign(date=q19.time.dt.normalize()).groupby(["station", "date"]).PM25.mean().unstack(0)
    dh = ["BARC", "Darussalam", "DoE", "Savar", "Gazipur", "Narayanganj", "Narsingdi"]
    dmed = float(np.median([daily[s].median() for s in dh]))
    btv = float(daily["BTV Chattogram"].median())
    add("S3 BTV level", "The host\nlisting settles its identity", [btv, btv / dmed, dmed])
    cv = pd.read_csv(os.path.join(ROOT, "06_results", "metrics", "blh_gapfill_cv.csv"))
    met = pd.read_csv(os.path.join(ROOT, "02_data", "raw", "meteo_dhaka_hourly_filled.csv"),
                      usecols=["blh_filled"])
    add("S BLH gap fill", r"Boundary-layer gap fill}\label{sec:s-gapfill}",
        [int(met.blh_filled.sum()), len(cv), cv.r2.mean(), cv.rmse.mean(), cv.bias.mean(),
         r.gap.loc["hours 00-05", "rmse"], r.gap.loc["observed < 200 m", "rmse"], r.gap.loc["observed < 200 m", "bias"]])
    return C


HIGHLIGHT_LINES = 5


def highlight_values(r):
    """The numbers each line of highlights.txt must carry, in order (years included)."""
    return [[-r.le("all", "PM25", "b_pct"), int(r.le("all", "PM25", "n_events")), 2013, 2024],
            [2020, 2023, 24, -r.lp("2020 general holiday", "PM25", "b_pct"),
             -r.lp("2023-24 blockade programme", "PM25", "b_pct")],
            [],
            [r.lim("eid", "share_djf_above_65"), 24],
            []]


# ------------------------------------------------------------------ comparison
def compare(expected, kind, vals, decs):
    if isinstance(expected, tuple):
        tag = expected[0]
        if tag == "abs":
            e = [abs(expected[1])]
            return kind == "num" and close(e[0], abs(vals[0]), decs[0]), e
        if tag == "about":
            return kind == "num" and abs(abs(expected[1]) - abs(vals[0])) <= expected[2] + 1e-9 and \
                np.sign(expected[1]) * np.sign(vals[0]) >= 0 or (kind == "num" and abs(expected[1] - vals[0]) <= expected[2] + 1e-9), [expected[1]]
        if tag == "range":
            ok = kind == "range" and close(expected[1], vals[0], decs[0]) and close(expected[2], vals[1], decs[1])
            return ok, [expected[1], expected[2]]
        if tag == "all":            # one printed number standing for several derived ones
            res = [compare(x, kind, vals, decs)[0] for x in expected[1]]
            return all(res), [x[1] if isinstance(x, tuple) else x for x in expected[1]]
        if tag == "bound_above":    # printed number is an upper bound ("stays below 400")
            return kind == "num" and vals[0] >= expected[1], [expected[1]]
        if tag == "rangeabout":
            ok = kind == "range" and abs(expected[1] - vals[0]) <= expected[3] + 0.5 * 10 ** -decs[0] + 1e-9 and \
                abs(expected[2] - vals[1]) <= expected[3] + 0.5 * 10 ** -decs[1] + 1e-9
            return ok, [expected[1], expected[2]]
        raise ValueError(tag)
    return kind == "num" and close(float(expected), vals[0], decs[0]), [float(expected)]


def refmt(raw, exp, kind, decs):
    """The derived value written in the printed number's style, or None when a person must
    rewrite the sentence (one printed number standing for several values, or a bound)."""
    tag = exp[0] if isinstance(exp, tuple) else "exact"
    if tag in ("all", "bound_above"):
        return None
    math = "$" in raw
    comma = "," in raw

    def one(v, d, part):
        signed = part.strip("$").strip()[:1] in "+-"
        s = ("%+." if signed else "%.") + str(d) + "f"
        v = round_half_up(v, d)
        txt = s % v
        if txt in ("-0", "+0") or txt.startswith(("-0.0", "+0.0")) and float(txt) == 0:
            txt = txt.replace("-", "+")
        if comma:
            ip, _, fp = txt.lstrip("+-").partition(".")
            txt = (txt[0] if txt[0] in "+-" else "") + "{:,}".format(int(ip)) + ("." + fp if fp else "")
        return txt

    if tag == "range" or tag == "rangeabout":
        parts = raw.replace("$", "").split("--")
        a = one(exp[1], decs[0], parts[0])
        b = one(exp[2], decs[1], parts[1])
        return ("$%s$--$%s$" % (a, b)) if math else "%s--%s" % (a, b)
    v = abs(exp[1]) if tag == "abs" else (exp[1] if tag == "about" else float(exp))
    if tag == "about" and not raw.replace("$", "").strip()[:1] in "+-":
        v = abs(v)
    txt = one(v, decs[0], raw)
    return "$%s$" % txt if math else txt


def close(expected, printed, d):
    return abs(round_half_up(expected, d) - printed) < 1e-9 or abs(expected - printed) <= 0.5 * 10 ** -d + 1e-9


def main():
    text = open(TEX, encoding="utf-8").read()
    items = amber(text)
    if "--inventory" in sys.argv:
        for i, (pos, raw) in enumerate(items):
            line = text.count("\n", 0, pos) + 1
            ctx = re.sub(r"\s+", " ", text[max(0, pos - 60):pos])
            print("%3d  L%-4d %-16s ...%s" % (i, line, raw, ctx[-60:]))
        return 0
    r = R()
    used, kinds, fixes = {}, {}, []
    fails, ok_n = [], 0
    for name, anchor, values in claims(r):
        pat = r"\s+".join(re.escape(w) for w in anchor.split())
        hits = [m.start() for m in re.finditer(pat, text)]
        if len(hits) != 1:
            fails.append("ANCHOR  %-40s anchor found %d times: %r" % (name, len(hits), anchor[:50]))
            continue
        after = [k for k, (pos, _) in enumerate(items) if pos > hits[0]][:len(values)]
        if len(after) < len(values):
            fails.append("ANCHOR  %-40s fewer amber numbers after anchor than claimed" % name)
            continue
        for j, (k, exp) in enumerate(zip(after, values)):
            used.setdefault(k, []).append(name)
            pos, raw = items[k]
            try:
                kind, vals, decs = parse_printed(raw)
            except ValueError:
                fails.append("PARSE   %-40s #%d cannot parse %r" % (name, j, raw))
                continue
            ok, e = compare(exp, kind, vals, decs)
            tag = exp[0] if isinstance(exp, tuple) else "exact"
            kinds[{"abs": "exact", "range": "exact", "all": "exact"}.get(tag, tag)] = \
                kinds.get({"abs": "exact", "range": "exact", "all": "exact"}.get(tag, tag), 0) + 1
            if ok:
                ok_n += 1
            else:
                line = text.count("\n", 0, pos) + 1
                fails.append("MISMATCH %-39s #%-2d L%-4d printed %-12s derived %s" %
                             (name, j, line, raw, ", ".join("%.4g" % x for x in e)))
                new = refmt(raw, exp, kind, decs)
                if new is not None:
                    fixes.append((pos, raw, new, line, name))
    # the highlights file carries no \pn{} marks: check its numbers line by line
    hl_path = HIGHLIGHTS
    if os.path.exists(hl_path):
        want = highlight_values(r)
        lines = open(hl_path, encoding="utf-8").read().splitlines()
        for i, (line, exp) in enumerate(zip(lines, want)):
            nums = re.findall(r"\d+\.\d+|\d+", line.replace("PM2.5", ""))
            ok = len(nums) == len(exp) and all(close(e, float(n), dec(n)) for e, n in zip(exp, nums))
            if not ok:
                fails.append("HIGHLIGHT line %d: printed %s, derived %s" %
                             (i + 1, nums, ", ".join("%.4g" % e for e in exp)))
        if len(lines) > HIGHLIGHT_LINES or any(len(x) > 85 for x in lines):
            fails.append("HIGHLIGHT more than 5 lines or a line over 85 characters")
    # the supplement: same rules, its own claims
    supp_path = os.path.join(os.path.dirname(TEX), "supplementary.tex")
    n_supp = ok_supp = 0
    if os.path.exists(supp_path):
        st = open(supp_path, encoding="utf-8").read()
        sitems = amber(st)
        n_supp = len(sitems)
        sused = set()
        for name, anchor, values in supp_claims(r):
            pat = r"\s+".join(re.escape(w) for w in anchor.split())
            hits = [m.start() for m in re.finditer(pat, st)]
            if len(hits) != 1:
                fails.append("SUPP ANCHOR %-36s anchor found %d times" % (name, len(hits)))
                continue
            after = [k for k, (pos, _) in enumerate(sitems) if pos > hits[0]][:len(values)]
            for j, (k, exp) in enumerate(zip(after, values)):
                sused.add(k)
                pos, raw = sitems[k]
                kind, vals, decs = parse_printed(raw)
                ok, e = compare(exp, kind, vals, decs)
                if ok:
                    ok_supp += 1
                else:
                    fails.append("SUPP MISMATCH %-34s #%-2d L%-4d printed %-10s derived %s" %
                                 (name, j, st.count("\n", 0, pos) + 1, raw, ", ".join("%.4g" % x for x in e)))
        for k in range(n_supp):
            if k not in sused:
                pos, raw = sitems[k]
                fails.append("SUPP UNCOVERED L%-4d %s" % (st.count("\n", 0, pos) + 1, raw))
    uncovered = [k for k in range(len(items)) if k not in used]
    double = [k for k, v in used.items() if len(v) > 1]
    for k in uncovered:
        pos, raw = items[k]
        ctx = re.sub(r"\s+", " ", text[max(0, pos - 50):pos])
        fails.append("UNCOVERED L%-4d %-14s ...%s" % (text.count("\n", 0, pos) + 1, raw, ctx[-50:]))
    for k in double:
        fails.append("DOUBLE   amber #%d claimed by %s" % (k, used[k]))
    for f in fails:
        print(f)
    if "--fix" in sys.argv and fixes:
        # Rewrite mismatched numbers in their printed style, last first so positions hold.
        # Only the number changes; the sentence around it is left for a person to reread.
        out = text
        for pos, raw, new, line, name in sorted(fixes, reverse=True):
            old = r"\pn{%s}" % raw
            assert out[pos:pos + len(old)] == old, (line, raw)
            out = out[:pos] + r"\pn{%s}" % new + out[pos + len(old):]
            print("FIXED    L%-4d %-12s -> %-12s (%s)" % (line, raw, new, name))
        open(TEX, "w", encoding="utf-8").write(out)
        print("%d numbers rewritten in %s; reread the sentences around them" % (len(fixes), TEX))
    print("\n%d of %d amber numbers verified; %d problems" % (ok_n, len(items), len(fails)))
    if n_supp:
        print("supplement: %d of %d checked numbers verified" % (ok_supp, n_supp))
    print("checks by type: %s  (exact = equal at the printed precision, half-up; about = within a "
          "stated tolerance, used for numbers the text gives as 'about'; bound_above = printed upper "
          "bound)" % ", ".join("%s %d" % kv for kv in sorted(kinds.items())))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
