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
