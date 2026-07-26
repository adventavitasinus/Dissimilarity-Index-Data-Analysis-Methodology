"""
UK Urban Ethnic Segregation Analysis (2021 Census)
====================================================

Computes two measures of residential ethnic clustering across urban
England and Wales:

  1. Adjacent-pair ethnic composition gradient (MSOA level)
  2. Index of Dissimilarity, D (LAD level), per Duncan & Duncan (1955)

See README.md for data sources and full methodology notes.

Usage:
    python analysis.py
"""

import geopandas as gpd
import pandas as pd

# ---------------------------------------------------------------------------
# Config — edit these paths if your downloaded files are named differently
# ---------------------------------------------------------------------------
ETHNICITY_CSV = "data/msoa_ethnicity_ts021.csv"
BOUNDARIES_GEOJSON = "data/msoa_boundaries_bgc.geojson"
RURAL_URBAN_CSV = "data/msoa_rural_urban.csv"

RUC_COLUMN = "Rural Urban flag"           # column name in your RUC file
ASIAN_PCT_COLUMN = "pct_asian"            # or rename after loading if needed
TOTAL_POP_COLUMN = "total_population"     # adjust to match your Nomis export

MIN_ASIAN_PCT_FOR_D = 5.0
HIGH_SEGREGATION_THRESHOLD = 0.6
MODERATE_SEGREGATION_THRESHOLD = 0.5

OUTPUT_DIR = "output"

# ---------------------------------------------------------------------------
# Stage 1: Load and merge
# ---------------------------------------------------------------------------
def load_data():
    boundaries = gpd.read_file(BOUNDARIES_GEOJSON)
    ethnicity = pd.read_csv(ETHNICITY_CSV)
    ruc = pd.read_csv(RURAL_URBAN_CSV)

    # NOTE: column names below assume ONS's standard export headers.
    # Inspect your actual files first — Nomis exports in particular vary
    # by which table/query you used — and adjust the merge keys/renames
    # accordingly. Printing df.columns for each source before merging is
    # the fastest way to catch a mismatch here.
    df = boundaries.merge(ethnicity, on="MSOA21CD").merge(ruc, on="MSOA21CD")

    if "pct_asian" not in df.columns:
        df["pct_asian"] = df["asian_count"] / df["total_population"] * 100

    df_urban = df[df["RUC11"].str.contains("Urban", case=False, na=False)].copy()
    return df_urban


