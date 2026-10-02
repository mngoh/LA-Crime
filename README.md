# Assault victims in Los Angeles

Who gets assaulted in Los Angeles, as rates rather than counts. 100,946 LAPD assault reports from January 2020 to June 2023, by race, sex and police division, against ACS population.

**Live analysis:** https://mngoh.github.io/LA-Crime/

## Finding

Black women are assaulted at 1,803 per 100,000 residents a year: 3 times the rate of Hispanic women (598), 5.4 times White women (335), 17 times Asian women (106), and more often than Hispanic or White men. The gap is a higher victimization rate, not population share.

Black women outnumber Black men only among simple-assault victims (56.5% women). Across all assaults they are 45% of Black victims, still the highest female share of any group (37% to 40% elsewhere).

Reported crimes only. Rates use residential population, so divisions with many visitors or unhoused residents (Central) read high.

## Method

- Victims: LAPD Crime Data from 2020 to Present, simple assault (battery) and aggravated assault, filtered in `0_data_cleaning.ipynb`. LAPD descent codes mapped to Black, Hispanic, White and Asian; 92,325 of 100,946 victims have known race and sex.
- Population: ACS 2020 to 2024 five-year estimates by census tract (via Census Reporter). 1,110 tracts inside the city were assigned to the 21 LAPD divisions by tract centroid using the city's division boundaries from LA GeoHub (11 fell outside).
- Rate = victims / residents / 3.5 years x 100,000. Cells under 2,000 residents are not rated.

## Reproduce

```bash
pip install -r requirements.txt
python scripts/compute_rates.py   # counts + rates -> data/page_data.json (downloads ACS, tract centroids and division boundaries once)
python scripts/build_page.py      # data/page_data.json -> index.html
```

## Contents

- `index.html`: the published page (Chart.js and Leaflet, no build step beyond the scripts above)
- `scripts/compute_rates.py`, `scripts/build_page.py`: the pipeline behind the page
- `data/eda_data.csv`, `data/eda_data_deadly.csv`: simple and aggravated assault victims; `data/page_data.json`: computed counts and rates
- `0_data_cleaning.ipynb`: how the two victim files were cut from the raw LAPD download
- `1_eda.ipynb`, `1_eda_early.ipynb`: exploratory analysis from 2023
- `2_regression_experiment.ipynb`: an exploratory regression, not used on the page
- `functions/`: helper and plotting functions
