"""Compute assault victim counts and victimization rates for the published page.

Inputs
  data/eda_data.csv          simple assault (battery) victims, LAPD, Jan 2020 to Dec 2023 (scripts/fetch_victims.py)
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

YEARS = 4.0  # January 2020 to December 2023
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
    df["partner"] = df["crime_code"].astype(str).isin(["626", "236"])  # intimate partner assault
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
    # female residents by age band, citywide (table variables 018 to 031)
    city_female_age = {race: [float(est[t]["estimate"][f"{t}{i:03d}"]) for i in range(18, 32)] for race, t in ACS_TABLE.items()}

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
            "city": city, "city_female_age": city_female_age, "by_division": by_division, "tracts": assigned, "unassigned": unassigned}


# ACS female age bands, in table order 018..031
AGE_BANDS = [(0, 4), (5, 9), (10, 14), (15, 17), (18, 19), (20, 24), (25, 29), (30, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, 84), (85, 200)]
AGE_LABELS = ["0-4", "5-9", "10-14", "15-17", "18-19", "20-24", "25-29", "30-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]


def age_band(age):
    for i, (lo, hi) in enumerate(AGE_BANDS):
        if lo <= age <= hi:
            return i


def weapon_class(w):
    w = str(w).upper()
    if "STRONG-ARM" in w:
        return "Strong-arm"
    if any(k in w for k in ["GUN", "PISTOL", "FIREARM", "RIFLE", "REVOLVER", "SHOTGUN", "UZI"]):
        return "Firearm"
    if any(k in w for k in ["KNIFE", "CUTTING", "BLADE", "MACHETE", "RAZOR", "SWORD", "SCISSORS", "ICE PICK", "AXE", "BOTTLE", "GLASS"]):
        return "Knife or cutting"
    if "UNKNOWN" in w or w == "NAN":
        return "Unknown or other"
    return "Blunt or other object"


def hypothesis_tests(df, pop, years):
    """Cuts of the data that test explanations for the Black women's rate gap. Women only."""
    women = df[(df["sex"] == "F") & df["race"].notna()].copy()
    black = women["race"] == "Black"
    out = {}

    # Age: age-specific rates per race, and rates standardized to the age mix of all women in the four groups
    aged = women[women["vict_age"] > 0].copy()
    aged["band"] = aged["vict_age"].apply(age_band)
    standard = [sum(pop["city_female_age"][r][i] for r in RACES) for i in range(len(AGE_BANDS))]
    std_total = sum(standard)
    age = {"labels": AGE_LABELS, "rates": {}, "standardized": {}, "crude": {}}
    for r in RACES:
        counts = aged[aged["race"] == r]["band"].value_counts()
        pops = pop["city_female_age"][r]
        rates_r = [(counts.get(i, 0) / pops[i] / years * 1e5) if pops[i] >= 500 else None for i in range(len(AGE_BANDS))]
        age["rates"][r] = [round(x) if x is not None else None for x in rates_r]
        age["standardized"][r] = round(sum((x or 0) * w for x, w in zip(rates_r, standard)) / std_total)
        age["crude"][r] = round(len(aged[aged["race"] == r]) / sum(pops) / years * 1e5)
    age["unknown_age"] = int((women["vict_age"] <= 0).sum())
    out["age"] = age

    # Location: within each division, Black women's rate against all other women's rate; and the citywide rate
    # Black women would have if they faced each division's other-women rate (indirect standardization)
    loc = []
    expected = 0.0
    for division, cells in sorted(pop["by_division"].items()):
        w = women[women["area_name"] == division]
        b_n = int((w["race"] == "Black").sum()); o_n = int((w["race"] != "Black").sum())
        b_pop = cells["Black"]["F"]; o_pop = sum(cells[r]["F"] for r in RACES if r != "Black")
        b_rate = rate(b_n, b_pop); o_rate = rate(o_n, o_pop)
        if o_pop > 0:
            expected += b_pop * (o_n / o_pop)
        loc.append({"division": division, "black_rate": b_rate, "other_rate": o_rate,
                    "ratio": round(b_rate / o_rate, 2) if b_rate and o_rate else None, "black_pop": round(b_pop)})
    black_pop_total = sum(c["Black"]["F"] for c in pop["by_division"].values())
    out["location"] = {"divisions": loc,
                       "actual_rate": round(int(black.sum()) / black_pop_total / years * 1e5),
                       "expected_if_other_rates": round(expected / black_pop_total / years * 1e5)}

    # Type: women's rates by race for simple and aggravated assault
    out["type"] = {kind: {r: rate(int(((women["race"] == r) & (women["kind"] == kind)).sum()), pop["city"][r]["F"]) for r in RACES}
                   for kind in ["simple", "aggravated"]}

    # Time: women's annual rates by race
    span = {2020: 1.0, 2021: 1.0, 2022: 1.0, 2023: 1.0}
    out["time"] = {str(y): {r: round(int(((women["race"] == r) & (women["year_incident_date"] == y)).sum()) / pop["city"][r]["F"] / span[y] * 1e5) for r in RACES} for y in span}

    # Premises: where assaults on Black women happen, against all other women
    prem = women["premise"].fillna("Unknown").str.title().str.replace(r"\s*\(.*\)", "", regex=True).str.strip()
    top = prem[black].value_counts().head(8).index.tolist()
    out["premises"] = {"labels": top,
                       "black": [round(float((prem[black] == p).mean() * 100), 1) for p in top],
                       "other": [round(float((prem[~black] == p).mean() * 100), 1) for p in top]}

    # Weapons: circumstances, by class
    wc = women["weapon_def"].apply(weapon_class)
    order = ["Strong-arm", "Firearm", "Knife or cutting", "Blunt or other object", "Unknown or other"]
    out["weapons"] = {"labels": order,
                      "black": [round(float((wc[black] == k).mean() * 100), 1) for k in order],
                      "other": [round(float((wc[~black] == k).mean() * 100), 1) for k in order]}
    out["women_n"] = {"black": int(black.sum()), "other": int((~black).sum())}
    return out


