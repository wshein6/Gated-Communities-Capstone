"""
compare_by_binary.py

Compare the physical size of vector features between the two groups of a
binary variable, in an arbitrary vector file.

Built to be pointed at a file you have not seen yet, including one holding
several kinds of urban element at once (building footprints, parks, road
centrelines, transit stops) rather than a single homogeneous layer.

    # look at the file first -- no --var needed
    python compare_by_binary.py --input city.geojson --inspect

    # then run the comparison
    python compare_by_binary.py --input city.geojson --var is_europe
    python compare_by_binary.py --input city.geojson --var in_core --element-col fclass --plot


WHAT IT DOES
------------
Splits the file into STRATA and runs a separate comparison inside each,
rather than one comparison over everything. Two things define a stratum:

  * Geometry family, always. Polygons are compared on area, lines on
    length, points have no size at all. Pooling a park's area with a
    road's length is meaningless, so the script never does it.
  * An element-type column, if you give one with --element-col (or ask
    for --element-auto). Parks are compared with parks, roads with roads.

This matters beyond tidiness. If the binary flag correlates with the MIX
of element types -- say the flagged areas are road-heavy and the
unflagged ones park-heavy -- then a pooled comparison measures
composition, not size, and can point the opposite way from every
within-type comparison. That is Simpson's paradox, and it is the normal
case in mixed urban data. The script tests for it: it reports the element
mix in each group, runs a chi-square on the contingency table, and warns
when the mix differs.

Because stratifying means running many tests, p-values across strata are
corrected with Benjamini-Hochberg FDR and reported as q-values. Test 30
element types and one or two will clear p<0.05 by chance alone.


TWO METHOD NOTES
----------------
1. Sizes are RECOMPUTED from geometry in an equal-area projection
   (EPSG:6933 by default), never read from an existing area/length
   column. Those columns are computed in whatever projection the file's
   author used; comparing them across groups spanning different latitudes
   compares projections, not places.

2. Feature sizes are heavily right-skewed. The headline test is a Welch
   t-test ON LOGGED sizes, reported as a multiplicative ratio ("1.8x
   larger"). A t-test on raw sizes is driven by the largest few features
   -- on a test case with identical medians and different spread, the raw
   test returns p = 3e-12 while the log test correctly returns p = 0.27.
   Mann-Whitney (rank-based) and Kolmogorov-Smirnov (whole-distribution)
   run alongside; when KS rejects and Mann-Whitney does not, the groups
   differ in distribution SHAPE rather than level, and the script says so.
   Medians and quantiles are printed before means for the same reason.


ARGUMENTS
---------
  --input          any GDAL-readable vector file (GeoJSON, GPKG,
                   shapefile, .zip of a shapefile, FlatGeobuf, ...)
  --inspect        describe the file and exit; suggests which columns
                   look like binary flags and which look like element
                   types. Use this on a file you have not seen.
  --var            the binary grouping column. Accepts 1/0, True/False,
                   yes/no, Y/N, t/f.
  --true-value     for a non-binary column, the value defining group 1
                   (--var continent --true-value Europe)
  --layer          layer name, for multi-layer files
  --element-col    column of element types to stratify within
  --element-auto   try to detect that column automatically
  --measure        auto (default) | area | perimeter | length | vertices
  --by             a further breakdown column (e.g. country_iso)
  --min-n          minimum features per group in a stratum (default 8)
  --no-pooled      suppress the pooled all-features comparison
  --plot           write log-scale plots
  --crs            override the equal-area CRS used for measurement
  --outdir         output directory (default output/comparisons)

  
REQUIRED EXTENSIONS
-------
pip install geopandas pandas numpy scipy matplotlib

OUTPUTS
-------
  all_comparisons_{var}.csv   one row per stratum: n, medians, ratio,
                              p-values, BH q-value -- the main table
  composition_{var}.csv       element mix by group + chi-square
  summary_{var}_{stratum}.csv per-stratum descriptive statistics
  tests_{var}_{stratum}.csv   per-stratum test statistics
  by_{by}_{var}_{stratum}.csv optional breakdown
  compare_{var}_{stratum}.png optional plots

"""

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy import stats

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = Path("output/comparisons_main")

# Equal-area projection for all area / length computation. EPSG:6933
# (NSIDC EASE-Grid 2.0 Global) is equal-area and global, so a polygon in
# Oslo and a polygon in Lagos are measured on the same footing.
DEFAULT_EQUAL_AREA_CRS = "EPSG:6933"

TRUE_TOKENS = {"1"}
FALSE_TOKENS = {"0"}

MEASURE_UNITS = {
    "area": "km2",
    "perimeter": "km",
    "length": "km",
    "vertices": "count",
}

# Which measure is meaningful for which geometry family.
FAMILY_DEFAULT_MEASURE = {
    "polygon": "area",
    "line": "length",
    "point": None,          # points have no size
}
FAMILY_ALLOWED_MEASURES = {
    "polygon": {"area", "perimeter", "length", "vertices"},
    "line": {"length", "vertices"},
    "point": {"vertices"},
}

GEOM_FAMILY = {
    "Polygon": "polygon", "MultiPolygon": "polygon",
    "LineString": "line", "MultiLineString": "line", "LinearRing": "line",
    "Point": "point", "MultiPoint": "point",
}

# Name hints used by --element-auto and by --inspect's suggestions.
ELEMENT_NAME_HINTS = (
    "fclass", "feature_type", "featuretype", "element", "element_type",
    "type", "class", "category", "kind", "landuse", "amenity", "highway",
    "building", "natural", "leisure", "layer", "subtype", "use", "code",
)

ALPHA = 0.05


# ---------------------------------------------------------------------------
# LOADING
# ---------------------------------------------------------------------------
def list_layers(path):
    try:
        return list(gpd.list_layers(path)["name"])
    except Exception:
        try:
            import fiona
            return list(fiona.listlayers(path))
        except Exception:
            return []


