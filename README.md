# Assault victims in Los Angeles

Who gets assaulted in Los Angeles, as rates rather than counts. 100,946 LAPD assault reports from January 2020 to June 2023, by race, sex and police division, against ACS population.

**Live analysis:** https://mngoh.github.io/LA-Crime/

## Finding

Black women are assaulted at 1,803 per 100,000 residents a year: 3 times the rate of Hispanic women (598), 5.4 times White women (335), 17 times Asian women (106), and more often than Hispanic or White men. The gap is a higher victimization rate, not population share.

Black women outnumber Black men only among simple-assault victims (56.5% women). Across all assaults they are 45% of Black victims, still the highest female share of any group (37% to 40% elsewhere).

## Testing explanations

Women only, Black women against all other women.

- Age: standardized to one age mix the rates are 1,758 vs 596 (Hispanic), 328 (White) and 99 (Asian). Age explains none of the gap.
- Location: at other women's rate in each division Black women would be at 560 per 100,000, not 1,806. Where assaults happen explains part of it; inside every rated division the rate is still 2.5 to 5.6 times other women's.
- Type: 2.6 times Hispanic women for simple assault, 4.2 times for aggravated.
- Time: 1,818, 1,809, 1,876 and 1,618 (first half of 2023, annualized). It persists.
- Premises: nearly identical distributions (street 22% vs 19%, home 38% vs 35%).
- Weapons: a firearm in 12.4% of assaults on Black women vs 6.4% for other women.
- Reporting: not testable with LAPD data. If Black women report more or less often than other women, every rate moves.

After age, location and year, roughly a threefold gap remains, widest in aggravated and armed assaults. The data shows it; it does not explain it.

## The model

`scripts/model_gap.py` asks how much of the gap survives adjustment. Poisson rate models at the census-tract level, women only; each assault is geocoded to the tract it happened in, and the denominator is that tract's female residents of the same group and age band (ACS 2020 to 2024). Covers 81.6% of located Black women victims and 98.2% of other women; the rest were assaulted in tracts with no resident women of their group and age.

| Controls | Black women vs other women |
|---|---|
| group only | 3.37x |
| + age | 3.3x |
| + year | 3.3x |
| + division | 2.57x |
| + tract socioeconomics | 2.48x |
| + tract homelessness | 2.46x (95% CI 2.36 to 2.56) |

Fully adjusted, by type: simple assault 2.14x, aggravated assault 3.29x. About 38% of the crude excess is explained, almost all of it by where the assault happened; a gap of about 2.46 remains that none of the measured factors account for.

Each comparison group on its own (crude, then fully adjusted): Hispanic women 2.54x and 2.09x; White women 4.79x and 2.26x; Asian women 15.69x and 10.31x. Pooling other women averages across that spread.

Homelessness enters as a tract-level count from the 2024 LAHSA Homeless Count, built by `scripts/lahsa_tracts.py`. LAHSA publishes actual counts only and states that per-tract occupant estimates are not precise, so three definitions were tested: people counted plus one per dwelling (2.46x), people counted only (2.47x) and unsheltered only (2.45x). The choice does not matter. Not in the model: exposure away from home, reporting behavior, and anything about offenders or circumstances.

## Context

National victimization surveys, which include crimes never reported to police, point the same way: BJS data for 2005 put the rate of violence against Black women almost 50% higher than against White women, across strangers, acquaintances and partners ([Heimer et al., BJS-hosted](https://bjs.ojp.gov/sites/g/files/xyckuh236/files/media/document/heimer.pdf); [Harrell, Black Victims of Violent Crime, BJS 2007](https://bjs.ojp.gov/content/pub/pdf/bvvc.pdf)). The Los Angeles police-recorded gap is larger than that national figure.

## Caveats

- This shows what the data says, not why. Nothing here measures causes, offenders or circumstances.
- Reported crimes only. Willingness to report and police recording practice differ by group, area and time, so a higher rate can partly reflect more reporting.
- Exposure is not population. Rates divide by where people live, not where they spend their time.
- Residential denominators inflate rates in divisions with many visitors, workers or unhoused residents (Central above all).
- 8,621 victims with unknown race or sex are excluded. LAPD descent codes are officer-recorded and collapsed to four groups.
- Victims cover January 2020 to June 2023, including the pandemic; population is the ACS 2020 to 2024 five-year average.

## Method

- Victims: LAPD Crime Data from 2020 to Present, simple assault (battery) and aggravated assault, filtered in `0_data_cleaning.ipynb`. LAPD descent codes mapped to Black, Hispanic, White and Asian; 92,325 of 100,946 victims have known race and sex.
- Population: ACS 2020 to 2024 five-year estimates by census tract (via Census Reporter). 1,110 tracts inside the city were assigned to the 21 LAPD divisions by tract centroid using the city's division boundaries from LA GeoHub (11 fell outside).
- Rate = victims / residents / 3.5 years x 100,000. Cells under 2,000 residents are not rated.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/compute_rates.py   # counts, rates, hypothesis tests -> data/page_data.json (downloads ACS, tract centroids and division boundaries once)
python scripts/lahsa_tracts.py    # 2024 LAHSA count by tract -> data/external/lahsa_tracts.csv
python scripts/model_gap.py       # adjustment ladder -> data/model_results.json (downloads tract geometry and ACS socioeconomics once)
python scripts/build_page.py      # both JSON files -> index.html
```

Run from the repository root. The notebooks also expect to be run from the root.

## Layout

```
index.html                    the published page (Chart.js and Leaflet)
scripts/
  compute_rates.py            counts, rates and the six hypothesis tests -> data/page_data.json
  lahsa_tracts.py             2024 LAHSA Homeless Count by tract -> data/external/lahsa_tracts.csv
  model_gap.py                tract-level Poisson adjustment ladder -> data/model_results.json
  build_page.py               renders index.html from the two JSON files
data/
  eda_data.csv                simple assault (battery) victims, LAPD, Jan 2020 to Jun 2023
  eda_data_deadly.csv         aggravated assault victims, same window
  page_data.json              computed counts, rates and tests
  model_results.json          model output
  external/                   cached downloads (ACS, tract centroids and geometry, division boundaries, LAHSA workbook); not committed
notebooks/
  0_data_cleaning.ipynb       how the two victim files were cut from the raw LAPD download (2023)
  1_eda.ipynb, 1_eda_early.ipynb   exploratory analysis (2023)
  2_regression_experiment.ipynb    an exploratory regression, not used on the page
  functions/                  helper and plotting functions used by the notebooks
```
