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
                rows.append({"geoid": geoid, "race": race, "band": COARSE_OF[i], "pop": float(est[f"{t}{18 + i:03d}"])})
    return pd.DataFrame(rows).groupby(["geoid", "race", "band"], as_index=False)["pop"].sum()


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
    """Optional: LAHSA 2024 count by tract from scripts/lahsa_tracts.py (data/external/lahsa_tracts.csv).

    Columns: geoid, homeless (one per person or dwelling counted), persons_est (LAHSA-style
    estimate using the count's dwelling multipliers), unsheltered_est (the same, street only)."""
    path = EXT / "lahsa_tracts.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"geoid": str}).groupby("geoid", as_index=False).sum(numeric_only=True)


def build_cells(located, pop, grid_years, division, ses, hl, groups, kinds=None, pool_other=False):
    """Tract x group x age band x year cells with counts, exposure and covariates, for the given victim groups.

    With pool_other, every non-Black group is merged into one "Other" group (one denominator per tract and
    age band), which is how the main ladder defines other women."""
    sub = located[located["race"].isin(groups)].copy()
    popg = pop[pop["race"].isin(groups)].copy()
    if pool_other:
        sub["race"] = np.where(sub["race"] == "Black", "Black", "Other")
        popg["race"] = np.where(popg["race"] == "Black", "Black", "Other")
        popg = popg.groupby(["geoid", "race", "band"], as_index=False)["pop"].sum()
    if kinds:
        sub = sub[sub["kind"].isin(kinds)]
    counts = sub.groupby(["geoid", "race", "band", "year_incident_date"]).size().rename("n").reset_index()
    grid = popg.merge(pd.DataFrame({"year_incident_date": grid_years}), how="cross")
    cells = grid.merge(counts, on=["geoid", "race", "band", "year_incident_date"], how="left").fillna({"n": 0})
    cells["exposure"] = cells["pop"]  # one person-year per resident per calendar year
    cells = cells[cells["pop"] >= MIN_CELL_POP].copy()
    cells["division"] = cells["geoid"].map(division)
    cells = cells.dropna(subset=["division"]).merge(ses, on="geoid", how="left").dropna(subset=["poverty", "log_income", "unemployment", "renters", "log_density"])
    if hl is not None:
        cells = cells.merge(hl, on="geoid", how="left").fillna({c: 0 for c in hl.columns if c != "geoid"})
        for c in [c for c in hl.columns if c != "geoid"]:
            cells["log_" + c] = np.log1p(cells[c])
    for col in ["poverty", "log_income", "unemployment", "renters", "log_density"]:
        cells[col] = (cells[col] - cells[col].mean()) / cells[col].std()
    cells["black"] = (cells["race"] == "Black").astype(int)
    cells["band"] = cells["band"].astype(str)
    cells["year"] = cells["year_incident_date"].astype(str)
    return cells


def ratio(cells, formula):
    """Rate ratio for Black women in a Poisson GLM with log exposure offset and robust errors."""
    fit = sm.GLM.from_formula(f"n ~ {formula}", data=cells, family=sm.families.Poisson(), offset=np.log(cells["exposure"])).fit(cov_type="HC0")
    b, se = fit.params["black"], fit.bse["black"]
    return {"rate_ratio": round(math.exp(b), 2), "ci_low": round(math.exp(b - 1.96 * se), 2), "ci_high": round(math.exp(b + 1.96 * se), 2)}


def main():
    df = load_victims()
    women = df[(df["sex"] == "F") & df["race"].notna() & (df["vict_age"] > 0) & df["lat"].notna() & (df["lat"] > 30)].copy()
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

    pop = tract_populations()
    years = sorted(located["year_incident_date"].unique())
    ses = tract_ses(aland)
    hl = homelessness()
    SES = "poverty + log_income + unemployment + renters + log_density"
    layers = [
        ("M0 group only", "black"),
        ("M1 + age", "black + C(band)"),
        ("M2 + year", "black + C(band) + C(year)"),
        ("M3 + division", "black + C(band) + C(year) + C(division)"),
        ("M4 + tract socioeconomics", f"black + C(band) + C(year) + C(division) + {SES}"),
    ]
    if hl is not None:
        layers.append(("M5 + tract homelessness", layers[-1][1] + " + log_homeless"))
    full = layers[-1][1]

    # 1. the main ladder: Black women against all other women
    cells = build_cells(located, pop, years, division, ses, hl, RACES, pool_other=True)
    cov = cells.groupby("black")["n"].sum()
    tot = located.groupby(located["race"] == "Black").size()
    coverage = {"Black": round(float(cov[1] / tot[True] * 100), 1), "Other": round(float(cov[0] / tot[False] * 100), 1)}
    print(f"model cells: {len(cells):,} (tract x race x age band x year), victims in cells: {int(cells['n'].sum()):,}; coverage by group: {coverage}")
    results = []
    for name, formula in layers:
        r = ratio(cells, formula)
        results.append({"model": name, **r, "controls": formula})
        print(f"{name:28s} Black women vs other women: {r['rate_ratio']:.2f}x  (95% CI {r['ci_low']:.2f} to {r['ci_high']:.2f})")

    # 2. the same, split by assault type
    by_type = {}
    for kind in ["simple", "aggravated"]:
        by_type[kind] = ratio(build_cells(located, pop, years, division, ses, hl, RACES, kinds=[kind], pool_other=True), full)
        print(f"fully adjusted, {kind:10s}: {by_type[kind]['rate_ratio']:.2f}x")

    # 3. each comparison group on its own: Black women against Hispanic, White and Asian women separately
    pairwise = {}
    for other in ["Hispanic", "White", "Asian"]:
        pc = build_cells(located, pop, years, division, ses, hl, ["Black", other])
        pairwise[other] = {"crude": ratio(pc, "black"), "adjusted": ratio(pc, full)}
        print(f"vs {other:8s} women: crude {pairwise[other]['crude']['rate_ratio']:.2f}x, fully adjusted {pairwise[other]['adjusted']['rate_ratio']:.2f}x "
              f"(95% CI {pairwise[other]['adjusted']['ci_low']:.2f} to {pairwise[other]['adjusted']['ci_high']:.2f})")

    # 4. homelessness sensitivity: swap the covariate definition
    sensitivity = {}
    if hl is not None:
        for col in [c for c in hl.columns if c != "geoid"]:
            sensitivity[col] = ratio(cells, layers[4][1] + f" + log_{col}")
            print(f"homelessness as {col:16s}: {sensitivity[col]['rate_ratio']:.2f}x")

    out = {"women_located": int(len(located)), "women_total": int(len(women)), "cells": int(len(cells)), "min_cell_pop": MIN_CELL_POP,
           "coverage": coverage, "age_bands": list(COARSE), "ladder": results, "fully_adjusted_by_type": by_type,
           "pairwise": pairwise, "homelessness_sensitivity": sensitivity, "homelessness_included": hl is not None,
           "ses_covariates": ["poverty rate", "log median household income", "unemployment rate", "renter share", "log population density"]}
    (DATA / "model_results.json").write_text(json.dumps(out, indent=1))
    print("wrote", DATA / "model_results.json")


if __name__ == "__main__":
    main()