def repair_gpkg_feature_count(path):
    """
    A GeoPackage whose gpkg_ogr_contents.feature_count is 0 reads as an
    EMPTY layer in GDAL/GeoPandas/QGIS even though the table is full.
    Some writers leave the counter stale. Detect it and say so, since the
    alternative is a silent zero-feature run.
    """
    if Path(path).suffix.lower() != ".gpkg":
        return
    try:
        import sqlite3
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = con.execute("SELECT table_name, feature_count "
                           "FROM gpkg_ogr_contents").fetchall()
        stale = []
        for table, count in rows:
            if count == 0:
                real = con.execute(
                    f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                if real > 0:
                    stale.append((table, real))
        con.close()
        if stale:
            print("WARNING: this GeoPackage reports 0 features for layer(s) "
                  f"{[t for t, _ in stale]} but the table(s) actually hold "
                  f"{[n for _, n in stale]} rows.")
            print("         gpkg_ogr_contents.feature_count is stale. GDAL, "
                  "GeoPandas and QGIS will all see an empty layer.")
            print("         Fix it at the source with:")
            for table, n in stale:
                print(f'           UPDATE gpkg_ogr_contents SET feature_count='
                      f'(SELECT COUNT(*) FROM "{table}") '
                      f'WHERE table_name=\'{table}\';')
    except Exception:
        pass


def load_features(input_path, layer=None):
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"'{input_path}' not found.")

    repair_gpkg_feature_count(input_path)

    layers = list_layers(input_path)
    if layer is not None:
        if layers and layer not in layers:
            raise ValueError(f"Layer '{layer}' not in file. Layers: {layers}")
        gdf = gpd.read_file(input_path, layer=layer)
    elif len(layers) > 1:
        print(f"File has multiple layers: {layers}")
        print(f"  No --layer given, using the first: '{layers[0]}'")
        gdf = gpd.read_file(input_path, layer=layers[0])
    else:
        gdf = gpd.read_file(input_path)

    if len(gdf) == 0:
        raise ValueError("Input has zero features.")
    if gdf.geometry.isna().all():
        raise ValueError("Input has no usable geometry.")

    if gdf.crs is None:
        print("WARNING: input has no CRS. Assuming EPSG:4326 (lon/lat degrees). "
              "If it is actually projected, pass the correct CRS upstream.")
        gdf = gdf.set_crs("EPSG:4326")

    print(f"Loaded {input_path.name}: {len(gdf):,} features, CRS {gdf.crs.to_string()}")
    if len(gdf) > 500_000:
        print(f"  NOTE: {len(gdf):,} features. Measurement and plotting may be slow.")
    return gdf


def clean_geometry(gdf):
    """Drop empty/missing geometry, repair invalid, explode collections."""
    n0 = len(gdf)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    if len(gdf) < n0:
        print(f"  Dropped {n0 - len(gdf)} features with missing or empty geometry.")

    has_collection = (gdf.geometry.geom_type == "GeometryCollection").any()
    if has_collection:
        n_before = len(gdf)
        gdf = gdf.explode(index_parts=False).reset_index(drop=True)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        print(f"  Exploded GeometryCollections: {n_before} -> {len(gdf)} features.")

    invalid = ~gdf.geometry.is_valid
    n_invalid = int(invalid.sum())
    if n_invalid:
        print(f"  Repairing {n_invalid} invalid geometries (make_valid).")
        try:
            gdf.loc[invalid, gdf.geometry.name] = gdf.loc[invalid].geometry.make_valid()
        except AttributeError:
            gdf.loc[invalid, gdf.geometry.name] = gdf.loc[invalid].geometry.buffer(0)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]

    gdf["_family"] = gdf.geometry.geom_type.map(GEOM_FAMILY).fillna("other")
    counts = gdf["_family"].value_counts().to_dict()
    print(f"  Geometry families: {counts}")
    return gdf


# ---------------------------------------------------------------------------
# INSPECTION -- for a file you have not seen
# ---------------------------------------------------------------------------
def binary_candidates(gdf, geom_name):
    """Columns that could serve as --var, with how they would be read."""
    out = []
    for col in gdf.columns:
        if col == geom_name or col.startswith("_"):
            continue
        s = gdf[col].dropna()
        if s.empty:
            continue
        distinct = pd.unique(s)
        if len(distinct) != 2:
            continue
        numeric = pd.to_numeric(s, errors="coerce")
        if numeric.notna().all() and set(np.unique(numeric)) <= {0.0, 1.0}:
            how = "numeric 0/1 -- works directly"
        else:
            toks = set(str(v).strip().casefold() for v in distinct)
            if toks <= (TRUE_TOKENS | FALSE_TOKENS):
                how = "recognised tokens -- works directly"
            else:
                vals = sorted(str(v) for v in distinct)
                how = f"needs --true-value (values: {vals})"
        counts = s.value_counts().to_dict()
        out.append({"column": col, "usage": how, "counts": counts})
    return out


def element_candidates(gdf, geom_name, max_distinct=60):
    """Columns that could serve as --element-col."""
    out = []
    for col in gdf.columns:
        if col == geom_name or col.startswith("_"):
            continue
        s = gdf[col].dropna()
        if s.empty:
            continue
        n_distinct = s.nunique()
        if not (2 <= n_distinct <= max_distinct):
            continue
        numeric = pd.to_numeric(s, errors="coerce")
        looks_numeric_continuous = numeric.notna().all() and n_distinct > 20
        if looks_numeric_continuous:
            continue
        name_hit = any(h in col.lower() for h in ELEMENT_NAME_HINTS)
        coverage = len(s) / len(gdf)
        score = (2.0 if name_hit else 0.0) + coverage - abs(np.log10(max(n_distinct, 2))) * 0.3
        out.append({
            "column": col,
            "n_distinct": int(n_distinct),
            "coverage": round(coverage, 3),
            "name_hint": name_hit,
            "top_values": s.value_counts().head(6).to_dict(),
            "_score": score,
        })
    return sorted(out, key=lambda r: -r["_score"])


