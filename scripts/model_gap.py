"""How much of the Black-women / other-women assault gap survives adjustment?

Poisson rate models at the census-tract level, women only. Each incident is
geocoded to the tract it happened in; the denominator is the tract's female
residents of that group and age band (ACS 2020-2024). Models are added one
layer at a time so the surviving rate ratio for Black women can be read off
after each adjustment:

  M0  group only                      (the crude gap against other women)
  M1  + victim age band
  M2  + year
  M3  + LAPD division fixed effects   (where the assault happened)
  M4  + tract socioeconomics          (poverty, income, unemployment, renters, density)
  M5  + tract homelessness            (LAHSA count, if data/external/lahsa_tracts.csv exists)

Writes data/model_results.json. Run after scripts/compute_rates.py (reuses its downloads).
"""
import csv
import json
import math
import pathlib
import urllib.request

import numpy as np
import pandas as pd
import statsmodels.api as sm
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from compute_rates import (ACS_TABLE, AGE_BANDS, AGE_LABELS, DATA, EXT, LA_CITY, RACE, RACES, YEARS,
                           age_band, division_lookup, fetch, load_victims)

CR = "https://api.censusreporter.org/1.0/data/show/acs2024_5yr"
GEO = f"https://api.censusreporter.org/1.0/geo/show/tiger2024?geo_ids=140|{LA_CITY}"
SES_TABLES = "B01003,B17001,B19013,B23025,B25003"
MIN_CELL_POP = 1  # a cell needs at least one resident to have a rate
# coarse age bands for the model, built from the ACS female bands (indexes into AGE_LABELS)
COARSE = {"0-17": [0, 1, 2, 3], "18-29": [4, 5, 6], "30-44": [7, 8], "45-64": [9, 10], "65+": [11, 12, 13]}
COARSE_OF = {i: name for name, idx in COARSE.items() for i in idx}


def tracts_geometry():
    g = json.loads(fetch(GEO, "la_tracts_geometry.json").read_text())["features"]
    geoids = [f["properties"]["geoid"].split("US")[1] for f in g]
    shapes = [shape(f["geometry"]) for f in g]
    aland = {gid: float(f["properties"]["aland"]) for gid, f in zip(geoids, g)}
    return geoids, shapes, aland


def tract_populations():
    """Female residents by tract, group (Black / other) and age band."""
    d = json.loads(fetch(f"{CR}?table_ids={','.join(ACS_TABLE.values())}&geo_ids=140|{LA_CITY}", "acs_la_tracts.json").read_text())
    rows = []
    for geo_id, tables in d["data"].items():
        geoid = geo_id.split("US")[1]
        for race, t in ACS_TABLE.items():
            est = tables[t]["estimate"]
            for i, label in enumerate(AGE_LABELS):
                rows.append({"geoid": geoid, "group": "Black" if race == "Black" else "Other", "band": COARSE_OF[i], "pop": float(est[f"{t}{18 + i:03d}"])})
    return pd.DataFrame(rows).groupby(["geoid", "group", "band"], as_index=False)["pop"].sum()


def tract_ses(aland):
    d = json.loads(fetch(f"{CR}?table_ids={SES_TABLES}&geo_ids=140|{LA_CITY}", "acs_la_tracts_ses.json").read_text())
    rows = []
    for geo_id, t in d["data"].items():
        geoid = geo_id.split("US")[1]
        e = lambda table, var: t[table]["estimate"][var]
        pop = e("B01003", "B01003001")
        pov_universe = e("B17001", "B17001001")
        labor = e("B23025", "B23025003")
        tenure = e("B25003", "B25003001")
        rows.append({
            "geoid": geoid,
            "poverty": e("B17001", "B17001002") / pov_universe if pov_universe else np.nan,
            "log_income": math.log(e("B19013", "B19013001")) if e("B19013", "B19013001") and e("B19013", "B19013001") > 0 else np.nan,
            "unemployment": e("B23025", "B23025005") / labor if labor else np.nan,
            "renters": e("B25003", "B25003003") / tenure if tenure else np.nan,
            "log_density": math.log(pop / (aland[geoid] / 1e6)) if pop and aland.get(geoid) else np.nan,
        })
    return pd.DataFrame(rows)


def homelessness():
    """Optional: LAHSA point-in-time count by tract, as data/external/lahsa_tracts.csv with columns geoid,homeless."""
    path = EXT / "lahsa_tracts.csv"
    if not path.exists():
        return None
    h = pd.read_csv(path, dtype={"geoid": str})
    return h.groupby("geoid", as_index=False)["homeless"].sum()


