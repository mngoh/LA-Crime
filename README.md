# LA Crime Analysis

Who are the victims of assault in Los Angeles? An analysis of LAPD crime data from 2020 to 2023, looking at assault victimization by race, sex and police division.

**Live analysis:** https://mngoh.github.io/LA-Crime/

## Key finding

Across 100,946 assault incidents, Black women are the only group in which female victims outnumber male victims: 56–70% of Black assault victims, depending on the division. The pattern holds across the 77th Street, Southeast, Southwest and Newton divisions, while Hispanic, White and Asian victims are roughly 55–60% male. The gap is widest in Southeast, where Black female victims (864) nearly double Black male victims (378).

These are reported crimes only, and the figures are raw victim counts, not population-adjusted rates.

## Data

LAPD crime data from the City of Los Angeles open data portal (data.lacity.org, dataset `2nrs-mtv8`), plus census data in `data/la_census.csv`.

## Contents

- `index.html`: the published analysis page
- `0_data_cleaning.ipynb`: cleaning the raw crime data
- `1_eda.py.ipynb`, `EDA.ipynb`: exploratory analysis
- `1_kmeans.py.ipynb`: early modelling experiments
- `functions/`: helper and plotting functions
- `data/`: cleaned datasets used by the notebooks