# ---------------------------------------------------------------------------
# Stage 2: Adjacent-pair gradient
# ---------------------------------------------------------------------------
def compute_adjacent_pair_gradients(df_urban: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    For every pair of urban MSOAs sharing a boundary, compute the absolute
    difference in % Asian population. Uses a spatial index (.sindex) rather
    than a naive O(n^2) all-pairs comparison, since that's intractable at
    ~6,000+ urban MSOAs.
    """
    df_urban = df_urban.reset_index(drop=True)
    sindex = df_urban.sindex

    results = []
    seen_pairs = set()

    for idx, row in df_urban.iterrows():
        # candidate neighbours via spatial index bounding-box query, then
        # confirm true polygon adjacency with .touches()
        possible_matches_index = list(sindex.intersection(row.geometry.bounds))
        for match_idx in possible_matches_index:
            if match_idx == idx:
                continue
            pair_key = tuple(sorted((idx, match_idx)))
            if pair_key in seen_pairs:
                continue
            neighbour = df_urban.iloc[match_idx]
            if row.geometry.touches(neighbour.geometry):
                seen_pairs.add(pair_key)
                gradient = abs(row["pct_asian"] - neighbour["pct_asian"])
                results.append({
                    "area_a": row["MSOA21NM"],
                    "area_b": neighbour["MSOA21NM"],
                    "pct_asian_a": row["pct_asian"],
                    "pct_asian_b": neighbour["pct_asian"],
                    "gradient": gradient,
                })

    pairs_df = pd.DataFrame(results).sort_values("gradient", ascending=False).reset_index(drop=True)
    pairs_df["rank"] = pairs_df.index + 1
    pairs_df["percentile"] = 100 * (1 - pairs_df["rank"] / len(pairs_df))
    return pairs_df


# ---------------------------------------------------------------------------
# Stage 3: Index of Dissimilarity per LAD
# ---------------------------------------------------------------------------
def compute_dissimilarity_index(df_urban: pd.DataFrame) -> pd.DataFrame:
    """
    Index of Dissimilarity (Duncan & Duncan, 1955):

        D = 0.5 * sum_i | a_i/A - n_i/N |

    where a_i = Asian population of MSOA i, A = total Asian population of the LAD,
    n_i = non-Asian population of MSOA i, N = total non-Asian population of the LAD.

    D ranges 0 (perfect integration) to 1 (complete segregation).
    Conventional thresholds: >0.6 high segregation, <0.3 low segregation.

    LAD boundaries are approximated by matching the common MSOA name prefix
    (e.g. all "Bradford 0XX" MSOAs -> Bradford). This matches true LAD
    boundaries in all but a small number of edge cases -- see README Limitations.
    """
    df = df_urban.copy()
    df["lad_name"] = df["MSOA21NM"].str.extract(r"^(.*?)\s*\d")

    df["asian_pop"] = df["pct_asian"] / 100 * df["total_population"]
    df["non_asian_pop"] = df["total_population"] - df["asian_pop"]

    records = []
    for lad, group in df.groupby("lad_name"):
        A = group["asian_pop"].sum()
        N = group["non_asian_pop"].sum()
        if A == 0 or N == 0:
            continue
        D = 0.5 * (abs(group["asian_pop"] / A - group["non_asian_pop"] / N)).sum()
        total_pop = group["total_population"].sum()
        pct_asian_lad = 100 * A / total_pop
        records.append({
            "lad_name": lad,
            "dissimilarity_index": D,
            "total_population": total_pop,
            "pct_asian": pct_asian_lad,
            "excluded_low_denominator": pct_asian_lad < MIN_ASIAN_PCT_FOR_D,
        })

    d_df = pd.DataFrame(records).sort_values("dissimilarity_index", ascending=False).reset_index(drop=True)
    return d_df


# ---------------------------------------------------------------------------
# Stage 4: Summary
# ---------------------------------------------------------------------------
def write_summary(pairs_df: pd.DataFrame, d_df: pd.DataFrame):
    d_interpretable = d_df[~d_df["excluded_low_denominator"]]
    high_seg = d_interpretable[d_interpretable["dissimilarity_index"] > HIGH_SEGREGATION_THRESHOLD]
    moderate_seg = d_interpretable[d_interpretable["dissimilarity_index"] > MODERATE_SEGREGATION_THRESHOLD]

    lines = [
        f"Adjacent-pair gradient: n={len(pairs_df)}, "
        f"mean={pairs_df['gradient'].mean():.2f}, sd={pairs_df['gradient'].std():.2f}",
        f"Dissimilarity index (interpretable LADs only): n={len(d_interpretable)}, "
        f"mean={d_interpretable['dissimilarity_index'].mean():.3f}, "
        f"sd={d_interpretable['dissimilarity_index'].std():.3f}",
        f"LADs above {HIGH_SEGREGATION_THRESHOLD} (high segregation): {len(high_seg)}",
        f"LADs above {MODERATE_SEGREGATION_THRESHOLD} (moderate+): {len(moderate_seg)}",
        f"Total population in LADs above {MODERATE_SEGREGATION_THRESHOLD}: "
        f"{moderate_seg['total_population'].sum():,.0f}",
    ]
    with open(f"{OUTPUT_DIR}/summary_stats.txt", "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


def main():
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df_urban = load_data()
    pairs_df = compute_adjacent_pair_gradients(df_urban)
    d_df = compute_dissimilarity_index(df_urban)

    pairs_df.to_csv(f"{OUTPUT_DIR}/adjacent_pair_gradients.csv", index=False)
    d_df.to_csv(f"{OUTPUT_DIR}/dissimilarity_by_lad.csv", index=False)
    write_summary(pairs_df, d_df)


if __name__ == "__main__":
    main()
