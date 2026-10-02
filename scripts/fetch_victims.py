"""Download LAPD assault victims, January 2020 to December 2023, from the city's open data portal.

Source: LAPD "Crime Data from 2020 to 2024" (data.lacity.org, dataset 2nrs-mtv8), the
pre-NIBRS records system. LAPD moved to NIBRS on March 7, 2024 and the old file thins out
from then on, so the window stops at the last full year, 2023.

Writes the two victim files the other scripts read, one row per report:
  data/eda_data.csv          crime code 624, BATTERY - SIMPLE ASSAULT
  data/eda_data_deadly.csv   crime code 230, ASSAULT WITH DEADLY WEAPON, AGGRAVATED ASSAULT

Values are kept as LAPD publishes them: no imputation. Missing coordinates stay 0, as LAPD
codes them, and are dropped where location is needed.

Run:  python scripts/fetch_victims.py
"""
import io
import urllib.parse
import urllib.request

import pandas as pd

from compute_rates import DATA

API = "https://data.lacity.org/resource/2nrs-mtv8.csv"
START, END = "2020-01-01T00:00:00", "2023-12-31T23:59:59"
FILES = {"624": "eda_data.csv", "230": "eda_data_deadly.csv"}
RENAME = {
    "dr_no": "div_record", "area": "area", "area_name": "area_name", "rpt_dist_no": "rpt", "part_1_2": "part",
    "crm_cd": "crime_code", "crm_cd_desc": "crime_code_def", "mocodes": "mocodes", "vict_age": "vict_age",
    "vict_sex": "vict_sex", "vict_descent": "vict_race", "premis_cd": "premise_code", "premis_desc": "premise",
    "weapon_used_cd": "weapon_code", "weapon_desc": "weapon_def", "status": "case_status", "status_desc": "status_def",
    "location": "location", "cross_street": "cross_street", "lat": "lat", "lon": "lon",
}


def download(code):
    query = urllib.parse.urlencode({
        "$where": f"crm_cd = '{code}' AND date_occ between '{START}' and '{END}'",
        "$order": "dr_no", "$limit": 500000,
    })
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": "LA-Crime analysis (github.com/mngoh/LA-Crime)"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return pd.read_csv(io.BytesIO(r.read()), dtype=str)


def main():
    for code, name in FILES.items():
        raw = download(code)
        d = raw[list(RENAME)].rename(columns=RENAME)
        occ = pd.to_datetime(raw["date_occ"])
        hhmm = raw["time_occ"].str.zfill(4)
        d["report_date"] = pd.to_datetime(raw["date_rptd"]).dt.date
        d["incident_date"] = occ.dt.date
        d["year_incident_date"] = occ.dt.year
        d["month_incident_date"] = occ.dt.month
        d["hour_incident"] = hhmm.str[:2].astype(int)
        d["vict_age"] = pd.to_numeric(d["vict_age"], errors="coerce")
        d["lat"] = pd.to_numeric(d["lat"], errors="coerce")
        d["lon"] = pd.to_numeric(d["lon"], errors="coerce")
        d = d.drop_duplicates("div_record")
        d.to_csv(DATA / name, index=False)
        print(f"{name}: {len(d):,} reports, {d['incident_date'].min()} to {d['incident_date'].max()}")


if __name__ == "__main__":
    main()
