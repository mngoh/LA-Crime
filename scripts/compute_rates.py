"""Compute assault victim counts and victimization rates for the published page.

Inputs
  data/eda_data.csv          simple assault (battery) victims, LAPD, Jan 2020 to Jun 2023
  data/eda_data_deadly.csv   aggravated assault victims, same window
  Census Reporter API        ACS 5-year population by race and sex, LA city and its census tracts
  Census gazetteer           2020 census tract centroids for California
  LA GeoHub                  LAPD division boundaries (GeoJSON)

Output
  data/page_data.json        everything scripts/build_page.py needs

Run:  python scripts/compute_rates.py
External downloads are cached in data/external/ (ignored by git).
"""
import csv
import json
import pathlib
import urllib.request

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXT = DATA / "external"
EXT.mkdir(exist_ok=True)

YEARS = 3.5  # January 2020 to June 2023
MIN_POP = 2000  # do not rate a race/sex cell with fewer residents than this

# LAPD victim descent codes -> the four groups used on the page
RACE = {"B": "Black", "H": "Hispanic", "W": "White",
        "A": "Asian", "C": "Asian", "F": "Asian", "J": "Asian", "K": "Asian", "V": "Asian", "Z": "Asian", "D": "Asian", "L": "Asian"}
RACES = ["Black", "Hispanic", "White", "Asian"]
# ACS "sex by age" tables: B = Black alone, I = Hispanic or Latino, H = White alone (not Hispanic), D = Asian alone
ACS_TABLE = {"Black": "B01001B", "Hispanic": "B01001I", "White": "B01001H", "Asian": "B01001D"}
LA_CITY = "16000US0644000"

CR = "https://api.censusreporter.org/1.0/data/show/acs2024_5yr"
GAZETTEER = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_gaz_tracts_06.txt"
DIVISIONS = ("https://services5.arcgis.com/7nsPwEMP38bSkCjy/arcgis/rest/services/LAPD_Division/FeatureServer/0/query"
             "?where=1%3D1&outFields=*&outSR=4326&f=geojson")
# Division names as LA GeoHub spells them -> as the LAPD data spells them
DIVISION_NAME = {"77TH STREET": "77th Street", "NORTH HOLLYWOOD": "N Hollywood", "WEST LOS ANGELES": "West LA"}


