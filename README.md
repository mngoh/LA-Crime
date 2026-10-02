# Assault victims in Los Angeles

Who gets assaulted in Los Angeles, as rates rather than counts. 174,827 LAPD assault reports from January 2020 to December 2023, intimate partner assault included, by race, sex and police division, against ACS population.

**Live analysis:** https://mngoh.github.io/LA-Crime/

The method is packaged as reusable Claude Code skills in [disparity-kit](https://github.com/mngoh/disparity-kit).

## Finding

Black women are assaulted at 3,544 per 100,000 residents a year: 2.9 times the rate of Hispanic women (1,240), 5.7 times White women (622), 18.4 times Asian women (193), and more often than the men of any group, Black men (2,894) included. The gap is a higher victimization rate, not population share. After adjusting for age, location, neighborhood and homelessness it is still about 2 times Hispanic or White women's.

Black women are 56% of Black assault victims, the highest female share of any group (47% to 51% elsewhere), and 65.5% of Black simple-assault victims.

## Testing explanations

Women only, Black women against all other women.

- Age: standardized to one age mix the rates are 3,468 vs 1,231 (Hispanic), 618 (White) and 182 (Asian). Age explains none of the gap.
- Location: at other women's rate in each division Black women would be at 1,129 per 100,000, not 3,548. Where assaults happen explains part of it; inside every rated division the rate is still 2.37 to 5.15 times other women's.
- Type: 2.5 times Hispanic women for simple assault, 4.0 times for aggravated.
- Time: 3,491, 3,564, 3,581 and 3,539 from 2020 to 2023. It persists.
- Premises: nearly identical distributions (home 49% vs 51%, street 20% vs 16%).
- Weapons: a firearm in 7.8% of assaults on Black women vs 3.9% for other women.
- Reporting: not testable with LAPD data. If Black women report more or less often than other women, every rate moves.

After age, location and year, roughly a threefold gap remains, widest in aggravated and armed assaults. The data shows it; it does not explain it.

## The model

`scripts/model_gap.py` asks how much of the gap survives adjustment. Poisson rate models at the census-tract level, women only; each assault is geocoded to the tract it happened in, and the denominator is that tract's female residents of the same group and age band (ACS 2020 to 2024). Covers 82.0% of located Black women victims and 98.3% of other women; the rest were assaulted in tracts with no resident women of their group and age.

| Controls | Black women vs other women |
|---|---|
| group only | 3.31x |
| + age | 3.25x |
| + year | 3.25x |
| + division | 2.58x |
| + tract socioeconomics | 2.5x |
| + tract homelessness | 2.48x (95% CI 2.39 to 2.57) |

Fully adjusted, by type: simple assault 2.22x, aggravated assault 3.29x. About 36% of the crude excess is explained, almost all of it by where the assault happened; a gap of about 2.48 remains that none of the measured factors account for.

Each comparison group on its own (crude, then fully adjusted): Hispanic women 2.41x and 2.08x; White women 5.12x and 2.44x; Asian women 16.68x and 10.71x. Pooling other women averages across that spread.

Homelessness enters as a tract-level count from the 2024 LAHSA Homeless Count, built by `scripts/lahsa_tracts.py`. LAHSA publishes actual counts only and states that per-tract occupant estimates are not precise, so three definitions were tested: people counted plus one per dwelling (2.48x), people counted only (2.49x) and unsheltered only (2.47x). The choice does not matter. Not in the model: exposure away from home, reporting behavior, and anything about offenders or circumstances.

## A second records system, and intimate partner assault

`scripts/compare_nibrs.py`, women only, per 100,000 residents a year.

- **Replication.** LAPD moved to NIBRS in March 2024. In June 2024 to August 2026, Black women's assault rate is 2.8x Hispanic women's and 6.01x White women's, against 2.86x and 5.7x in 2020 to 2023. The Asian comparison moved most (18.36x to 11.96x).
- **Intimate partner assault** (old codes 626 and 236) is nearly half of assaults on women in every group (47.5% Black, 49.7% Hispanic, 45.0% White, 43.9% Asian). Black women's partner assault rate is 1,685, 2.73x Hispanic and 6.02x White women's; without partner assault the ratios are 2.98x and 5.44x. The gap is the same size either way.

NIBRS assaults are offense codes 13A and 13B, classed as intimate partner by their offense label; officer and child victims are excluded in both systems. NIBRS labels do not map one-to-one to the old codes, so compare ratios between groups, not levels between systems.

## Context

National victimization surveys, which include crimes never reported to police, point the same way: BJS data for 2005 put the rate of violence against Black women almost 50% higher than against White women, across strangers, acquaintances and partners ([Heimer et al., BJS-hosted](https://bjs.ojp.gov/sites/g/files/xyckuh236/files/media/document/heimer.pdf); [Harrell, Black Victims of Violent Crime, BJS 2007](https://bjs.ojp.gov/content/pub/pdf/bvvc.pdf)). The Los Angeles police-recorded gap is larger than that national figure.

## Caveats

- This shows what the data says, not why. Nothing here measures causes, offenders or circumstances.
- Reported crimes only. Willingness to report and police recording practice differ by group, area and time, so a higher rate can partly reflect more reporting.
- Reports, not people. A woman assaulted twice counts twice, so rates are not the share of women assaulted.
- Race is officer-recorded; the population is Black alone. LA has 24% more people who are Black alone or in combination. If multiracial victims are recorded as Black, the worst case lowers the ratios to about 2.3 times Hispanic and 4.6 times White women.
- Missing race is uneven: victims with unknown or "Other" race cluster where few Black residents live. Spread like known victims in each division, the ratios move from 2.86x to 2.83x (Hispanic) and 5.7x to 5.46x (White).
- Controls are not neutral: neighborhood, income and housing are shaped by segregation, so a gap that shrinks after them is located, not explained away.
- The Asian comparison moved 35% between records systems and is left out of the headline.
- Exposure is not population. Rates divide by where people live, not where they spend their time.
- Residential denominators inflate rates in divisions with many visitors, workers or unhoused residents (Central above all).
- Covers simple and aggravated assault including intimate partner assault (codes 624, 626, 230, 236); assaults on police, child abuse and sexual battery are left out. 13,084 victims with unknown race or sex are excluded. LAPD descent codes are officer-recorded and collapsed to four groups.
- Victims cover January 2020 to December 2023, including the pandemic; population is the ACS 2020 to 2024 five-year average.

## Method

- Victims: LAPD Crime Data from 2020 to 2024 (the pre-NIBRS system), simple assault (codes 624 and 626, intimate partner) and aggravated assault (230 and 236), downloaded by `scripts/fetch_victims.py` with no imputation. The window stops at December 2023, the last full year before LAPD's March 2024 switch to NIBRS. LAPD descent codes mapped to Black, Hispanic, White and Asian; 161,743 of 174,827 victims have known race and sex.
- Population: ACS 2020 to 2024 five-year estimates by census tract (via Census Reporter). 1,110 tracts inside the city were assigned to the 21 LAPD divisions by tract centroid using the city's division boundaries from LA GeoHub (11 fell outside).
- Rate = victims / residents / 4 years x 100,000. Cells under 2,000 residents are not rated.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/fetch_victims.py    # LAPD assault victims 2020 to 2023, partner assault included -> data/eda_data*.csv
python scripts/compute_rates.py   # counts, rates, hypothesis tests -> data/page_data.json (downloads ACS, tract centroids and division boundaries once)
python scripts/lahsa_tracts.py    # 2024 LAHSA count by tract -> data/external/lahsa_tracts.csv
python scripts/model_gap.py       # adjustment ladder -> data/model_results.json (downloads tract geometry and ACS socioeconomics once)
python scripts/compare_nibrs.py   # NIBRS replication and intimate partner assault -> data/nibrs_comparison.json
python scripts/build_page.py      # the JSON files -> index.html
```

Run from the repository root. The notebooks also expect to be run from the root.

## Layout

```
index.html                    the published page (Chart.js and Leaflet)
scripts/
  fetch_victims.py            LAPD assault victims, Jan 2020 to Dec 2023 -> data/eda_data*.csv
  compute_rates.py            counts, rates and the six hypothesis tests -> data/page_data.json
  lahsa_tracts.py             2024 LAHSA Homeless Count by tract -> data/external/lahsa_tracts.csv
  model_gap.py                tract-level Poisson adjustment ladder -> data/model_results.json
  compare_nibrs.py            NIBRS replication and intimate partner assault -> data/nibrs_comparison.json
  build_page.py               renders index.html from the JSON files
data/
  eda_data.csv                simple assault (battery) victims, LAPD, Jan 2020 to Dec 2023
  eda_data_deadly.csv         aggravated assault victims, same window
  page_data.json              computed counts, rates and tests
  model_results.json          model output
  nibrs_comparison.json       NIBRS and intimate partner comparison
  external/                   cached downloads (ACS, tract centroids and geometry, division boundaries, LAHSA workbook); not committed
notebooks/
  0_data_cleaning.ipynb       the original 2023 cleaning, superseded by scripts/fetch_victims.py
  1_eda.ipynb, 1_eda_early.ipynb   exploratory analysis (2023)
  2_regression_experiment.ipynb    an exploratory regression, not used on the page
  functions/                  helper and plotting functions used by the notebooks
```
