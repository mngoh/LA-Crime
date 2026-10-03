"""Does the gap replicate in LAPD's new records system, and how does intimate partner assault compare?

Two sources, no overlap in time:
  legacy  LAPD Crime Data from 2020 to 2024 (2nrs-mtv8), January 2020 to December 2023
  NIBRS   LAPD NIBRS Victims (gqf2-vm2j), June 2024 to August 2026. LAPD switched on March 7, 2024;
          March to May 2024 are excluded while volume ramped up, and the latest weeks while reports catch up.

Assaults on women are split the same way in both:
  general           legacy codes 624 (simple) and 230 (aggravated), the definition the rest of this repo uses;
                    NIBRS 13A/13B offenses that are not intimate partner, child, or officer victims
  intimate partner  legacy codes 626 and 236; NIBRS offenses labelled IPV, intimate partner, spouse,
                    cohabitant or dating relationship
Officer and child-abuse offenses are left out of both, as the legacy system coded them separately.
The NIBRS labels are not a one-to-one match for the legacy codes (NIBRS aggravated assault also covers
brandishing and attempted murder), so compare ratios between groups, not raw levels between systems.

Rates are women victims per 100,000 female residents per year, ACS 2020 to 2024 population.
Writes data/nibrs_comparison.json.  Run after scripts/compute_rates.py (reuses its cached ACS download).
"""
import json
import re
import urllib.parse
import urllib.request

from compute_rates import DATA, RACE, RACES, population

PORTAL = "https://data.lacity.org/resource"
LEGACY = {"624": "general", "230": "general", "626": "intimate", "236": "intimate"}
LEGACY_YEARS = 4.0
NIBRS_START, NIBRS_END = "2024-06-01T00:00:00", "2026-08-31T23:59:59"
NIBRS_YEARS = 27 / 12
NIBRS_RACE = {"Black/African American": "Black", "Black": "Black", "Hispanic": "Hispanic", "H - Hispanic": "Hispanic",
              "White/Caucasian": "White", "White": "White",
              **{k: "Asian" for k in ["Other Asian", "Asian Indian", "Korean", "Filipino", "Chinese", "Japanese",
                                      "Vietnamese", "Cambodian", "Laotian"]}}
IPV = re.compile(r"IPV|Intimate Partner|Spouse|Cohabitant|Dating", re.I)
EXCLUDE = re.compile(r"Peace Officer|Police|P\.O\.|Firefighter|Obstruct|Resist|Child|Elder.*Cruelty", re.I)


def soql(dataset, params):
    url = f"{PORTAL}/{dataset}.json?" + urllib.parse.urlencode({**params, "$limit": 50000})
    req = urllib.request.Request(url, headers={"User-Agent": "Los-Angeles-CA-Assault-Victim-Rates-by-Race-and-Sex-2020-2023 analysis (github.com/mngoh/Los-Angeles-CA-Assault-Victim-Rates-by-Race-and-Sex-2020-2023)"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def nibrs_kind(offenses):
    """Classify one victim's offense list; None if it holds no assault we compare."""
    assaults = [o for o in offenses.split(", ") if re.search(r"- 13[AB]\s*$", o)]
    assaults = [o for o in assaults if not EXCLUDE.search(o)]
    if not assaults:
        return None
    return "intimate" if any(IPV.search(o) for o in assaults) else "general"


def counts():
    """Women victims by source, kind and race."""
    out = {s: {k: {r: 0 for r in RACES} for k in ["general", "intimate"]} for s in ["legacy", "nibrs"]}
    rows = soql("2nrs-mtv8", {"$select": "crm_cd, vict_descent, count(*) as n", "$group": "crm_cd, vict_descent",
                              "$where": f"vict_sex = 'F' AND crm_cd in ({','.join(repr(c) for c in LEGACY)}) "
                                        "AND date_occ between '2020-01-01T00:00:00' and '2023-12-31T23:59:59'"})
    for r in rows:
        race = RACE.get(r.get("vict_descent"))
        if race:
            out["legacy"][LEGACY[r["crm_cd"]]][race] += int(r["n"])
    rows = soql("gqf2-vm2j", {"$select": "victimofslist, vict_descent, count(*) as n", "$group": "victimofslist, vict_descent",
                              "$where": f"vict_sex = 'F' AND date_occ between '{NIBRS_START}' and '{NIBRS_END}' "
                                        "AND (victimofslist like '%- 13A%' OR victimofslist like '%- 13B%')"})
    for r in rows:
        race, kind = NIBRS_RACE.get(r.get("vict_descent")), nibrs_kind(r.get("victimofslist", ""))
        if race and kind:
            out["nibrs"][kind][race] += int(r["n"])
    return out


def main():
    pop = population()["city"]
    n = counts()
    years = {"legacy": LEGACY_YEARS, "nibrs": NIBRS_YEARS}
    result = {"windows": {"legacy": "January 2020 to December 2023", "nibrs": "June 2024 to August 2026"}, "counts": n, "rates": {}, "ratios": {}, "intimate_share": {}}
    for s in n:
        result["rates"][s] = {}
        for kind in ["general", "intimate", "all"]:
            c = {r: (n[s]["general"][r] + n[s]["intimate"][r]) if kind == "all" else n[s][kind][r] for r in RACES}
            rates = {r: round(c[r] / pop[r]["F"] / years[s] * 1e5) for r in RACES}
            result["rates"][s][kind] = rates
            result["ratios"].setdefault(s, {})[kind] = {r: round(rates["Black"] / rates[r], 2) for r in RACES if r != "Black"}
        result["intimate_share"][s] = {r: round(n[s]["intimate"][r] / (n[s]["general"][r] + n[s]["intimate"][r]) * 100, 1) for r in RACES}
    (DATA / "nibrs_comparison.json").write_text(json.dumps(result, indent=1))
    for s in n:
        print(f"{s:6s} women's rates per 100,000/yr:", result["rates"][s])
        print(f"{s:6s} Black women's rate as a multiple of each group:", result["ratios"][s])
        print(f"{s:6s} intimate partner share of women's assaults:", result["intimate_share"][s])
    print("wrote", DATA / "nibrs_comparison.json")


if __name__ == "__main__":
    main()
