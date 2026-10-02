"""Homelessness by census tract from the 2024 Greater Los Angeles Homeless Count.

LAHSA publishes tract-split counts as a workbook (https://www.lahsa.org/data). This
turns it into data/external/lahsa_tracts.csv with one row per tract: geoid, homeless.

LAHSA's tract file holds actual counts only. Its README says estimated occupants of
vehicles and tents "are not designed to be precise at the census tract level", so no
official per-tract person estimate exists. Three definitions are written so the
model can test whether the choice matters:
  homeless      people counted (street, safe parking, shelters) + one per vehicle, tent or makeshift shelter
  people_only   people counted, dwellings ignored
  unsheltered   street people + dwellings, shelters ignored
All enter the model on a log scale, as covariates.

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
    people = la[PEOPLE].fillna(0).sum(axis=1)
    dwellings = la[DWELLINGS].fillna(0).sum(axis=1)
    street_people = la[["totStreetSingAdult", "totStreetFamMem", "totSafeParkSingAdult", "totSafeParkFamMem"]].fillna(0).sum(axis=1)
    la["homeless"] = people + dwellings
    la["people_only"] = people
    la["unsheltered"] = street_people + dwellings
    out = la.groupby("geoid", as_index=False)[["homeless", "people_only", "unsheltered"]].sum()
    out.to_csv(EXT / "lahsa_tracts.csv", index=False)
    print(f"{len(out)} city tracts; people {int(people.sum()):,}, dwellings {int(dwellings.sum()):,}; wrote {EXT / 'lahsa_tracts.csv'}")


if __name__ == "__main__":
    main()