def fetch(url, name):
    """Download url to data/external/name once and return the path."""
    path = EXT / name
    if not path.exists():
        print("downloading", name)
        req = urllib.request.Request(url, headers={"User-Agent": "LA-Crime-analysis/1.0 (github.com/mngoh/LA-Crime)"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())
    return path


def load_victims():
    frames = []
    for name, kind in [("eda_data.csv", "simple"), ("eda_data_deadly.csv", "aggravated")]:
        d = pd.read_csv(DATA / name, encoding="latin-1", engine="python", on_bad_lines="skip")
        d["kind"] = kind
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["race"] = df["vict_race"].map(RACE)
    df["sex"] = df["vict_sex"].where(df["vict_sex"].isin(["M", "F"]))
    return df


def victim_counts(df):
    known = df.dropna(subset=["race", "sex"])

    def by_race_sex(frame):
        t = frame.groupby(["race", "sex"]).size().unstack(fill_value=0)
        t["female_share"] = (t["F"] / (t["F"] + t["M"])).round(3)
        return t.to_dict("index")

    out = {
        "total": len(df),
        "simple": int((df["kind"] == "simple").sum()),
        "aggravated": int((df["kind"] == "aggravated").sum()),
        "known": len(known),
        "divisions": int(df["area_name"].nunique()),
        "race_sex_all": by_race_sex(known),
        "race_sex_simple": by_race_sex(known[known["kind"] == "simple"]),
        "race_sex_aggravated": by_race_sex(known[known["kind"] == "aggravated"]),
        "all_by_year": known.groupby(["year_incident_date", "sex"]).size().unstack(fill_value=0).to_dict("index"),
        "weapons": df["weapon_def"].value_counts().head(6).to_dict(),
        "median_age": float(df.loc[df["vict_age"] > 0, "vict_age"].median()),
        "age_iqr": [float(df.loc[df["vict_age"] > 0, "vict_age"].quantile(q)) for q in (0.25, 0.75)],
        "centroids": df.groupby("area_name")[["lat", "lon"]].median().round(4).to_dict("index"),
    }
    div = known.groupby(["area_name", "race", "sex"]).size().unstack(fill_value=0)
    out["division_counts"] = {area: {race: {"F": int(row["F"]), "M": int(row["M"])} for (a, race), row in div.iterrows() if a == area}
                              for area in div.index.get_level_values(0).unique()}
    return out


def male_female(estimate, table):
    return float(estimate[table + "002"]), float(estimate[table + "017"])


def point_in_ring(lat, lon, ring):
    """Ray-casting test; ring is a list of [lon, lat]."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def division_lookup():
    features = json.loads(fetch(DIVISIONS, "lapd_divisions.geojson").read_text())["features"]

    def lookup(lat, lon):
        for f in features:
            rings = f["geometry"]["coordinates"]
            if point_in_ring(lat, lon, rings[0]) and not any(point_in_ring(lat, lon, hole) for hole in rings[1:]):
                name = f["properties"]["APREC"]
                return DIVISION_NAME.get(name, name.title())
        return None
    return lookup


def population():
    """City-wide and per-division residents by race and sex."""
    tables = ",".join(["B01001"] + list(ACS_TABLE.values()))
    place = json.loads(fetch(f"{CR}?table_ids={tables}&geo_ids={LA_CITY}", "acs_la_city.json").read_text())
    tracts = json.loads(fetch(f"{CR}?table_ids={','.join(ACS_TABLE.values())}&geo_ids=140|{LA_CITY}", "acs_la_tracts.json").read_text())

    est = place["data"][LA_CITY]
    city = {race: dict(zip(["M", "F"], male_female(est[t]["estimate"], t))) for race, t in ACS_TABLE.items()}

    centroid = {}
    with open(fetch(GAZETTEER, "gazetteer_tracts_ca.txt"), encoding="latin-1") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            lon_key = next(k for k in row if k.startswith("INTPTLONG"))
            centroid[row["GEOID"].strip()] = (float(row["INTPTLAT"]), float(row[lon_key]))

    lookup = division_lookup()
    by_division, assigned, unassigned = {}, 0, 0
    for geo_id, tables_ in tracts["data"].items():
        geoid = geo_id.split("US")[1]
        if geoid not in centroid:
            continue
        division = lookup(*centroid[geoid])
        if division is None:
            unassigned += 1
            continue
        assigned += 1
        for race, t in ACS_TABLE.items():
            m, f = male_female(tables_[t]["estimate"], t)
            cell = by_division.setdefault(division, {}).setdefault(race, {"M": 0.0, "F": 0.0})
            cell["M"] += m
            cell["F"] += f
    return {"release": place["release"]["name"], "city_total": float(est["B01001"]["estimate"]["B01001001"]),
            "city": city, "by_division": by_division, "tracts": assigned, "unassigned": unassigned}


def rate(count, residents):
    return round(count / residents / YEARS * 1e5) if residents >= MIN_POP else None


def main():
    df = load_victims()
    counts = victim_counts(df)
    pop = population()

    missing = set(counts["division_counts"]) ^ set(pop["by_division"])
    assert not missing, f"division names differ between LAPD data and boundaries: {missing}"

    city_rates = {}
    for race in RACES:
        f_n, m_n = counts["race_sex_all"][race]["F"], counts["race_sex_all"][race]["M"]
        f_pop, m_pop = pop["city"][race]["F"], pop["city"][race]["M"]
        city_rates[race] = {"F": rate(f_n, f_pop), "M": rate(m_n, m_pop), "popF": f_pop, "popM": m_pop}
        city_rates[race]["ratio"] = round(city_rates[race]["F"] / city_rates[race]["M"], 2)

    division_rates = []
    for division in sorted(counts["division_counts"]):
        rec = {"division": division}
        for race in RACES:
            for sex in ["F", "M"]:
                n = counts["division_counts"][division].get(race, {}).get(sex, 0)
                residents = pop["by_division"][division][race][sex]
                rec[f"{race}_{sex}"] = {"n": n, "pop": round(residents), "rate": rate(n, residents)}
        division_rates.append(rec)

    out = {"window": "January 2020 to June 2023", "years": YEARS, "min_pop": MIN_POP, "counts": counts,
           "population": {k: pop[k] for k in ["release", "city_total", "city", "tracts", "unassigned"]},
           "rates": city_rates, "division_rates": division_rates}
    (DATA / "page_data.json").write_text(json.dumps(out, indent=1, default=int))
    print("victims", counts["total"], "| known race and sex", counts["known"], "| tracts", pop["tracts"], "| unassigned", pop["unassigned"])
    print("rates per 100,000 per year:", {r: (v["F"], v["M"]) for r, v in city_rates.items()})
    print("wrote", DATA / "page_data.json")


if __name__ == "__main__":
    main()
