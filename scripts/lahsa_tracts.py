"""Homelessness by census tract from the 2024 Greater Los Angeles Homeless Count.

LAHSA publishes tract-split counts as a workbook (https://www.lahsa.org/data). This
turns it into data/external/lahsa_tracts.csv with one row per tract: geoid, homeless.

"homeless" is a conservative exposure proxy, not LAHSA's official person estimate:
people counted on the street, in safe parking and in shelters, plus one person per
car, van, camper, tent or makeshift shelter observed. LAHSA applies larger
multipliers to dwellings; the model only uses this on a log scale, as a covariate.

Run:  python scripts/lahsa_tracts.py   then   python scripts/model_gap.py
"""
import pandas as pd

from compute_rates import EXT, fetch

WORKBOOK = "https://www.lahsa.org/item.ashx?id=9405-update-hc-2024-data-by-census-sub-tract.xlsx&dl=true"
PEOPLE = ["totStreetSingAdult", "totStreetFamMem", "totSafeParkSingAdult", "totSafeParkFamMem", "totSheltPeople"]
DWELLINGS = ["totCars", "totVans", "totCampers", "totTents", "totEncamp"]


def main():
    path = fetch(WORKBOOK, "lahsa_hc2024_by_census_subtract.xlsx")
    counts = pd.read_excel(path, sheet_name="Counts")
    la = counts[counts["LACity"] == 1].copy()
    # tract_split is the 6-digit tract code, sometimes with a split suffix such as 102103_q1 or 265524_r1.1
    la["geoid"] = "06037" + la["tract_split"].astype(str).str.extract(r"^(\d+)")[0].str.zfill(6)
    la["homeless"] = la[PEOPLE].fillna(0).sum(axis=1) + la[DWELLINGS].fillna(0).sum(axis=1)
    out = la.groupby("geoid", as_index=False)["homeless"].sum()
    out.to_csv(EXT / "lahsa_tracts.csv", index=False)
    print(f"{len(out)} city tracts, {int(out['homeless'].sum()):,} people and dwellings counted; wrote {EXT / 'lahsa_tracts.csv'}")


if __name__ == "__main__":
    main()