def inspect(gdf, geom_name):
    print("\n" + "=" * 74)
    print("FILE INSPECTION")
    print("=" * 74)

    print(f"\nFeatures: {len(gdf):,}")
    fam = gdf["_family"].value_counts()
    for family, n in fam.items():
        measure = FAMILY_DEFAULT_MEASURE.get(family)
        note = f"compared on {measure}" if measure else "NO size measure (points)"
        print(f"  {family:<9} {n:>8,}   {note}")

    data_cols = [c for c in gdf.columns
                 if c != geom_name and not c.startswith("_")]
    print(f"\nColumns ({len(data_cols)} non-geometry):")
    for col in data_cols:
        s = gdf[col]
        nn = int(s.notna().sum())
        print(f"  {col:<28} {str(s.dtype):<10} {nn:>8,} non-null, "
              f"{s.nunique():>6,} distinct")

    bins = binary_candidates(gdf, geom_name)
    print("\nCandidate --var columns (exactly 2 distinct values):")
    if bins:
        for b in bins:
            print(f"  --var {b['column']}")
            print(f"      {b['usage']}")
            print(f"      counts: {b['counts']}")
    else:
        print("  none found. A flag may need building first, e.g.")
        print("    gdf['is_core'] = (gdf['dist_km'] < 5).astype(int)")
        print("  or use --true-value on a categorical column.")

    els = element_candidates(gdf, geom_name)
    print("\nCandidate --element-col columns (categorical, 2-60 values):")
    if els:
        for e in els[:6]:
            flag = " <- name suggests an element type" if e["name_hint"] else ""
            print(f"  --element-col {e['column']}  "
                  f"({e['n_distinct']} values, {e['coverage']:.0%} coverage){flag}")
            print(f"      top: {e['top_values']}")
    else:
        print("  none found. Comparisons will be stratified by geometry family only.")

    print("\nSuggested next command:")
    var = bins[0]["column"] if bins else "YOUR_FLAG"
    cmd = f"  python compare_by_binary.py --input <file> --var {var}"
    if els:
        cmd += f" --element-col {els[0]['column']}"
    print(cmd + " --plot")
    print("=" * 74)


# ---------------------------------------------------------------------------
# MEASUREMENT
# ---------------------------------------------------------------------------
def count_vertices(geom):
    if geom is None or geom.is_empty:
        return 0
    try:
        return len(geom.get_coordinates())
    except Exception:
        from shapely.geometry import mapping

        def walk(obj):
            if isinstance(obj, (list, tuple)):
                if obj and isinstance(obj[0], (int, float)):
                    return 1
                return sum(walk(o) for o in obj)
            return 0

        return walk(mapping(geom).get("coordinates", []))


def resolve_measure(family, requested):
    """Pick the measure for a geometry family, or None if there isn't one."""
    if requested == "auto":
        return FAMILY_DEFAULT_MEASURE.get(family)
    if requested not in FAMILY_ALLOWED_MEASURES.get(family, set()):
        return None
    return requested


def compute_measure(gdf, measure, equal_area_crs):
    """
    Recompute the size measure from geometry in an equal-area projection.

    Deliberately ignores any pre-existing area/length column: those are
    computed in whatever CRS the file's author used, and comparing them
    across groups at different latitudes compares projections.
    """
    if measure == "vertices":
        values = gdf.geometry.apply(count_vertices).astype(float)
    else:
        projected = gdf.to_crs(equal_area_crs)
        if measure == "area":
            values = projected.geometry.area / 1e6              # m2 -> km2
        elif measure in ("perimeter", "length"):
            values = projected.geometry.length / 1e3            # m -> km
        else:
            raise ValueError(f"Unknown measure '{measure}'")

    out = gdf.copy()
    out["_size"] = values.replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
    n_bad = int((out["_size"].isna() | (out["_size"] <= 0)).sum())
    if n_bad:
        print(f"    Dropping {n_bad} features with missing or non-positive {measure}.")
    return out[out["_size"].notna() & (out["_size"] > 0)]


# ---------------------------------------------------------------------------
# GROUPING VARIABLE
# ---------------------------------------------------------------------------
def coerce_binary(series, var_name, true_value=None):
    """Map a column onto {1, 0}. NaN marks rows that could not be mapped."""
    if true_value is not None:
        target_num = pd.to_numeric(pd.Series([str(true_value).strip()]),
                                   errors="coerce").iloc[0]
        col_num = pd.to_numeric(series, errors="coerce")
        if pd.notna(target_num) and col_num.notna().any():
            matched = (col_num == target_num).fillna(False)
            present = col_num.notna() | series.notna()
        else:
            raw = series.astype("string").str.strip()
            matched = (raw.str.casefold()
                       == str(true_value).strip().casefold()).fillna(False)
            present = raw.notna()

        out = pd.Series(np.where(matched.to_numpy(), 1.0, 0.0),
                        index=series.index, dtype=float)
        out[~present.to_numpy()] = np.nan
        n1 = int((out == 1).sum())
        if n1 == 0:
            raise ValueError(
                f"No rows have '{var_name}' == '{true_value}'. Distinct values: "
                f"{sorted(series.dropna().astype(str).unique())[:12]}"
            )
        print(f"  '{var_name}' == '{true_value}' -> group 1 ({n1:,} features), "
              f"everything else -> group 0")
        return out

    numeric = pd.to_numeric(series, errors="coerce")
    non_null = numeric.dropna()
    if len(non_null) > 0:
        distinct = np.unique(non_null)
        if set(distinct) <= {0.0, 1.0}:
            out = numeric.astype(float)
            unmapped = int(series.notna().sum() - numeric.notna().sum())
            if unmapped:
                print(f"  WARNING: {unmapped} rows of '{var_name}' were not "
                      f"numeric and are excluded.")
            return out
        if len(distinct) > 2:
            # A count or continuous column. Treating its 0s and 1s as the
            # two groups would silently throw away every other row.
            raise ValueError(
                f"'{var_name}' is numeric with {len(distinct)} distinct values "
                f"(e.g. {', '.join(str(v) for v in distinct[:6])}...), not a 0/1 "
                f"flag. Treating its 0s and 1s as the groups would silently drop "
                f"every other row. Pass --true-value to define group 1 explicitly, "
                f"or build a proper binary column first "
                f"(e.g. high = {var_name} >= median)."
            )

    raw = series.astype("string").str.strip().str.casefold()
    out = pd.Series(np.nan, index=series.index, dtype=float)
    out[raw.isin(TRUE_TOKENS)] = 1.0
    out[raw.isin(FALSE_TOKENS)] = 0.0

    unmapped_mask = series.notna() & out.isna()
    n_unmapped = int(unmapped_mask.sum())
    if n_unmapped:
        bad = sorted(series[unmapped_mask].astype(str).unique())[:8]
        print(f"  WARNING: {n_unmapped} rows of '{var_name}' are not recognisably "
              f"binary and are excluded: {bad}")
    if out.notna().sum() == 0:
        raise ValueError(
            f"Could not interpret '{var_name}' as binary. Distinct values: "
            f"{sorted(series.dropna().astype(str).unique())[:12]}. "
            f"Use --true-value to pick which value is group 1."
        )
    return out


