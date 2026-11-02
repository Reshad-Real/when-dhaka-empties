"""Write the data-bearing manuscript tables as LaTeX, straight from the result files, so no
number in them is transcribed by hand.

  paper/working/tables/tab_effects.tex     Table 3, from out/table3.csv
  paper/working/tables/tab_scenarios.tex   Table 6, from out/aqi_scenarios.csv and
                                   out/aqi_scenarios_stations.csv
  paper/working/tables/tab_stations.tex    Table 2, stations and PM2.5 coverage by year
  paper/working/tables/tab_sensitivity.tex Table 5, robustness of the Dhaka Friday contrast
  paper/working/tables/tab_screening.tex   Table S2, from out/cams_validation.csv
Usage: python -I make_paper_tables.py
"""
import os

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "out")
TAB = os.path.join(HERE, "..", "paper", "working", "tables")
NUM = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
os.makedirs(TAB, exist_ok=True)


def tex(s):
    return str(s).replace("−", "$-$").replace("+", "$+$").replace("%", r"\%")


def num(v, nd=1, sign=True):
    s = ("%+." + str(nd) + "f") % v if sign else ("%." + str(nd) + "f") % v
    return s.replace("-", "$-$").replace("+", "$+$") if sign else s


def effects():
    T = pd.read_csv(os.path.join(OUT, "table3.csv"))
    T = T[T.shock.isin(["Friday", "Saturday"])]      # Part B of the supplement: the weekly design only
    units = ["night 00-05", "morning 06-11", "afternoon 12-17", "evening 18-23", "daily"]
    lines = [r"\begin{longtable}{L{1.4cm} L{1.3cm} L{1.0cm} C{1.8cm} C{1.8cm} C{1.8cm} C{1.8cm} C{1.8cm} C{1.8cm}}",
             r"\caption{Weekly rest day, 2019--2024: Pooled contrasts by diurnal block, percent (95\% interval), "
             r"and the change in the daily PM$_{2.5}$ AQI sub-index in index points. Friday and Saturday "
             r"against the same block on Sunday to Wednesday, joint-date moving-block bootstrap (14-day "
             r"blocks, 400 replicates). The night block is 00--05\,h of the calendar day, so a Friday's "
             r"night block is Thursday night."
             r"}\label{tab:effects}\\",
             r"\toprule",
             r"\textbf{Shock} & \textbf{Region} & \textbf{Tracer} & \textbf{Night} & \textbf{Morning} & "
             r"\textbf{Afternoon} & \textbf{Evening} & \textbf{Daily} & \textbf{AQI (points)} \\",
             r"\midrule\endfirsthead",
             r"\toprule",
             r"\textbf{Shock} & \textbf{Region} & \textbf{Tracer} & \textbf{Night} & \textbf{Morning} & "
             r"\textbf{Afternoon} & \textbf{Evening} & \textbf{Daily} & \textbf{AQI (points)} \\",
             r"\midrule\endhead",
             r"\bottomrule\endfoot"]
    for _, r in T.iterrows():
        lab = r.shock
        if r.shock == "Lockdown":
            lab += r"\newline {\scriptsize(%s)}" % ("model" if "model interval" in r.interval else "placebo-based")
        cells = [lab, r.region.replace("national", "National"),
                 {"PM2.5": r"PM$_{2.5}$", "NOx": r"NO$_x$"}.get(r.tracer, r.tracer)]
        cells += [tex(r[u]).replace(" [", r"\newline [") for u in units]
        a = r["daily AQI (points)"]
        cells.append(tex(a).replace(" [", r"\newline [") if isinstance(a, str) and a.strip() else "")
        lines.append(" & ".join(cells) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\footnotesize"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_effects.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def scenarios():
    S = pd.read_csv(os.path.join(OUT, "aqi_scenarios.csv")).set_index("scenario")
    St = pd.read_csv(os.path.join(OUT, "aqi_scenarios_stations.csv"))
    rng = St.groupby("scenario").d_mean_aqi.agg(["min", "max"])
    names = [("rest_day", "Every day takes the rest-day profile (Friday morning to evening, then the night after Friday)"),
             ("rest_day_calendar", "The same with the calendar-Friday profile (Thursday night included)"),
             ("cut_allday", "Friday-afternoon-sized concentration cut at all 24 hours"),
             ("cut_day_only", "The same cut at 12--23\\,h only"),
             ("cut_night_only", "The same cut at 00--11\\,h only")]
    b = S.loc["baseline"]
    hdr = (r"\textbf{Scenario} & \textbf{PM$_{2.5}$ (\%)} & \textbf{Sub-index (points)} & "
           r"\textbf{Days $>$150} & \textbf{Days $>$200} & \textbf{Days $>$300} & \textbf{CAMS range} \\")
    lines = [r"\begin{longtable}{L{4.4cm} C{1.7cm} C{1.9cm} C{1.6cm} C{1.6cm} C{1.6cm} C{2.0cm}}",
             r"\caption{Illustrative scenarios: Concentration reductions shaped like the observed weekly "
             r"pattern, applied to a working-day counterfactual of the US Embassy hourly record (Thursday, "
             r"Friday and Saturday hours converted to their Sunday--Wednesday equivalents; Eid, lockdown and "
             r"strike days left out), January 2019 to March 2025. Change in mean PM$_{2.5}$, in the mean daily "
             r"PM$_{2.5}$ AQI sub-index and in days per year above three category boundaries, with 95\% "
             r"intervals from the joint-date bootstrap draws of the block effects. These rescale "
             r"concentrations; they are not forecasts of a policy and not equivalent emissions cuts. "
             r"Baseline: Mean PM$_{2.5}$ " + num(b.mean_pm, 1, False) + r"\,$\mu$g\,m$^{-3}$, mean sub-index "
             + num(b.mean_aqi, 1, False) + r", and " + num(b.days150, 0, False) + r", " + num(b.days200, 0, False)
             + r" and " + num(b.days300, 0, False) + r" days per year above 150, 200 and 300. Last column: "
             r"Range of the sub-index change over the " + NUM[St.station.nunique()]
             + r" screened Dhaka CAMS stations, 2019--2024.}\label{tab:scenarios}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead",
             r"\bottomrule\endfoot"]

    def iv(r, col):
        return num(r[col]) + r"\newline {\scriptsize[%s, %s]}" % (num(r[col + "_lo"]), num(r[col + "_hi"]))
    for key, lab in names:
        r = S.loc[key]
        cams = ("%s to %s" % (num(rng.loc[key, "min"]), num(rng.loc[key, "max"]))) if key in rng.index else "--"
        lines.append(" & ".join([lab, iv(r, "d_pm_pct"), iv(r, "d_mean_aqi"), iv(r, "d_days150"),
                                 iv(r, "d_days200"), iv(r, "d_days300"), cams]) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_scenarios.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def stations():
    """Compact station table: region, host, PM2.5 coverage by year, and what each is used for."""
    import sys
    sys.path.insert(0, HERE)
    from cams_shocks import embassy_hourly
    from screens import gas_allowed, screens
    cov = pd.read_csv(os.path.join(OUT, "coverage_station_year.csv"))
    loc = pd.read_csv(os.path.join(HERE, "..", "data", "station_locations.csv")).set_index("station")
    ok_pm, gas_ok, flat = screens()
    dh = ["BARC", "Darussalam", "DoE", "Savar", "Gazipur", "Narayanganj", "Narsingdi"]
    emb = embassy_hourly(os.path.join(HERE, "..", ".."))
    emb = emb[(emb.time >= "2019-01-01") & (emb.time < "2025-01-01")].drop_duplicates("time")
    years = list(range(2019, 2025))
    hours = {y: (pd.Timestamp("%d-01-01" % (y + 1)) - pd.Timestamp("%d-01-01" % y)).days * 24 for y in years}
    ecov = emb.groupby(emb.time.dt.year).size()
    pos = lambda st: (r"%.3f\,N\newline %.3f\,E" % (loc.loc[st, "lat"], loc.loc[st, "lon"])) if st in loc.index else "--"
    rows = [["US Embassy", "Dhaka", loc.loc["US Embassy", "host"].split(",")[0], pos("US Embassy")]
            + ["%d" % round(100 * ecov.get(y, 0) / hours[y]) for y in years] + ["PM$_{2.5}$ (reference)"]]
    order = dh + sorted(s for s in cov.station.unique() if s not in dh)
    for st in order:
        c = cov[cov.station == st].set_index("year")
        reg = "Dhaka" if st in dh else "National"
        use = []
        if (reg == "National") or st in ok_pm:
            use.append("PM$_{2.5}$")
        for g, lab in (("NOX", "NO$_x$"), ("CO", "CO")):
            if gas_allowed(st, g, "Dhaka" if st in dh else "national", gas_ok, flat):
                use.append(lab)
        host = loc.loc[st, "host"].split(",")[0] if st in loc.index else ""
        rows.append([st, reg, host, pos(st)] + ["%d" % round(c.loc[y, "PM25"]) if y in c.index else "0" for y in years]
                    + [", ".join(use) if use else "none"])
    hdr = (r"\textbf{Station} & \textbf{Region} & \textbf{Host} & \textbf{Position} & "
           + " & ".join(r"\textbf{%d}" % y for y in years) + r" & \textbf{Used for} \\")
    lines = [r"\begin{longtable}{L{2.3cm} L{1.2cm} L{2.9cm} L{1.4cm} " + "C{0.6cm} " * 6 + r"L{2.2cm}}",
             r"\caption{Monitoring stations: Host institution, position (World Air Quality Index listing; the "
             r"US Embassy from OpenStreetMap), valid PM$_{2.5}$ hours by year (percent of the year, after quality "
             r"control) and the analyses each enters. No siting classification of the CAMS stations is "
             r"published. Dhaka-region PM$_{2.5}$ is screened against the US Embassy reference; gas analyzers are "
             r"screened against TROPOMI NO$_2$ in the Dhaka region and for faults everywhere "
             r"(Section~\ref{sec:screening}). Exclusions by rule, station and year are in "
             r"Table~\ref{S-tab:s-qc-station}; coverage of the gases in Table~\ref{S-tab:s-coverage-year}."
             r"}\label{tab:stations}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead", r"\bottomrule\endfoot"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\footnotesize"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_stations.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def sensitivity():
    """Main-paper summary of robustness and sensitivity for the Dhaka Friday PM2.5 contrast."""
    P = pd.read_csv(os.path.join(OUT, "robust_pooled.csv"))
    B = pd.read_csv(os.path.join(OUT, "robust_bootstrap_days.csv"))
    BL = pd.read_csv(os.path.join(OUT, "robust_bootstrap_blocklen.csv"))
    q = P[(P.region == "Dhaka") & (P.tracer == "PM25") & (P.day == "Fri")]
    blocks = ["afternoon 12-17", "evening 18-23", "daily"]

    def boot_row(lab, tab):
        g = tab.set_index("block")
        return [lab, str(int(g.k.max())) if "k" in g else "7"] + [
            num(g.loc[b, "pct"]) + r"\newline {\scriptsize[%s, %s]}" % (num(g.loc[b, "lo_pct"]), num(g.loc[b, "hi_pct"]))
            for b in blocks]

    rows = []
    fb = B[(B.day == "Fri") & (B.region == "Dhaka") & (B.tracer == "PM25")]
    rows.append(boot_row("Main, joint-date bootstrap (14-day blocks)", fb))
    for blen in (7, 28):
        rows.append(boot_row("Bootstrap, %d-day blocks" % blen,
                             BL[(BL.block_days == blen) & (BL.region == "Dhaka")]))
    labs = [("cluster", "Week-clustered errors"), ("nomet", "No meteorology"), ("y2019_21", "2019--2021 only"),
            ("y2022_25", "2022--2025 only"), ("dry", "Dry season (Nov--Apr)"), ("wet", "Wet season (May--Oct)"),
            ("no_imputed", "Without the gap-filled boundary-layer months"),
            ("no_pandemic", "Without 26 March 2020 -- December 2021 (pandemic restrictions)"),
            ("balanced", "Balanced dates ($\\geq$70\\% of stations)"), ("noembassy", "Without the Embassy"),
            ("screen_none", "No station screens"), ("screen_strict", "Stricter screens")]
    for v, lab in labs:
        g = q[q.variant == v].set_index("block")
        rows.append([lab, str(int(g.k.max()))] + ["%s {\\scriptsize($z$=%s)}" % (num(g.loc[b, "pct"]),
                                                                                  num(g.loc[b, "z"], 1))
                                                    for b in blocks])
    hdr = r"\textbf{Variant} & \textbf{$k$} & \textbf{Afternoon} & \textbf{Evening} & \textbf{Daily} \\"
    lines = [r"\begin{longtable}{L{6.0cm} C{0.6cm} C{2.6cm} C{2.6cm} C{2.6cm}}",
             r"\caption{Robustness of the Dhaka-region Friday PM$_{2.5}$ contrast, percent. Bootstrap rows: "
             r"95\% interval from 400 joint-date resamples with the block length shown. Other rows: "
             r"Random-effects pooling, $z$-statistic in parentheses. $k$: Stations. The full set, with the "
             r"national stations and each station left out, is in Table~\ref{tab:s-robust}; the gases under "
             r"each screen in Table~\ref{tab:s-gas-screens}.}\label{tab:sensitivity}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead", r"\bottomrule\endfoot"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_sensitivity.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def screening():
    V = pd.read_csv(os.path.join(OUT, "cams_validation.csv"))
    lines = [r"\begin{longtable}{L{2.2cm} C{1.8cm} C{1.6cm} C{1.4cm} C{1.4cm} C{1.6cm} C{1.6cm} C{2.4cm}}",
             r"\caption{Screening of the Dhaka-region CAMS stations. Daily PM$_{2.5}$ correlation "
             r"(log) and median ratio with the US Embassy monitor over the overlapping days; the lag in "
             r"hours at which hourly PM$_{2.5}$ correlates best with the Embassy record; and the "
             r"deseasonalized daily Spearman correlation of each gas analyzer with TROPOMI NO$_2$. "
             r"Inclusion rules: PM$_{2.5}$ correlation $\geq$0.6 and best lag within one hour; a gas "
             r"correlation $\geq$0.2.}\label{tab:screening}\\",
             r"\toprule",
             r"\textbf{Station} & \textbf{Record} & \textbf{$r$ with Embassy} & \textbf{Ratio} & "
             r"\textbf{Best lag (h)} & \textbf{NO$_x$ vs TROPOMI} & \textbf{CO vs TROPOMI} & \textbf{Used for} \\",
             r"\midrule\endfirsthead",
             r"\toprule",
             r"\textbf{Station} & \textbf{Record} & \textbf{$r$ with Embassy} & \textbf{Ratio} & "
             r"\textbf{Best lag (h)} & \textbf{NO$_x$ vs TROPOMI} & \textbf{CO vs TROPOMI} & \textbf{Used for} \\",
             r"\midrule\endhead",
             r"\bottomrule\endfoot"]
    for _, r in V.iterrows():
        use = []
        if r.daily_r_embassy >= 0.6 and abs(r.best_lag_h) <= 1:
            use.append("PM$_{2.5}$")
        if r.NOX_rho_tropomi >= 0.2:
            use.append("NO$_x$")
        if r.CO_rho_tropomi >= 0.2:
            use.append("CO")
        lines.append(" & ".join([r.station, "%s--%s" % (str(r["first"])[:4], str(r["last"])[:4]),
                                 "%.2f" % r.daily_r_embassy, "%.2f" % r.ratio_to_embassy,
                                 "%+d" % r.best_lag_h, num(r.NOX_rho_tropomi, 2), num(r.CO_rho_tropomi, 2),
                                 ", ".join(use) if use else "none"]) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_screening.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


# ----------------------------------------------------------------------------- the long record
HOSTS = {"BARC": "Bangladesh Agricultural Research Council, Farmgate",
         "Darussalam": "National Institute of Mass Communication, Darus Salam",
         "DoE": "DoE headquarters, Agargaon",
         "Gazipur": "Gazipur", "Narayanganj": "Narayanganj", "Narsingdi": "Narsingdi",
         "US Embassy": "US Embassy, Baridhara (reference monitor)"}
EPISODES = ["2013-14 pre-election blockades", "2015 nationwide blockade", "2018 road-safety protests",
            "2020 general holiday", "2021 strict lockdowns", "2023-24 blockade programme",
            "2024 uprising and curfew"]
EP_LABEL = {"2013-14 pre-election blockades": "Pre-election blockades, 26 Nov 2013 -- 5 Jan 2014",
            "2015 nationwide blockade": "Nationwide blockade, 6 Jan -- 5 Apr 2015",
            "2018 road-safety protests": "Road-safety protests, 29 Jul -- 8 Aug 2018",
            "2020 general holiday": "Pandemic general holiday, 26 Mar -- 30 May 2020",
            "2021 strict lockdowns": "Strict lockdowns, 14 Apr -- 10 Aug 2021 (three spells)",
            "2023-24 blockade programme": "Blockade and hartal days, 29 Oct 2023 -- 8 Jan 2024",
            "2024 uprising and curfew": "Shutdown, curfew and holidays, 18 Jul -- 5 Aug 2024"}


def ivl(lo, hi, nd=1):
    return r"{\scriptsize[%s, %s]}" % (num(lo, nd), num(hi, nd))


def long_stations():
    C = pd.read_csv(os.path.join(OUT, "long_station_check.csv"))
    allr = C[C.period == "all"].set_index("station")
    r16 = C[C.period == "2016-2018"].set_index("station").r_log
    r19 = C[C.period == "2019-2024"].set_index("station").r_log
    hdr = (r"\textbf{Station} & \textbf{Host or location} & \textbf{Daily means (period)} & "
           r"\textbf{$r$, 2016--2018} & \textbf{$r$, 2019--2024} & \textbf{Gas tracers} \\")
    lines = [r"\begin{longtable}{L{2.0cm} L{4.6cm} L{3.0cm} C{1.6cm} C{1.6cm} L{1.7cm}}",
             r"\caption{PM$_{2.5}$ monitors of the long record. Daily means need at least 18 valid hours. "
             r"$r$: Correlation of daily log PM$_{2.5}$ with the US Embassy monitor. Gas tracers: The "
             r"station's NO$_x$ and CO analyzers that pass the screens of Section~\ref{sec:screen}; the "
             r"NO$_x$ analyzer at Savar, whose PM$_{2.5}$ timing fails the screen, is also used.}"
             r"\label{tab:stations}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead",
             r"\bottomrule\endfoot"]
    order = ["US Embassy", "BARC", "Darussalam", "Gazipur", "Narayanganj", "DoE", "Narsingdi"]
    for st in order:
        a = allr.loc[st]
        per = "%s (%s--%s)" % ("{:,}".format(int(a.n_days)), str(a["first"])[:4], str(a["last"])[:4])
        gases = a.gases if isinstance(a.gases, str) else ""
        lines.append(" & ".join([st, HOSTS[st], per,
                                 ("%.2f" % r16[st]) if st in r16 else "--",
                                 ("%.2f" % r19[st]) if st in r19 else "--",
                                 gases.replace("NOX", "NO$_x$").replace(";", ", ") or "--"]) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_long_stations.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def shocks():
    L = pd.read_csv(os.path.join(OUT, "long_eid.csv"))
    P = pd.read_csv(os.path.join(OUT, "long_episodes.csv"))
    M = pd.read_csv(os.path.join(OUT, "long_episode_mobility.csv")).set_index("episode")
    e = lambda o: L[(L.analysis == "all") & (L.outcome == o)].iloc[0]
    hdr = (r"\textbf{Event} & \textbf{Days} & \textbf{$k$} & \textbf{PM$_{2.5}$ (\%)} & "
           r"\textbf{PM$_{2.5}$ ($\mu$g\,m$^{-3}$)} & \textbf{AQI (points)} & \textbf{Activity check (\%)} \\")
    lines = [r"\begin{longtable}{L{4.3cm} C{0.9cm} C{0.4cm} C{2.3cm} C{2.0cm} C{2.0cm} L{3.0cm}}",
             r"\caption{Change in daily PM$_{2.5}$, in concentration and in the daily PM$_{2.5}$ AQI "
             r"sub-index, during Eid and each prolonged disruption, pooled over the Dhaka-region monitors "
             r"($k$ stations), with the activity change measured independently. Eid: Days $-$1 to +3 of the "
             r"usable Eids against days $-$15 to +18, with 95\% intervals from resampling the events. "
             r"Disruptions: Against the year, calendar-month, day-of-week and weather expectation; first the "
             r"95\% model interval, then (second line) the interval with the spread of placebo estimates "
             r"for the same calendar days in other years added, which also reflects counterfactual "
             r"uncertainty; the concentration and AQI columns give that second interval. Days: Event days "
             r"(for Eid, events). Activity check: TROPOMI tropospheric NO$_2$ column (from 2019), surface "
             r"NO$_x$ (CAMS analyzers) and, for 2020 and 2021, Google workplace mobility against "
             r"Google's early-2020 baseline.}\label{tab:shocks}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead",
             r"\bottomrule\endfoot"]
    pm, ug, aq, nx, tr = e("PM25"), e("PM25_ugm3"), e("AQI"), e("NOX"), e("TROPOMI")
    lines.append(" & ".join([
        r"Eid holidays, 2013--2024", str(int(pm.n_events)), str(int(pm.k)),
        num(pm.b_pct) + r"\newline " + ivl(pm.lo_boot_pct, pm.hi_boot_pct),
        num(ug.b) + r"\newline " + ivl(ug.lo_boot, ug.hi_boot),
        num(aq.b) + r"\newline " + ivl(aq.lo_boot, aq.hi_boot),
        r"NO$_2$ column " + num(tr.b_pct) + r"\newline NO$_x$ " + num(nx.b_pct)]) + r" \\")
    for ep in EPISODES:
        q = P[P.episode == ep].set_index("outcome")
        p = q.loc["PM25"]
        cal = (r"\newline " + ivl(p.lo_cal_pct, p.hi_cal_pct)) if pd.notna(p.lo_cal_pct) else ""
        act = []
        if "TROPOMI" in q.index:
            act.append(r"NO$_2$ column " + num(q.loc["TROPOMI", "b_pct"]))
        if "NOX" in q.index and min(pd.Timestamp(p.start).year, 2019) < 2019:
            act.append(r"NO$_x$ " + num(q.loc["NOX", "b_pct"]))
        if ep in M.index:
            act.append("workplaces " + num(M.loc[ep, "workplaces"], 0))
        lines.append(" & ".join([
            EP_LABEL[ep], str(int(p.n_days)), str(int(p.k)),
            num(p.b_pct) + r"\newline " + ivl(p.lo_pct, p.hi_pct) + cal,
            num(q.loc["PM25_ugm3", "b"]) + (r"\newline " + ivl(q.loc["PM25_ugm3", "lo_cal"], q.loc["PM25_ugm3", "hi_cal"])
                                            if pd.notna(q.loc["PM25_ugm3", "lo_cal"]) else ""),
            num(q.loc["AQI", "b"]) + (r"\newline " + ivl(q.loc["AQI", "lo_cal"], q.loc["AQI", "hi_cal"])
                                      if pd.notna(q.loc["AQI", "lo_cal"]) else ""),
            r"\newline ".join(act) or "--"]) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_shocks.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def events():
    root = os.path.join(HERE, "..", "..")
    cal = os.path.join(root, "Traffic", "data_availability", "02_event_calendars")
    E = pd.read_csv(os.path.join(cal, "disruption_episodes.csv")).set_index("episode")
    eid = pd.read_csv(os.path.join(cal, "eid_dates_2013_2024.csv"), parse_dates=["date"])
    L = pd.read_csv(os.path.join(OUT, "long_eid.csv"))
    P = pd.read_csv(os.path.join(OUT, "long_episodes.csv"))
    usable = int(L[(L.analysis == "all") & (L.outcome == "PM25")].n_events.iloc[0])
    season = {1: "dry", 2: "dry", 3: "pre-monsoon", 4: "pre-monsoon", 5: "pre-monsoon", 6: "monsoon",
              7: "monsoon", 8: "monsoon", 9: "monsoon", 10: "post-monsoon", 11: "dry", 12: "dry"}
    hdr = (r"\textbf{Event} & \textbf{Kind} & \textbf{Days} & \textbf{Season} & "
           r"\textbf{Activity check} \\")
    lines = [r"\begin{longtable}{L{5.0cm} L{4.3cm} C{1.6cm} L{2.0cm} L{2.6cm}}",
             r"\caption{The events. Days: Event days in the definition, with the days on which "
             r"\pmtf{} was observed at one or more monitors in brackets. Sources and the dates of each "
             r"Eid are in Tables~\ref{S-tab:s-eid-dates} and~\ref{S-tab:s-episodes}.}\label{tab:events}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead",
             r"\bottomrule\endfoot",
             " & ".join([r"Eid-ul-Fitr and Eid-ul-Adha, 2013--2024",
                         r"Holiday exodus; offices, factories and most shops closed",
                         "%d Eids (%d usable)" % (len(eid), usable), "April to October",
                         r"NO$_2$ column (2019 on), NO$_x$, CO"]) + r" \\"]
    for ep in EPISODES:
        e = E.loc[ep]
        p = P[(P.episode == ep) & (P.outcome == "PM25")].iloc[0]
        months = pd.date_range(e.start, e.end)
        seas = sorted({season[m] for m in months.month}, key=["dry", "pre-monsoon", "monsoon", "post-monsoon"].index)
        acts = P[(P.episode == ep)].outcome.tolist()
        chk = []
        if "TROPOMI" in acts:
            chk.append(r"NO$_2$ column")
        if pd.Timestamp(e.start).year < 2019 and "NOX" in acts:
            chk.append(r"NO$_x$")
        if pd.Timestamp(e.start).year in (2020, 2021):
            chk.append("mobility")
        lines.append(" & ".join([EP_LABEL[ep], e.kind[0].upper() + e.kind[1:],
                                 "%d (%d)" % (p.n_days, p.n_obs_days), ", ".join(seas),
                                 ", ".join(chk) or "none"]) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_events.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


def limits():
    S = pd.read_csv(os.path.join(OUT, "limits.csv")).set_index("scenario")
    rows = [("observed", "Observed"), ("eid", "Every day as on Eid"),
            ("holiday_2020", "Every day as in the 2020 general holiday"),
            ("blockade_2023", "Every day as on the 2023--24 blockade days")]
    hdr = (r"\textbf{Scenario} & \textbf{Annual mean} & \textbf{Dec--Feb mean} & \textbf{Days $>$65 (\%)} & "
           r"\textbf{Dec--Feb days $>$65 (\%)} & \textbf{AQI $>$200 (\%)} & \textbf{Gap to 35 closed (\%)} \\")
    lines = [r"\begin{longtable}{L{4.0cm} C{1.7cm} C{1.7cm} C{1.6cm} C{1.9cm} C{1.6cm} C{1.9cm}}",
             r"\caption{Illustrative ceiling: The US Embassy record, March 2016 to December 2024 ("
             + "{:,}".format(int(S.loc["observed", "n_days"])) + r" days), with every day's PM$_{2.5}$ "
             r"reduced in the proportion estimated for each event (Table~\ref{tab:shocks}). Concentrations in "
             r"$\mu$g\,m$^{-3}$. 65 and 35: The national 24-hour and annual PM$_{2.5}$ standards (APCR 2022, "
             r"Schedule 1). AQI $>$200: Days in the very unhealthy or hazardous categories. Last column: Share of the "
             r"gap between the observed mean and the annual standard that the reduction would close. For Eid "
             r"the bracketed values apply the ends of its 95\% interval. The proportions were estimated "
             r"mostly outside the winter; applying them to every day assumes they hold in all seasons.}"
             r"\label{tab:limits}\\",
             r"\toprule", hdr, r"\midrule\endfirsthead", r"\toprule", hdr, r"\midrule\endhead",
             r"\bottomrule\endfoot"]
    cols = [("mean", 1), ("djf_mean", 1), ("share_above_65", 1), ("share_djf_above_65", 1),
            ("share_aqi_above_200", 1), ("gap_closed_pct", 1)]
    for key, lab in rows:
        r = S.loc[key]
        cells = [lab]
        for c, nd in cols:
            v = num(r[c], nd, False)
            if key == "eid":
                lo, hi = S.loc["eid_lo", c], S.loc["eid_hi", c]
                v += r"\newline {\scriptsize[%s, %s]}" % (num(min(lo, hi), nd, False), num(max(lo, hi), nd, False))
            cells.append("--" if key == "observed" and c == "gap_closed_pct" else v)
        lines.append(" & ".join(cells) + r" \\")
    lines.append(r"\end{longtable}")
    lines = [r"\begingroup\small"] + lines + [r"\endgroup"]
    open(os.path.join(TAB, "tab_limits.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    effects()
    scenarios()
    stations()
    sensitivity()
    long_stations()
    events()
    shocks()
    limits()
    # screening() is superseded by Table S3 (make_supp_tables.py) and no longer called
    print("wrote", sorted(os.listdir(TAB)))
