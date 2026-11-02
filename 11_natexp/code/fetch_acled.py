"""Fetch every ACLED event for Bangladesh, 1 January 2012 to 31 December 2024.

Run this yourself: it signs in to ACLED with the myACLED e-mail and password in
Traffic/gates/credentials.env (ACLED_EMAIL, ACLED_PASSWORD), which are read but never
printed.  ACLED's terms allow only derived products to be shared, so the records are kept
on this computer (Traffic/gates/out/acled_bangladesh_2012_2024.json, outside the public
deposit); the analysis derives daily counts of strike, blockade, curfew and protest events
from them.

Usage (from E:/FYDP_D):  python -I 11_natexp/code/fetch_acled.py
"""
import json
import os
import pathlib
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
CRED = ROOT / "Traffic" / "gates" / "credentials.env"
OUT = ROOT / "Traffic" / "gates" / "out" / "acled_bangladesh_2012_2024.json"


def credentials():
    vals = {}
    for line in CRED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals.get("ACLED_EMAIL"), vals.get("ACLED_PASSWORD")


def token(email, password):
    r = subprocess.run(["curl", "-s", "-m", "60", "-X", "POST", "https://acleddata.com/oauth/token",
                        "-H", "Content-Type: application/x-www-form-urlencoded",
                        "--data-urlencode", "username=" + email, "--data-urlencode", "password=" + password,
                        "-d", "grant_type=password", "-d", "client_id=acled", "-d", "scope=authenticated"],
                       capture_output=True)
    j = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    return j.get("access_token"), j.get("error_description") or j.get("error")


def main():
    if not CRED.exists():
        sys.exit("credentials.env not found at %s" % CRED)
    email, password = credentials()
    if not email or not password:
        sys.exit("ACLED_EMAIL or ACLED_PASSWORD missing from credentials.env")
    tok, err = token(email, password)
    if not tok:
        sys.exit("ACLED sign-in failed: %s" % err)
    print("signed in to ACLED (token valid 24 h)")
    rows = []
    for year in range(2012, 2025):                 # one request per year keeps responses small
        q = urllib.parse.urlencode({"country": "Bangladesh", "event_date": "%d-01-01|%d-12-31" % (year, year),
                                    "event_date_where": "BETWEEN", "limit": 0})
        r = subprocess.run(["curl", "-s", "-m", "600", "-H", "Authorization: Bearer " + tok,
                            "https://acleddata.com/api/acled/read?" + q], capture_output=True)
        data = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
        got = data.get("data", data if isinstance(data, list) else [])
        print("  %d: %d events" % (year, len(got)))
        if not got:
            sys.exit("empty response for %d: %s" % (year, str(data)[:200]))
        rows += got
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows), encoding="utf-8")
    print("wrote %d events to %s (keep this file private: ACLED terms)" % (len(rows), OUT))


if __name__ == "__main__":
    main()