def prepare_groups(gdf, var, true_value=None):
    if var not in gdf.columns:
        cols = [c for c in gdf.columns
                if c != gdf.geometry.name and not c.startswith("_")]
        raise KeyError(f"Column '{var}' not in input. Available: {cols}\n"
                       f"Run with --inspect to see which columns look usable.")

    gdf = gdf.copy()
    gdf["_group"] = coerce_binary(gdf[var], var, true_value=true_value)
    gdf = gdf[gdf["_group"].notna()]

    n1 = int((gdf["_group"] == 1).sum())
    n0 = int((gdf["_group"] == 0).sum())
    if true_value is None:
        lab1, lab0 = f"{var}=1", f"{var}=0"
    else:
        lab1, lab0 = f"{var}=={true_value}", f"{var}!={true_value}"
    print(f"  Group 1 ({lab1}): {n1:,} features | Group 0 ({lab0}): {n0:,} features")
    if n1 == 0 or n0 == 0:
        raise ValueError(f"One group is empty ({n1} and {n0}). Nothing to compare.")
    return gdf


# ---------------------------------------------------------------------------
# COMPOSITION / CONFOUNDING CHECK
# ---------------------------------------------------------------------------
def composition_check(gdf, var, element_col=None):
    """
    Does the binary flag correlate with WHICH KIND of feature is present?

    If it does, a pooled size comparison is partly measuring composition.
    Mixed urban files are the normal case for this: flagged areas that are
    road-heavy and unflagged areas that are park-heavy will differ in
    "average feature size" for reasons that have nothing to do with size.
    """
    key_parts = ["_family"] + ([element_col] if element_col else [])
    gdf = gdf.copy()
    gdf["_stratum_label"] = gdf[key_parts].astype(str).agg(" / ".join, axis=1)

    tab = pd.crosstab(gdf["_stratum_label"], gdf["_group"])
    for g in (0.0, 1.0):
        if g not in tab.columns:
            tab[g] = 0
    tab = tab[[0.0, 1.0]]
    tab.columns = ["n_group_0", "n_group_1"]

    out = tab.reset_index().rename(columns={"_stratum_label": "stratum"})
    tot0 = max(out["n_group_0"].sum(), 1)
    tot1 = max(out["n_group_1"].sum(), 1)
    out["share_group_0"] = out["n_group_0"] / tot0
    out["share_group_1"] = out["n_group_1"] / tot1
    out["share_difference"] = out["share_group_1"] - out["share_group_0"]
    out = out.sort_values("share_difference", key=np.abs, ascending=False)

    chi2 = p = np.nan
    cramers_v = np.nan
    if tab.shape[0] >= 2 and tab.to_numpy().sum() > 0:
        try:
            chi2, p, dof, _ = stats.chi2_contingency(tab.to_numpy())
            n = tab.to_numpy().sum()
            cramers_v = float(np.sqrt(chi2 / (n * (min(tab.shape) - 1))))
        except Exception:
            pass

    print("\n" + "-" * 74)
    print(f"COMPOSITION: does '{var}' predict WHICH KIND of feature is present?")
    print("-" * 74)
    show = out.head(10).copy()
    for c in ("share_group_0", "share_group_1", "share_difference"):
        show[c] = show[c].map(lambda v: f"{v:+.1%}" if c.endswith("difference")
                              else f"{v:.1%}")
    print(show.to_string(index=False))

    if np.isfinite(p):
        if p < ALPHA:
            print(f"\nChi-square: p = {p:.3g}, Cramer's V = {cramers_v:.3f}. "
                  f"The two groups DO contain different mixes of feature type.")
            print("A pooled comparison over all features would partly measure that "
                  "mix rather than size. The per-stratum rows below are the ones to "
                  "read; the pooled row can point the opposite way (Simpson's "
                  "paradox) and is reported for reference only.")
        else:
            print(f"\nChi-square: p = {p:.3g}. Feature-type mix is similar across "
                  f"groups, so the pooled comparison is not badly confounded by "
                  f"composition.")
    out["chi2"] = chi2
    out["chi2_pvalue"] = p
    out["cramers_v"] = cramers_v
    return out


# ---------------------------------------------------------------------------
# DESCRIPTIVES AND TESTS
# ---------------------------------------------------------------------------
def describe_group(values, label, unit):
    v = np.asarray(values, dtype=float)
    logv = np.log(v)
    return {
        "group": label,
        "n": len(v),
        f"median_{unit}": float(np.median(v)),
        f"p10_{unit}": float(np.percentile(v, 10)),
        f"p25_{unit}": float(np.percentile(v, 25)),
        f"p75_{unit}": float(np.percentile(v, 75)),
        f"p90_{unit}": float(np.percentile(v, 90)),
        f"geometric_mean_{unit}": float(np.exp(logv.mean())),
        f"mean_{unit}": float(v.mean()),
        f"sd_{unit}": float(v.std(ddof=1)) if len(v) > 1 else np.nan,
        f"min_{unit}": float(v.min()),
        f"max_{unit}": float(v.max()),
        f"total_{unit}": float(v.sum()),
        "sd_of_log": float(logv.std(ddof=1)) if len(v) > 1 else np.nan,
        "skewness": float(stats.skew(v)) if len(v) > 2 else np.nan,
    }