def main():
    df = load_victims()
    women = df[(df["sex"] == "F") & df["race"].notna() & (df["vict_age"] > 0) & df["lat"].notna() & (df["lat"] > 30)].copy()
    women["group"] = np.where(women["race"] == "Black", "Black", "Other")
    women["band"] = women["vict_age"].apply(age_band).map(COARSE_OF)

    # geocode each assault to the tract it happened in
    geoids, shapes, aland = tracts_geometry()
    tree = STRtree(shapes)
    pts = [Point(lon, lat) for lat, lon in zip(women["lat"], women["lon"])]
    hit = tree.query(pts, predicate="within")  # 2 x n: [point index, tract index]
    tract_of = {}
    for pi, ti in zip(*hit):
        tract_of.setdefault(pi, geoids[ti])
    women["geoid"] = [tract_of.get(i) for i in range(len(women))]
    located = women.dropna(subset=["geoid"])
    print(f"women with age and location: {len(women):,}; inside a city tract: {len(located):,}")

    # division for each tract (fixed effects), by tract centroid
    lookup = division_lookup()
    division = {}
    for gid, shp in zip(geoids, shapes):
        c = shp.centroid
        division[gid] = lookup(c.y, c.x)

    counts = located.groupby(["geoid", "group", "band", "year_incident_date"]).size().rename("n").reset_index()
    pop = tract_populations()
    years = sorted(located["year_incident_date"].unique())
    grid = pop.merge(pd.DataFrame({"year_incident_date": years}), how="cross")
    cells = grid.merge(counts, on=["geoid", "group", "band", "year_incident_date"], how="left").fillna({"n": 0})
    cells["exposure"] = cells["pop"] * np.where(cells["year_incident_date"] == 2023, 0.5, 1.0)
    cells = cells[cells["pop"] >= MIN_CELL_POP].copy()
    cells["division"] = cells["geoid"].map(division)
    cells = cells.dropna(subset=["division"])
    ses = tract_ses(aland)
    cells = cells.merge(ses, on="geoid", how="left").dropna(subset=["poverty", "log_income", "unemployment", "renters", "log_density"])
    hl = homelessness()
    if hl is not None:
        cells = cells.merge(hl, on="geoid", how="left").fillna({"homeless": 0})
        cells["log_homeless"] = np.log1p(cells["homeless"])
    for col in ["poverty", "log_income", "unemployment", "renters", "log_density"]:
        cells[col] = (cells[col] - cells[col].mean()) / cells[col].std()
    cov = cells.groupby("group")["n"].sum()
    tot = located.groupby("group").size()
    coverage = {g: round(float(cov.get(g, 0) / tot[g] * 100), 1) for g in tot.index}
    print(f"model cells: {len(cells):,} (tract x group x age band x year), victims in cells: {int(cells['n'].sum()):,}; coverage by group: {coverage}")

    cells["black"] = (cells["group"] == "Black").astype(int)
    cells["band"] = cells["band"].astype(str)
    cells["year"] = cells["year_incident_date"].astype(str)
    layers = [
        ("M0 group only", "black"),
        ("M1 + age", "black + C(band)"),
        ("M2 + year", "black + C(band) + C(year)"),
        ("M3 + division", "black + C(band) + C(year) + C(division)"),
        ("M4 + tract socioeconomics", "black + C(band) + C(year) + C(division) + poverty + log_income + unemployment + renters + log_density"),
    ]
    if hl is not None:
        layers.append(("M5 + tract homelessness", layers[-1][1] + " + log_homeless"))

    results = []
    for name, formula in layers:
        model = sm.GLM.from_formula(f"n ~ {formula}", data=cells, family=sm.families.Poisson(), offset=np.log(cells["exposure"]))
        fit = model.fit(cov_type="HC0")
        b, se = fit.params["black"], fit.bse["black"]
        results.append({"model": name, "rate_ratio": round(math.exp(b), 2), "ci_low": round(math.exp(b - 1.96 * se), 2),
                        "ci_high": round(math.exp(b + 1.96 * se), 2), "controls": formula})
        print(f"{name:28s} Black women vs other women: {math.exp(b):.2f}x  (95% CI {math.exp(b - 1.96 * se):.2f} to {math.exp(b + 1.96 * se):.2f})")

    # the same ladder, split by assault type
    by_type = {}
    for kind in ["simple", "aggravated"]:
        ck = located[located["kind"] == kind].groupby(["geoid", "group", "band", "year_incident_date"]).size().rename("n").reset_index()
        ct = grid.merge(ck, on=["geoid", "group", "band", "year_incident_date"], how="left").fillna({"n": 0})
        ct["exposure"] = ct["pop"] * np.where(ct["year_incident_date"] == 2023, 0.5, 1.0)
        ct = ct[ct["pop"] >= MIN_CELL_POP].copy()
        ct["division"] = ct["geoid"].map(division)
        ct = ct.dropna(subset=["division"]).merge(ses, on="geoid", how="left").dropna()
        for col in ["poverty", "log_income", "unemployment", "renters", "log_density"]:
            ct[col] = (ct[col] - ct[col].mean()) / ct[col].std()
        ct["black"] = (ct["group"] == "Black").astype(int); ct["band"] = ct["band"].astype(str); ct["year"] = ct["year_incident_date"].astype(str)
        fit = sm.GLM.from_formula(f"n ~ {layers[4][1]}", data=ct, family=sm.families.Poisson(), offset=np.log(ct["exposure"])).fit(cov_type="HC0")
        b, se = fit.params["black"], fit.bse["black"]
        by_type[kind] = {"rate_ratio": round(math.exp(b), 2), "ci_low": round(math.exp(b - 1.96 * se), 2), "ci_high": round(math.exp(b + 1.96 * se), 2)}
        print(f"fully adjusted, {kind:10s}: {math.exp(b):.2f}x (95% CI {math.exp(b - 1.96 * se):.2f} to {math.exp(b + 1.96 * se):.2f})")

    out = {"women_located": int(len(located)), "women_total": int(len(women)), "cells": int(len(cells)), "min_cell_pop": MIN_CELL_POP, "coverage": coverage, "age_bands": list(COARSE),
           "ladder": results, "fully_adjusted_by_type": by_type, "homelessness_included": hl is not None,
           "ses_covariates": ["poverty rate", "log median household income", "unemployment rate", "renter share", "log population density"]}
    (DATA / "model_results.json").write_text(json.dumps(out, indent=1))
    print("wrote", DATA / "model_results.json")


if __name__ == "__main__":
    main()