def unknown_race_sensitivity(df, pop):
    """Women's rates if victims with no usable race resembled the known-race victims in the same division.

    Two versions: truly unknown race (X, blank) only, and unknown plus LAPD's "Other" descent code (an upper bound).
    Unknown race is not spread evenly, so this shows how far the uneven pattern can move the ratios."""
    women = df[df["sex"] == "F"]
    out = {}
    for name, extra in [("unknown", set()), ("unknown_and_other", {"O"})]:
        pool = women["race"].isna() & (women["vict_race"].isna() | women["vict_race"].isin({"X", "-"} | extra))
        added = {r: 0.0 for r in RACES}
        for division, w in women.groupby("area_name"):
            known = w["race"].value_counts()
            n_pool = int(pool[w.index].sum())
            if known.sum():
                for r in RACES:
                    added[r] += n_pool * known.get(r, 0) / known.sum()
        rates = {r: rate(int((women["race"] == r).sum()) + added[r], pop["city"][r]["F"]) for r in RACES}
        out[name] = {"pool": int(pool.sum()), "rates": rates, "ratios": {r: round(rates["Black"] / rates[r], 2) for r in RACES[1:]}}
    return out


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

    tests = hypothesis_tests(df, pop, YEARS)
    tests["unknown_race"] = unknown_race_sensitivity(df, pop)
    print("if unknown race resembled known victims in the same division:", {k: v["ratios"] for k, v in tests["unknown_race"].items()})
    out = {"window": "January 2020 to December 2023", "years": YEARS, "min_pop": MIN_POP, "counts": counts, "tests": tests,
           "population": {k: pop[k] for k in ["release", "city_total", "city", "tracts", "unassigned"]},
           "rates": city_rates, "division_rates": division_rates}
    (DATA / "page_data.json").write_text(json.dumps(out, indent=1, default=int))
    print("victims", counts["total"], "| known race and sex", counts["known"], "| tracts", pop["tracts"], "| unassigned", pop["unassigned"])
    print("rates per 100,000 per year:", {r: (v["F"], v["M"]) for r, v in city_rates.items()})
    print("age-standardized women's rates:", tests["age"]["standardized"], "| crude:", tests["age"]["crude"])
    print("location: actual", tests["location"]["actual_rate"], "expected at other women's division rates", tests["location"]["expected_if_other_rates"])
    print("wrote", DATA / "page_data.json")


if __name__ == "__main__":
    main()