def run_tests(v1, v0, unit):
    rows = []
    n1, n0 = len(v1), len(v0)
    log1, log0 = np.log(v1), np.log(v0)

    # --- 1. Welch t-test on logs: the headline test -----------------------
    # Welch (unequal variance) rather than Student's, because group sizes
    # and spreads are rarely comparable. On logs the difference in means is
    # the log ratio of geometric means, so exp(diff) is a clean
    # "group 1 is X times larger" effect size.
    t_log = stats.ttest_ind(log1, log0, equal_var=False)
    diff_log = float(log1.mean() - log0.mean())
    se_log = float(np.sqrt(log1.var(ddof=1) / n1 + log0.var(ddof=1) / n0))
    dof = float(getattr(t_log, "df", n1 + n0 - 2))
    tcrit = float(stats.t.ppf(1 - ALPHA / 2, dof)) if np.isfinite(dof) else np.nan
    rows.append({
        "test": "welch_t_on_log",
        "statistic": float(t_log.statistic),
        "pvalue": float(t_log.pvalue),
        "dof": dof,
        "effect": "geometric_mean_ratio_1_over_0",
        "effect_size": float(np.exp(diff_log)),
        "effect_ci_low": float(np.exp(diff_log - tcrit * se_log)),
        "effect_ci_high": float(np.exp(diff_log + tcrit * se_log)),
        "n_group_1": n1, "n_group_0": n0,
        "note": "headline test; compares geometric means, robust to right skew",
    })

    # --- 2. Mann-Whitney U ------------------------------------------------
    # U / (n1*n0) is the common-language effect size: the probability a
    # randomly drawn group-1 feature is larger than a group-0 one.
    mw = stats.mannwhitneyu(v1, v0, alternative="two-sided")
    rows.append({
        "test": "mann_whitney_u",
        "statistic": float(mw.statistic),
        "pvalue": float(mw.pvalue),
        "dof": np.nan,
        "effect": "prob_random_group1_exceeds_random_group0",
        "effect_size": float(mw.statistic) / (n1 * n0),
        "effect_ci_low": np.nan, "effect_ci_high": np.nan,
        "n_group_1": n1, "n_group_0": n0,
        "note": "no distributional assumption; tests stochastic dominance",
    })

    # --- 3. Kolmogorov-Smirnov -------------------------------------------
    ks = stats.ks_2samp(v1, v0, alternative="two-sided")
    rows.append({
        "test": "kolmogorov_smirnov",
        "statistic": float(ks.statistic),
        "pvalue": float(ks.pvalue),
        "dof": np.nan,
        "effect": "max_cdf_gap",
        "effect_size": float(ks.statistic),
        "effect_ci_low": np.nan, "effect_ci_high": np.nan,
        "n_group_1": n1, "n_group_0": n0,
        "note": "sensitive to differences in spread/shape, not just level",
    })

    # --- raw-scale t-test, for completeness only --------------------------
    t_raw = stats.ttest_ind(v1, v0, equal_var=False)
    rows.append({
        "test": "welch_t_on_raw",
        "statistic": float(t_raw.statistic),
        "pvalue": float(t_raw.pvalue),
        "dof": float(getattr(t_raw, "df", np.nan)),
        "effect": f"mean_difference_{unit}",
        "effect_size": float(v1.mean() - v0.mean()),
        "effect_ci_low": np.nan, "effect_ci_high": np.nan,
        "n_group_1": n1, "n_group_0": n0,
        "note": "reported for completeness; dominated by the largest features",
    })
    return pd.DataFrame(rows)


def benjamini_hochberg(pvalues):
    """BH step-up FDR adjustment; returns q-values aligned to the input."""
    p = np.asarray(pvalues, dtype=float)
    ok = np.isfinite(p)
    q = np.full_like(p, np.nan, dtype=float)
    if ok.sum() == 0:
        return q
    pv = p[ok]
    m = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    adj = ranked * m / (np.arange(m) + 1)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    out = np.empty(m)
    out[order] = np.minimum(adj, 1.0)
    q[ok] = out
    return q


# ---------------------------------------------------------------------------
# ONE STRATUM
# ---------------------------------------------------------------------------
def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:60] or "x"


