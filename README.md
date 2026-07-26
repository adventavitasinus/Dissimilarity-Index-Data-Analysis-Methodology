# UK Urban Ethnic Segregation Analysis (2021 Census)

Supporting data and code for the "Current Issues" section of *Progressive Nationalism*, published on [Substack link].

This repo computes two measures of residential ethnic clustering across urban England and Wales, using the 2021 Census:

1. **Adjacent-pair gradient** — for every pair of neighbouring urban MSOAs, the absolute difference in % "Asian, Asian British or Asian Welsh" population.
2. **Index of Dissimilarity (D)** — a standard segregation statistic (Duncan & Duncan, 1955) computed per local authority district (LAD).

The essay cites summary statistics and named examples (Wensley Fold/Witton, Manningham/Wrose, Washwood Heath/Nechells, Montrose Avenue/Stopsley) drawn directly from this pipeline's output. This repo lets anyone regenerate those numbers from public data rather than take them on trust.

## Data sources

All three inputs are public, free, and covered by the Open Government Licence v3.0. This repo does **not** redistribute the raw files (they're large and the license is best honoured by linking to the origin) — download them yourself from:

| Dataset | Source | Notes |
|---|---|---|
| Ethnic group by MSOA (Table TS021) | [Nomis](https://www.nomisweb.co.uk) or [ONS Census 2021 data download](https://www.ons.gov.uk/census) | Row per MSOA, counts by ethnic group |
| MSOA boundaries (Dec 2021, BGC V3) | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk) | Use the *Generalised Clipped* (20m) boundary set — smaller file, adequate for adjacency detection |
| Rural-Urban Classification (Table 1C) | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk) | Binary urban/rural flag per MSOA |

Place downloaded files in `data/` using these names (or edit the paths at the top of `analysis.py`):
```
data/msoa_ethnicity_ts021.csv
data/msoa_boundaries_bgc.geojson
data/msoa_rural_urban.csv
```

## Method summary

- Only **urban** MSOAs are analysed. Rural MSOAs have near-zero minority populations in most of the country and would flatten the gradient distribution toward zero, obscuring exactly the clustering the analysis is trying to detect.
- Adjacency is determined by polygon boundary contact (`geopandas.touches()`), accelerated with a spatial index (`.sindex`) rather than a naive O(n²) comparison.
- LAD-level aggregation for the dissimilarity index approximates LAD boundaries by matching the common MSOA name prefix (e.g. all `Bradford 0XX` MSOAs → Bradford). This matches true LAD boundaries in all but a small number of edge cases — see **Limitations** below.
- A minimum 5% Asian-population threshold is applied before interpreting D values, to avoid the index being driven by statistical noise in areas with very small minority populations (standard practice for dissimilarity indices — see Limitations).

Full formula and thresholds are in the essay's methodology section and reproduced in the docstring of `compute_dissimilarity_index()` in `analysis.py`.

## Reproducing the analysis

```bash
# environment
pip install -r requirements.txt

# run
python analysis.py
```

Outputs are written to `output/`:
- `adjacent_pair_gradients.csv` — all urban adjacent MSOA pairs with gradient, sorted descending
- `dissimilarity_by_lad.csv` — D statistic per urban LAD, with population and threshold-exclusion flag
- `summary_stats.txt` — the headline numbers quoted in the essay (mean/SD for both metrics, percentile rank of named case studies)

## Limitations (stated plainly, not just in a footnote)

- **Boundary generalisation.** The 20m-generalised boundary file can marginally undercount adjacency at complex, jagged borders. This doesn't bias the *median* of a ~14,600-pair distribution, but it means any single pair's inclusion/exclusion should be treated as approximate, not exact.
- **LAD approximation via name prefix.** A small number of MSOAs may be misassigned to the wrong LAD where naming doesn't cleanly follow administrative boundaries. Spot-checked against known LAD boundaries for the districts named in the essay; not exhaustively verified nationwide.
- **5% threshold is a convention, not a law of statistics.** It follows common practice in segregation-index literature to avoid small-denominator noise, but the exact cutoff (5% vs. 3% vs. 10%) is a judgment call and changes which LADs appear in the "high segregation" count at the margin (see the South Derbyshire case, excluded despite D = 0.654).
- **This is original analysis, not peer-reviewed.** It has not been checked by an independent analyst. Treat findings accordingly, and please open an issue if you spot an error in the code or method — corrections will be noted in the commit history.
- **Software versions:** see `requirements.txt`. If you're citing this repo, cite the tagged release (below), not the live `main` branch, since dependencies and code may be updated over time.

## Citing this repo

Please cite the tagged release, not a live branch, so the linked version can't change under you:

```
[Author]. (2026). UK Urban Ethnic Segregation Analysis (2021 Census) [Software], v1.0.
https://github.com/[username]/uk-segregation-analysis/releases/tag/v1.0
```

## License

Code in this repo is released under the MIT License (see `LICENSE`). Underlying ONS/Nomis data is Crown Copyright under the Open Government Licence v3.0 and is not redistributed here — see data source links above.