def compare_stratum(sub, label, measure, unit, var, min_n, outdir,
                    by_col=None, plot=False, verbose=True):
    v1 = sub.loc[sub["_group"] == 1, "_size"].to_numpy(dtype=float)
    v0 = sub.loc[sub["_group"] == 0, "_size"].to_numpy(dtype=float)
    n1, n0 = len(v1), len(v0)

    base = {
        "stratum": label, "measure": measure, "unit": unit,
        "n_group_1": n1, "n_group_0": n0,
    }
    if n1 < min_n or n0 < min_n:
        base["tested"] = False
        base["reason"] = f"fewer than --min-n={min_n} features in a group"
        if verbose:
            print(f"  SKIP  {label:<34} n1={n1}, n0={n0} (below --min-n={min_n})")
        return base, None, None

    # Degenerate stratum: essentially no variation to test. Common with
    # --measure vertices on templated geometry (every box has 5 vertices).
    # scipy emits precision-loss warnings rather than a usable result here.
    pooled_vals = np.concatenate([v1, v0])
    if np.unique(pooled_vals).size < 2 or np.std(np.log(pooled_vals)) < 1e-12:
        base["tested"] = False
        base["reason"] = "no variation in the measure within this stratum"
        if verbose:
            print(f"  SKIP  {label:<34} every feature has the same {measure} "
                  f"({pooled_vals[0]:g} {unit}); nothing to test")
        return base, None, None

    summary = pd.DataFrame([
        describe_group(v1, "group_1", unit),
        describe_group(v0, "group_0", unit),
        describe_group(np.concatenate([v1, v0]), "all", unit),
    ])
    tests = run_tests(v1, v0, unit)
    t = tests.set_index("test")

    base.update({
        "tested": True, "reason": "",
        f"median_1_{unit}": float(np.median(v1)),
        f"median_0_{unit}": float(np.median(v0)),
        "geometric_mean_ratio": t.loc["welch_t_on_log", "effect_size"],
        "ratio_ci_low": t.loc["welch_t_on_log", "effect_ci_low"],
        "ratio_ci_high": t.loc["welch_t_on_log", "effect_ci_high"],
        "tstat_log": t.loc["welch_t_on_log", "statistic"],
        "pvalue_log": t.loc["welch_t_on_log", "pvalue"],
        "prob_1_exceeds_0": t.loc["mann_whitney_u", "effect_size"],
        "pvalue_mannwhitney": t.loc["mann_whitney_u", "pvalue"],
        "pvalue_ks": t.loc["kolmogorov_smirnov", "pvalue"],
        "pvalue_raw_t": t.loc["welch_t_on_raw", "pvalue"],
        "skew_group_1": summary.loc[0, "skewness"],
        "skew_group_0": summary.loc[1, "skewness"],
    })

    if verbose:
        ratio = base["geometric_mean_ratio"]
        print(f"  {label:<34} n={n1:>6,}/{n0:<6,}  ratio={ratio:>7.3g}  "
              f"p={base['pvalue_log']:.3g}")

    tag = f"{safe_name(var)}_{safe_name(label)}"
    summary.to_csv(outdir / f"summary_{tag}.csv", index=False)
    tests.to_csv(outdir / f"tests_{tag}.csv", index=False)

    if by_col:
        bd = breakdown(sub, by_col, unit, min_per_group=max(3, min_n // 2))
        if bd is not None:
            bd.to_csv(outdir / f"by_{safe_name(by_col)}_{tag}.csv", index=False)

    if plot:
        make_plots(v1, v0, var, measure, unit, label,
                   outdir / f"compare_{tag}.png")

    return base, summary, tests


def breakdown(gdf, by_col, unit, min_per_group=3):
    if by_col not in gdf.columns:
        return None
    rows = []
    for key, sub in gdf.groupby(by_col, dropna=True):
        v1 = sub.loc[sub["_group"] == 1, "_size"].to_numpy(dtype=float)
        v0 = sub.loc[sub["_group"] == 0, "_size"].to_numpy(dtype=float)
        row = {
            by_col: key, "n_group_1": len(v1), "n_group_0": len(v0),
            f"median_1_{unit}": float(np.median(v1)) if len(v1) else np.nan,
            f"median_0_{unit}": float(np.median(v0)) if len(v0) else np.nan,
        }
        if len(v1) >= min_per_group and len(v0) >= min_per_group:
            log1, log0 = np.log(v1), np.log(v0)
            res = stats.ttest_ind(log1, log0, equal_var=False)
            row["geometric_mean_ratio"] = float(np.exp(log1.mean() - log0.mean()))
            row["tstat_log"] = float(res.statistic)
            row["pvalue_log"] = float(res.pvalue)
            row["testable"] = True
        else:
            row.update({"geometric_mean_ratio": np.nan, "tstat_log": np.nan,
                        "pvalue_log": np.nan, "testable": False})
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("n_group_1", ascending=False)
    if out["testable"].any():
        out.loc[out["testable"], "qvalue_bh"] = benjamini_hochberg(
            out.loc[out["testable"], "pvalue_log"].to_numpy())
    return out


# ---------------------------------------------------------------------------
# PLOTS
# ---------------------------------------------------------------------------
def make_plots(v1, v0, var, measure, unit, label, out_path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    # Histogram on a log x-axis. A linear axis squashes a skewed size
    # distribution into the leftmost sliver of the plot and shows nothing.
    ax = axes[0]
    all_v = np.concatenate([v1, v0])
    bins = np.logspace(np.log10(all_v.min()), np.log10(all_v.max()), 40)
    ax.hist(v0, bins=bins, alpha=0.55, label=f"{var}=0 (n={len(v0):,})", color="#4C72B0")
    ax.hist(v1, bins=bins, alpha=0.55, label=f"{var}=1 (n={len(v1):,})", color="#C44E52")
    ax.axvline(np.median(v0), color="#4C72B0", linestyle="--", linewidth=1.5)
    ax.axvline(np.median(v1), color="#C44E52", linestyle="--", linewidth=1.5)
    ax.set_xscale("log")
    ax.set_xlabel(f"{measure} ({unit}, log scale)")
    ax.set_ylabel("number of features")
    ax.set_title(f"{label}\n{measure} by {var} (dashed = medians)")
    ax.legend(fontsize=9)

    ax = axes[1]
    tick_kw = {"tick_labels": [f"{var}=0", f"{var}=1"]}
    flier = dict(marker=".", markersize=3, alpha=0.4)
    try:
        ax.boxplot([v0, v1], showfliers=True, flierprops=flier, **tick_kw)
    except TypeError:
        ax.boxplot([v0, v1], labels=[f"{var}=0", f"{var}=1"],
                   showfliers=True, flierprops=flier)
    ax.set_yscale("log")
    ax.set_ylabel(f"{measure} ({unit}, log scale)")
    ax.set_title(f"{label}")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def make_overview_plot(results, var, out_path):
    """Forest plot of the geometric-mean ratio across strata."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    df = results[results["tested"] & results["stratum"].ne("POOLED (all features)")]
    df = df.dropna(subset=["geometric_mean_ratio"])
    if df.empty:
        return False
    df = df.sort_values("geometric_mean_ratio")

    fig, ax = plt.subplots(figsize=(8, max(3.0, 0.42 * len(df) + 1.6)))
    y = np.arange(len(df))
    sig = df["qvalue_bh"].fillna(1.0) < ALPHA
    colors = np.where(sig, "#C44E52", "#999999")

    ax.hlines(y, df["ratio_ci_low"], df["ratio_ci_high"],
              color=colors, linewidth=2, alpha=0.8)
    ax.scatter(df["geometric_mean_ratio"], y, color=colors, zorder=3, s=36)
    ax.axvline(1.0, color="black", linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{s}  (n={a:,}/{b:,})" for s, a, b in
                        zip(df["stratum"], df["n_group_1"], df["n_group_0"])],
                       fontsize=9)
    ax.set_xscale("log")
    ax.set_xlabel(f"geometric mean size ratio, {var}=1 vs {var}=0 (log scale)")
    ax.set_title("Size difference by stratum", fontsize=12)
    fig.suptitle("red = significant after BH FDR correction | bars = 95% CI | "
                 "dashed line = no difference",
                 fontsize=8.5, y=0.985, color="#444444")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


# ---------------------------------------------------------------------------
# INTERPRETATION
# ---------------------------------------------------------------------------
def interpret(results, var, composition):
    print("\n" + "=" * 74)
    print("READING THE RESULTS")
    print("=" * 74)

    tested = results[results["tested"]]
    if tested.empty:
        print("No stratum had enough features on both sides to test. Lower "
              "--min-n, drop --element-col, or check the flag.")
        return

    strata = tested[tested["stratum"] != "POOLED (all features)"]
    if not strata.empty:
        sig = strata[strata["qvalue_bh"] < ALPHA]
        print(f"{len(strata)} strata tested, {len(sig)} significant after "
              f"Benjamini-Hochberg FDR correction at {ALPHA:g}.")
        if len(strata) > 1:
            print("(Correction matters here: testing many strata uncorrected "
                  "produces false positives by construction.)")
        for _, r in sig.sort_values("geometric_mean_ratio").iterrows():
            unit = r["unit"]
            direction = "larger" if r["geometric_mean_ratio"] > 1 else "smaller"
            print(f"  {r['stratum']}: {var}=1 features are "
                  f"{r['geometric_mean_ratio']:.3g}x {direction} "
                  f"(95% CI {r['ratio_ci_low']:.3g}-{r['ratio_ci_high']:.3g}, "
                  f"q = {r['qvalue_bh']:.3g}); medians "
                  f"{r[f'median_1_{unit}']:,.4g} vs {r[f'median_0_{unit}']:,.4g} {unit}")
        if sig.empty:
            print("  No stratum survives correction.")

        # direction conflict between strata and the pooled row
        pooled = tested[tested["stratum"] == "POOLED (all features)"]
        if not pooled.empty and not sig.empty:
            pooled_ratio = pooled.iloc[0]["geometric_mean_ratio"]
            same = np.sign(np.log(sig["geometric_mean_ratio"]))
            if np.isfinite(pooled_ratio) and len(set(same)) == 1:
                if np.sign(np.log(pooled_ratio)) != same.iloc[0]:
                    print("\nWARNING: the pooled comparison points the OPPOSITE way "
                          "from every significant stratum. This is Simpson's "
                          "paradox driven by feature-type composition. Quote the "
                          "per-stratum results, not the pooled one.")

    # shape-vs-level, per stratum
    shape_only = tested[(tested["pvalue_ks"] < ALPHA)
                        & (tested["pvalue_mannwhitney"] >= ALPHA)]
    if not shape_only.empty:
        print(f"\nNOTE: in {list(shape_only['stratum'])}, KS rejects but "
              f"Mann-Whitney does not. Those groups differ in the SHAPE of the "
              f"size distribution -- spread, or the weight of the tails -- rather "
              f"than in typical level. Read the quantiles (p10/p25/p75/p90) in the "
              f"per-stratum summary files, not just the ratio.")

    # raw vs log divergence
    diverge = tested[(tested["pvalue_raw_t"] < ALPHA)
                     & (tested["pvalue_log"] >= ALPHA)]
    if not diverge.empty:
        print(f"\nNOTE: in {list(diverge['stratum'])}, a naive t-test on raw sizes "
              f"would have come out significant while the log-scale test does not. "
              f"That gap is the largest few features doing the work. The log test "
              f"is the one to quote.")

    if tested["skew_group_1"].max() > 2 or tested["skew_group_0"].max() > 2:
        print(f"\nSkewness is high (max {max(tested['skew_group_1'].max(), tested['skew_group_0'].max()):.1f}), "
              f"which is why medians and the log-scale ratio are the right summary, "
              f"not raw means.")

    if composition is not None and np.isfinite(composition["chi2_pvalue"].iloc[0]):
        if composition["chi2_pvalue"].iloc[0] < ALPHA:
            print(f"\nFeature-type composition differs across groups "
                  f"(Cramer's V = {composition['cramers_v'].iloc[0]:.3f}), so the "
                  f"pooled row is confounded. Per-stratum rows are the answer.")
    print("=" * 74)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main(args):
    outdir = Path(args.outdir)
    gdf = load_features(args.input, layer=args.layer)
    geom_name = gdf.geometry.name
    gdf = clean_geometry(gdf)

    if args.inspect:
        inspect(gdf, geom_name)
        return

    if not args.var:
        raise ValueError("--var is required (or use --inspect to explore the file).")

    outdir.mkdir(parents=True, exist_ok=True)

    # element-type column
    element_col = args.element_col
    if element_col is None and args.element_auto:
        cands = element_candidates(gdf, geom_name)
        cands = [c for c in cands if c["column"] != args.var]
        if cands:
            element_col = cands[0]["column"]
            print(f"  --element-auto chose '{element_col}' "
                  f"({cands[0]['n_distinct']} values). Override with --element-col.")
        else:
            print("  --element-auto found no suitable column; stratifying by "
                  "geometry family only.")
    if element_col and element_col not in gdf.columns:
        raise KeyError(f"--element-col '{element_col}' not in input. "
                       f"Run with --inspect to see the columns.")
    if element_col:
        n_cat = gdf[element_col].nunique()
        if n_cat > args.max_categories:
            print(f"  WARNING: '{element_col}' has {n_cat} categories; only the "
                  f"{args.max_categories} most common are tested separately.")
            keep = gdf[element_col].value_counts().head(args.max_categories).index
            gdf = gdf[gdf[element_col].isin(keep)]

    gdf = prepare_groups(gdf, args.var, true_value=args.true_value)
    composition = composition_check(gdf, args.var, element_col)

    # Build strata: geometry family always, element type if available.
    strata_keys = ["_family"] + ([element_col] if element_col else [])

    print("\n" + "-" * 74)
    print("PER-STRATUM COMPARISONS")
    print("-" * 74)

    results, skipped_points = [], 0
    for key, sub in gdf.groupby(strata_keys, dropna=False, observed=True):
        key = key if isinstance(key, tuple) else (key,)
        family = key[0]
        label = " / ".join(str(k) for k in key)

        measure = resolve_measure(family, args.measure)
        if measure is None:
            if family == "point":
                skipped_points += len(sub)
                print(f"  SKIP  {label:<34} points have no size measure "
                      f"({len(sub):,} features; counts are in the composition table)")
            else:
                print(f"  SKIP  {label:<34} --measure {args.measure} is not "
                      f"meaningful for {family} geometry")
            continue

        unit = MEASURE_UNITS[measure]
        sub = compute_measure(sub, measure, args.crs)
        if sub.empty:
            continue
        row, _, _ = compare_stratum(sub, label, measure, unit, args.var,
                                    args.min_n, outdir, by_col=args.by,
                                    plot=args.plot)
        results.append(row)

    # Pooled comparison, only where it is coherent: a single geometry family.
    if not args.no_pooled:
        fams = [f for f in gdf["_family"].unique()
                if FAMILY_DEFAULT_MEASURE.get(f) is not None]
        if len(fams) == 1:
            measure = resolve_measure(fams[0], args.measure)
            if measure:
                unit = MEASURE_UNITS[measure]
                pooled = compute_measure(gdf[gdf["_family"] == fams[0]],
                                         measure, args.crs)
                if not pooled.empty:
                    row, _, _ = compare_stratum(
                        pooled, "POOLED (all features)", measure, unit, args.var,
                        args.min_n, outdir, by_col=args.by, plot=args.plot)
                    results.append(row)
        elif len(fams) > 1:
            print(f"\n  No pooled row: the file mixes {fams}, which are measured in "
                  f"different units ({', '.join(MEASURE_UNITS[FAMILY_DEFAULT_MEASURE[f]] for f in fams)}). "
                  f"Pooling them would average areas with lengths.")

    if not results:
        print("\nNothing could be compared. Try --min-n lower, or --inspect.")
        return

    res = pd.DataFrame(results)
    if "tested" in res and res["tested"].any():
        mask = res["tested"] & res["stratum"].ne("POOLED (all features)")
        if mask.any():
            res.loc[mask, "qvalue_bh"] = benjamini_hochberg(
                res.loc[mask, "pvalue_log"].to_numpy())

    comp_path = outdir / f"composition_{safe_name(args.var)}.csv"
    all_path = outdir / f"all_comparisons_{safe_name(args.var)}.csv"
    composition.to_csv(comp_path, index=False)
    res.to_csv(all_path, index=False)

    interpret(res, args.var, composition)

    print(f"\nSaved {all_path}")
    print(f"Saved {comp_path}")
    print(f"Per-stratum summary/tests files in {outdir}/")
    if skipped_points:
        print(f"({skipped_points:,} point features were counted but not sized.)")

    if args.plot:
        ov = outdir / f"overview_{safe_name(args.var)}.png"
        if make_overview_plot(res, args.var, ov):
            print(f"Saved {ov}")


def build_parser():
    p = argparse.ArgumentParser(
        description="Compare vector feature size between the two groups of a "
                    "binary variable, stratified by geometry type and element type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Start with --inspect on a file you have not seen before.",
    )
    p.add_argument("--input", required=True,
                   help="Any GDAL-readable vector file (GeoJSON, GPKG, shapefile, ...).")
    p.add_argument("--inspect", action="store_true",
                   help="Describe the file and exit; suggests usable columns.")
    p.add_argument("--var", default=None,
                   help="Binary grouping column (e.g. is_europe).")
    p.add_argument("--true-value", default=None, dest="true_value",
                   help="For a non-binary column, the value defining group 1.")
    p.add_argument("--layer", default=None, help="Layer name for multi-layer files.")
    p.add_argument("--element-col", default=None, dest="element_col",
                   help="Column of element types to compare within (e.g. fclass).")
    p.add_argument("--element-auto", action="store_true", dest="element_auto",
                   help="Try to detect the element-type column automatically.")
    p.add_argument("--measure", default="auto",
                   choices=["auto", "area", "perimeter", "length", "vertices"],
                   help="auto picks area for polygons and length for lines.")
    p.add_argument("--by", default=None, help="Further breakdown column.")
    p.add_argument("--min-n", type=int, default=8, dest="min_n",
                   help="Minimum features per group within a stratum (default 8).")
    p.add_argument("--max-categories", type=int, default=30, dest="max_categories",
                   help="Cap on element-type categories tested (default 30).")
    p.add_argument("--no-pooled", action="store_true", dest="no_pooled",
                   help="Suppress the pooled all-features comparison.")
    p.add_argument("--plot", action="store_true", help="Write log-scale plots.")
    p.add_argument("--crs", default=DEFAULT_EQUAL_AREA_CRS,
                   help=f"Equal-area CRS for measurement (default {DEFAULT_EQUAL_AREA_CRS}).")
    p.add_argument("--outdir", default=str(DEFAULT_OUTPUT_DIR),
                   help=f"Output directory (default {DEFAULT_OUTPUT_DIR}).")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    try:
        main(args)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
