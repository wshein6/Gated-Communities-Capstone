"""
compare_by_binary_csv.py  --  CSV-COMPATIBLE VERSION

Compare the physical size of features between the two groups of a binary
variable, reading a CSV (or TSV) whose coordinates live in a column such as

    boundaries
    [71.72245023 29.4113817  71.72312079 29.41207762]

That column is expected: this version is built for a table with no
geometry of its own, and it finds the coordinate column automatically, so
--geometry-from is optional. Everything else -- GeoJSON, GPKG, shapefile
-- still works exactly as in compare_by_binary.py; the CSV path is simply
the one made frictionless here.

    # look at the file first -- no --var needed
    python compare_by_binary_csv.py --input table.csv --inspect

    # then run the comparison; the coordinate column is auto-detected
    python compare_by_binary_csv.py --input table.csv --var is_europe

    # name the column yourself if the file has more than one
    python compare_by_binary_csv.py --input table.csv --var is_europe --geometry-from boundaries

    # group on whether ANY of several flags is set (their sum > 0)
    python compare_by_binary_csv.py --input table.csv --vars has_metro has_port has_airport

    # stratify by element type, and draw the plots
    python compare_by_binary_csv.py --input table.csv --var in_core --element-col fclass --plot


WHAT "SIZE" MEANS HERE, AND THE ONE CAVEAT
------------------------------------------
Four numbers in the coordinate column are read as a bounding box, so the
polygon measured is the box, not the feature inside it. For compact
shapes -- a cluster footprint, a building, a parcel -- the box is a close
stand-in. For anything long and diagonal, such as a road centreline, the
box is far larger than the thing itself and its area is close to
meaningless.

The inflation also depends on orientation, so if the two groups differ in
the shape or bearing of their features, a box comparison measures that
difference as well as size. On a test where group 1 was identical to
group 0 but rotated 45 degrees, boxes reported group 1 as 3.33x larger
(p = 2e-55) while the true geometry showed no difference at all
(ratio 1.07, p = 0.37).

A CSV carries no true geometry to check that against, so the script says
so plainly rather than implying a check it could not run. Where the same
features are also available as a GeoJSON or GPKG, running that file
through compare_by_binary.py and comparing the two answers is the way to
confirm the boxes are not misleading you.

Areas are computed in an equal-area projection (EPSG:6933 by default)
from the coordinates, never taken from an existing area column, so
features at different latitudes are measured on the same footing.

COMBINING SEVERAL FLAGS (--vars)
--------------------------------
--vars takes any number of binary columns and groups on how many are
set. The default threshold is 1, so group 1 is every feature where the
sum of the flags exceeds zero and group 0 is the rest:

    --vars has_metro has_port has_airport                 sum > 0
    --vars has_metro has_port has_airport --min-true 2    sum >= 2
    --vars has_metro has_port has_airport --min-true 3    all three

Missing components are resolved rather than assumed away. A feature
joins group 1 as soon as enough flags are observed true, whatever else
is missing; it joins group 0 only when it could not reach the threshold
even if every missing flag turned out true. Features in between are
undetermined and are dropped with a count, unless --na-as-zero says to
read a missing flag as not-set. Treating missing as zero quietly moves
those features into group 0 and biases the comparison when missingness
is related to size, so it is opt-in rather than the default.

The run prints how many features each flag accounts for and how often
each is the ONLY flag set, which is what tells you whether the combined
group is one phenomenon or three stacked together.


COORDINATE COLUMNS (--geometry-from)
------------------------------------
Size can be built from a column of raw coordinates instead of the file's
geometry, which also lets the input be a plain CSV with no geometry at
all. The parser is format-agnostic: it pulls every number out of the
cell, so all of these work --

    [71.72245023 29.4113817  71.72312079 29.41207762]      numpy repr
    [71.72245023, 29.4113817, 71.72312079, 29.41207762]    JSON-ish
    71.72245023,29.4113817,71.72312079,29.41207762         bare CSV
    (71.72245 29.41138, 71.72312 29.41208)                 parenthesised
    POLYGON ((71.722 29.411, ...))                         WKT
    [71.72, 29.41, 71.73, 29.41, 71.73, 29.42, ...]        a full ring

Four numbers are read as a bounding box; more than four as a coordinate
sequence (a ring if it closes, a line otherwise); two as a point.
Override with --coords-as.

Axis order is sniffed from the data: the script checks which of the two
slots stays within +/-90 and so must hold latitude, and reports what it
chose. Force it with --bbox-order xyxy (lon/lat) or yxyx (lat/lon).

A BOUNDING BOX IS NOT THE FEATURE. The envelope of a diagonal road is
large while the road has no area at all, and that inflation depends on
each feature's shape and orientation. So when the file ALSO carries real
geometry, the script measures both and reports the envelope-inflation
ratio per group; if the inflation differs across groups, a bbox
comparison is biased and the script says so and names the real-geometry
run as the one to trust.


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
DEFAULT_OUTPUT_DIR = Path("output/comparisons")

# Equal-area projection for all area / length computation. EPSG:6933
# (NSIDC EASE-Grid 2.0 Global) is equal-area and global, so a polygon in
# Oslo and a polygon in Lagos are measured on the same footing.
DEFAULT_EQUAL_AREA_CRS = "EPSG:6933"

TRUE_TOKENS = {"1", "1.0", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "0.0", "false", "f", "no", "n"}

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
# COORDINATE-COLUMN PARSING  (--geometry-from)
# ---------------------------------------------------------------------------
# Matches any number, including scientific notation and leading signs, so
# the parser does not care about brackets, commas or whitespace.
_NUM_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

_WKT_PREFIXES = ("POINT", "LINESTRING", "POLYGON", "MULTIPOINT",
                 "MULTILINESTRING", "MULTIPOLYGON", "GEOMETRYCOLLECTION")

COORD_NAME_HINTS = ("bound", "bbox", "box", "extent", "envelope", "coord",
                    "geom", "wkt", "shape", "outline", "ring", "footprint")


def parse_coord_cell(value):
    """
    Pull a coordinate sequence out of one cell.

    Returns ('wkt', str), a float ndarray, or None if nothing usable.
    Deliberately tolerant: the numbers are what matter, not the
    punctuation around them.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, np.ndarray)):
        try:
            arr = np.asarray(value, dtype=float).ravel()
        except (TypeError, ValueError):
            return None
        return arr if arr.size else None
    if isinstance(value, float) and np.isnan(value):
        return None

    s = str(value).strip()
    if not s or s.lower() in {"nan", "none", "null", "[]", "()"}:
        return None
    if s.upper().lstrip("(").lstrip().startswith(_WKT_PREFIXES):
        return ("wkt", s)

    nums = _NUM_RE.findall(s)
    if not nums:
        return None
    try:
        return np.array([float(n) for n in nums], dtype=float)
    except ValueError:
        return None


def detect_bbox_order(samples, is_geographic):
    """
    Decide whether a 4-number cell is [minx miny maxx maxy] (xyxy, the
    GeoJSON order) or [miny minx maxy maxx] (yxyx, the lat/lon order).

    Latitude cannot exceed +/-90, so whichever slot stays inside that
    range is the latitude slot. Where both slots qualify the data is
    genuinely ambiguous and xyxy is assumed, which is stated.
    """
    if not is_geographic:
        return "xyxy", "non-geographic CRS; assuming [minx miny maxx maxy]"

    arr = np.array([s for s in samples if isinstance(s, np.ndarray) and s.size == 4])
    if arr.size == 0:
        return "xyxy", "no 4-number cells sampled; assuming [minx miny maxx maxy]"

    # xyxy puts latitude in slots 1 and 3; yxyx puts it in slots 0 and 2.
    xyxy_ok = bool(np.all(np.abs(arr[:, [1, 3]]) <= 90))
    yxyx_ok = bool(np.all(np.abs(arr[:, [0, 2]]) <= 90))
    xyxy_sorted = bool(np.all(arr[:, 0] <= arr[:, 2]) and np.all(arr[:, 1] <= arr[:, 3]))

    if xyxy_ok and not yxyx_ok:
        return "xyxy", "slots 2 and 4 stay within +/-90, so they are latitude"
    if yxyx_ok and not xyxy_ok:
        return "yxyx", "slots 1 and 3 stay within +/-90, so they are latitude"
    if xyxy_ok and yxyx_ok:
        # Genuinely undecidable from the values alone: every number is a
        # valid latitude. Show what each reading implies so it can be
        # checked by eye against a known location.
        mid = arr.mean(axis=0)
        note = ("ambiguous -- every value is within +/-90, so both readings are "
                "possible; assuming [minx miny maxx maxy]. "
                f"Mean centre reads as lon {(mid[0] + mid[2]) / 2:.4f}, "
                f"lat {(mid[1] + mid[3]) / 2:.4f} under xyxy, or lon "
                f"{(mid[1] + mid[3]) / 2:.4f}, lat {(mid[0] + mid[2]) / 2:.4f} "
                f"under yxyx -- set --bbox-order if the second is your study area")
        if not xyxy_sorted:
            note += "; note the min/max ordering does not hold under xyxy"
        return "xyxy", note
    return "xyxy", ("neither order keeps latitude within +/-90; assuming "
                    "[minx miny maxx maxy] -- check --geometry-crs")


def coords_to_geometry(parsed, coords_as, bbox_order):
    """Turn one parsed cell into a shapely geometry, or None."""
    from shapely.geometry import box as shp_box, LineString, Point, Polygon
    from shapely import wkt as shp_wkt

    if parsed is None:
        return None
    if isinstance(parsed, tuple) and parsed[0] == "wkt":
        try:
            return shp_wkt.loads(parsed[1])
        except Exception:
            return None

    nums = np.asarray(parsed, dtype=float)
    if not np.all(np.isfinite(nums)):
        return None
    n = nums.size

    kind = coords_as
    if kind == "auto":
        if n == 4:
            kind = "bbox"
        elif n == 2:
            kind = "point"
        elif n >= 6 and n % 2 == 0:
            kind = "polygon"
        else:
            return None

    if kind == "bbox":
        if n != 4:
            return None
        a, b, c, d = nums
        minx, miny, maxx, maxy = (a, b, c, d) if bbox_order == "xyxy" else (b, a, d, c)
        if minx > maxx:
            minx, maxx = maxx, minx
        if miny > maxy:
            miny, maxy = maxy, miny
        if minx == maxx and miny == maxy:
            return Point(minx, miny)
        return shp_box(minx, miny, maxx, maxy)

    if n % 2 != 0:
        return None
    pts = nums.reshape(-1, 2)
    if bbox_order == "yxyx":
        pts = pts[:, ::-1]

    if kind == "point":
        return Point(pts[0]) if len(pts) >= 1 else None
    if kind == "line":
        return LineString(pts) if len(pts) >= 2 else None
    if kind == "polygon":
        ring = pts
        if len(ring) >= 2 and not np.allclose(ring[0], ring[-1]):
            ring = np.vstack([ring, ring[0]])
        if len(ring) < 4:
            return LineString(pts) if len(pts) >= 2 else None
        try:
            return Polygon(ring)
        except Exception:
            return None
    return None


def build_geometry_from_column(df, column, coords_as, bbox_order, geometry_crs):
    """
    Replace (or supply) geometry from a coordinate column.

    Returns (GeoDataFrame, info dict). The original geometry, if the file
    had one, is kept as '_true_geometry' so the envelope-inflation
    diagnostic can compare the two.
    """
    if column not in df.columns:
        cols = [c for c in df.columns if not c.startswith("_")]
        raise KeyError(f"--geometry-from column '{column}' not in input. "
                       f"Available: {cols}\nRun with --inspect to explore the file.")

    parsed = df[column].map(parse_coord_cell)
    n_null = int(parsed.isna().sum())

    sizes = parsed.map(lambda p: p.size if isinstance(p, np.ndarray) else -1)
    usable = sizes[sizes > 0]
    size_counts = usable.value_counts().to_dict() if len(usable) else {}
    n_wkt = int(parsed.map(lambda p: isinstance(p, tuple)).sum())

    try:
        crs_obj = gpd.GeoSeries([], crs=geometry_crs).crs
        is_geographic = bool(crs_obj.is_geographic)
    except Exception:
        is_geographic = True

    order, order_note = (bbox_order, "set explicitly with --bbox-order") \
        if bbox_order != "auto" \
        else detect_bbox_order(parsed.dropna().head(2000).tolist(), is_geographic)

    geoms = parsed.map(lambda p: coords_to_geometry(p, coords_as, order))
    n_failed = int(geoms.isna().sum()) - n_null

    print(f"  Building geometry from '{column}' ({geometry_crs})")
    if n_wkt:
        print(f"    {n_wkt:,} cells parsed as WKT")
    if size_counts:
        shown = ", ".join(f"{int(k)} numbers: {v:,} rows"
                          for k, v in sorted(size_counts.items())[:5])
        print(f"    cell shapes -> {shown}")
    print(f"    axis order: {order} ({order_note})")
    if n_null:
        print(f"    {n_null:,} rows had an empty or unparseable cell and are dropped")
    if n_failed > 0:
        print(f"    {n_failed:,} rows parsed but could not form a geometry and are dropped")

    out = df.copy()
    had_geometry = isinstance(df, gpd.GeoDataFrame) and df.geometry.notna().any()
    if had_geometry:
        out["_true_geometry"] = df.geometry.values

    out = gpd.GeoDataFrame(out, geometry=gpd.GeoSeries(geoms.values, crs=geometry_crs))
    out = out[out.geometry.notna()]
    if out.empty:
        raise ValueError(
            f"No usable geometry could be built from '{column}'. "
            f"Sample cell: {df[column].dropna().iloc[0]!r}. "
            f"Try --coords-as to state what the numbers mean."
        )

    kinds = out.geometry.geom_type.value_counts().to_dict()
    print(f"    built {len(out):,} geometries: {kinds}")

    return out, {"column": column, "order": order, "had_true_geometry": had_geometry}


def envelope_inflation_check(gdf, var, equal_area_crs):
    """
    How much larger is the bounding box than the feature it encloses, and
    does that differ across groups?

    If it does, a bbox-based size comparison is biased: it is partly
    measuring shape and orientation rather than size. A diagonal line has
    a huge envelope and no area; a compact blob has an envelope barely
    larger than itself.
    """
    sub = gdf[gdf["_true_geometry"].notna()].copy()
    if sub.empty:
        return None

    true_geom = gpd.GeoSeries(sub["_true_geometry"].values, crs=gdf.crs)
    polygonal = true_geom.geom_type.isin(["Polygon", "MultiPolygon"])
    if not polygonal.any():
        print("\nNOTE: the file's real geometry has no polygons, so true area is "
              "zero everywhere and envelope inflation is undefined. Bounding-box "
              "area measures the extent each feature spans, not its footprint.")
        return None

    sub = sub[polygonal.values]
    true_area = gpd.GeoSeries(sub["_true_geometry"].values,
                              crs=gdf.crs).to_crs(equal_area_crs).area
    bbox_area = sub.geometry.to_crs(equal_area_crs).area
    ratio = (bbox_area.to_numpy() / np.where(true_area.to_numpy() > 0,
                                             true_area.to_numpy(), np.nan))
    ok = np.isfinite(ratio) & (ratio > 0)
    if ok.sum() < 10:
        return None

    groups = sub["_group"].to_numpy()[ok]
    r = ratio[ok]
    r1, r0 = r[groups == 1], r[groups == 0]

    print("\n" + "-" * 74)
    print("ENVELOPE INFLATION: how much bigger is the bounding box than the feature?")
    print("-" * 74)
    print(f"  median bbox area / true area -- group 1: {np.median(r1):.3f}x | "
          f"group 0: {np.median(r0):.3f}x  (1.0 = feature fills its box)")

    out = {"median_inflation_group_1": float(np.median(r1)),
           "median_inflation_group_0": float(np.median(r0)),
           "n": int(ok.sum())}
    if len(r1) >= 8 and len(r0) >= 8:
        res = stats.ttest_ind(np.log(r1), np.log(r0), equal_var=False)
        out["inflation_ratio_1_over_0"] = float(
            np.exp(np.log(r1).mean() - np.log(r0).mean()))
        out["pvalue"] = float(res.pvalue)
        if res.pvalue < ALPHA:
            print(f"  These differ (p = {res.pvalue:.3g}). The two groups' features "
                  f"have systematically different shapes or orientations,")
            print(f"  so a bounding-box comparison is measuring that as well as "
                  f"size. Run WITHOUT --geometry-from to compare true geometry; "
                  f"treat that run as the answer.")
        else:
            print(f"  These are statistically similar (p = {res.pvalue:.3g}), so the "
                  f"bounding box inflates both groups about equally and the bbox "
                  f"comparison tracks the real one.")
    return out


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


TABULAR_SUFFIXES = {".csv", ".tsv", ".txt", ".psv"}

# Encodings tried, in order, when reading a table. Windows files are often
# cp1252 rather than UTF-8, and Python on Windows defaults to the locale
# codec, which fails on bytes like 0x9d. latin-1 maps every byte, so the
# chain always terminates.
TABLE_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def read_table_robust(path, suffix):
    """
    Read a CSV/TSV without assuming its encoding or separator.

    Encoding is tried in order rather than guessed once, because a single
    stray byte in a name field should not stop the run. The encoding that
    worked is reported when it is not UTF-8, since reading as latin-1
    will render such a byte as the wrong character -- harmless for the
    numeric columns this script uses, but worth knowing about.
    """
    sep = {".tsv": "\t", ".psv": "|"}.get(suffix, ",")
    last_err = None
    for enc in TABLE_ENCODINGS:
        try:
            df = pd.read_csv(path, sep=sep, encoding=enc)
        except (UnicodeDecodeError, UnicodeError) as exc:
            last_err = exc
            continue
        except Exception as exc:                       # separator problems
            last_err = exc
            break

        # One column back from a .csv usually means it is not comma
        # separated after all; let pandas sniff the dialect.
        if df.shape[1] == 1 and suffix in (".csv", ".txt"):
            try:
                sniffed = pd.read_csv(path, sep=None, engine="python", encoding=enc)
                if sniffed.shape[1] > 1:
                    df = sniffed
            except Exception:
                pass

        if enc != TABLE_ENCODINGS[0]:
            print(f"  NOTE: this file is not UTF-8; read it as {enc}. "
                  f"Text fields may show the odd wrong character; numbers are "
                  f"unaffected.")
        return df

    raise ValueError(
        f"Could not read '{Path(path).name}' as a table. Last error: {last_err}"
    )



def load_features(input_path, layer=None, geometry_from=None, allow_tabular=False):
    """
    Read the input. With --geometry-from the input may be a plain table
    with no geometry at all, so tabular formats are allowed through.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"'{input_path}' not found.")

    suffix = input_path.suffix.lower()
    if suffix in TABULAR_SUFFIXES:
        if not (geometry_from or allow_tabular):
            raise ValueError(
                f"'{input_path.name}' is a plain table with no geometry. "
                f"Pass --geometry-from COLUMN to build geometry from a "
                f"coordinate column."
            )
        df = read_table_robust(input_path, suffix)
        if df.empty:
            raise ValueError("Input table has zero rows.")
        print(f"Loaded {input_path.name}: {len(df):,} rows (tabular, no geometry)")
        return df

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

    has_geom = ("geometry" in gdf and gdf.geometry.notna().any())
    if not has_geom and not (geometry_from or allow_tabular):
        raise ValueError("Input has no usable geometry. If the coordinates live "
                         "in an attribute column, pass --geometry-from COLUMN.")

    if has_geom and gdf.crs is None:
        print("WARNING: input has no CRS. Assuming EPSG:4326 (lon/lat degrees). "
              "If it is actually projected, pass the correct CRS upstream.")
        gdf = gdf.set_crs("EPSG:4326")

    crs_text = gdf.crs.to_string() if gdf.crs else "none"
    print(f"Loaded {input_path.name}: {len(gdf):,} features, CRS {crs_text}")
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


def coord_candidates(gdf, geom_name, sample=400):
    """Columns whose cells parse as coordinate sequences (for --geometry-from)."""
    out = []
    for col in gdf.columns:
        if col == geom_name or col.startswith("_"):
            continue
        s = gdf[col].dropna()
        if s.empty or pd.api.types.is_numeric_dtype(s):
            continue
        head = s.head(sample)
        parsed = [parse_coord_cell(v) for v in head]
        good = [p for p in parsed
                if isinstance(p, tuple)
                or (isinstance(p, np.ndarray) and p.size >= 2 and p.size % 2 == 0)]
        if len(good) < max(5, 0.6 * len(head)):
            continue
        sizes = [p.size for p in good if isinstance(p, np.ndarray)]
        if sizes:
            common = int(pd.Series(sizes).mode().iloc[0])
            shape = {4: "4 numbers -> bounding box", 2: "2 numbers -> point"}.get(
                common, f"{common} numbers -> coordinate ring")
        else:
            shape = "WKT"
        name_hit = any(h in col.lower() for h in COORD_NAME_HINTS)
        out.append({
            "column": col, "shape": shape,
            "coverage": len(good) / len(head),
            "sample": str(head.iloc[0])[:72],
            "_score": (1.0 if name_hit else 0.0) + len(good) / len(head),
        })
    return sorted(out, key=lambda r: -r["_score"])


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


def inspect_tabular(df):
    """Inspect a table that has no geometry yet, to find the coordinate column."""
    print("\n" + "=" * 74)
    print("FILE INSPECTION (no geometry -- a coordinate column is needed)")
    print("=" * 74)
    print(f"\nRows: {len(df):,}")
    print(f"\nColumns ({len(df.columns)}):")
    for col in df.columns:
        s = df[col]
        print(f"  {col:<28} {str(s.dtype):<10} {int(s.notna().sum()):>8,} non-null, "
              f"{s.nunique():>6,} distinct")

    coords = coord_candidates(df, geom_name="__none__")
    print("\nCandidate --geometry-from columns:")
    if coords:
        for c in coords[:4]:
            print(f"  --geometry-from {c['column']}  "
                  f"({c['shape']}, {c['coverage']:.0%} parseable)")
            print(f"      sample: {c['sample']}")
    else:
        print("  none found -- no column parses as a coordinate sequence.")

    bins = binary_candidates(df, geom_name="__none__")
    print("\nCandidate --var columns (exactly 2 distinct values):")
    for b in bins[:6]:
        print(f"  --var {b['column']}   ({b['usage']}); counts: {b['counts']}")
    if not bins:
        print("  none found.")

    if coords and bins:
        print("\nSuggested next command:")
        print(f"  python compare_by_binary_csv.py --input <file> "
              f"--var {bins[0]['column']} --geometry-from {coords[0]['column']} --plot")
    print("=" * 74)


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

    coords = coord_candidates(gdf, geom_name)
    if coords:
        print("\nCandidate --geometry-from columns (cells that parse as coordinates):")
        for c in coords[:4]:
            print(f"  --geometry-from {c['column']}  "
                  f"({c['shape']}, {c['coverage']:.0%} parseable)")
            print(f"      sample: {c['sample']}")

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
    cmd = f"  python compare_by_binary_csv.py --input <file> --var {var}"
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
    return gdf, lab1, lab0


def prepare_groups_multi(gdf, cols, min_true=1, na_as_zero=False):
    """
    Group on a COMBINATION of binary columns: group 1 is a feature where
    at least `min_true` of them are set, group 0 is the rest.

    With the default min_true=1 this is exactly "sum of the flags > 0".

    Missing components are handled rather than assumed away. A row counts
    as group 1 as soon as `min_true` flags are observed true, whatever is
    missing. It counts as group 0 only when it could not reach the
    threshold even if every missing component turned out to be true.
    Anything in between is genuinely undetermined and is dropped, with a
    count, unless --na-as-zero says to read missing as not-set.
    """
    missing = [c for c in cols if c not in gdf.columns]
    if missing:
        avail = [c for c in gdf.columns
                 if c != gdf.geometry.name and not c.startswith("_")]
        raise KeyError(f"Column(s) {missing} not in input. Available: {avail}\n"
                       f"Run with --inspect to see which columns look usable.")
    if len(cols) != len(set(cols)):
        raise ValueError(f"--vars lists a column more than once: {cols}")

    gdf = gdf.copy()
    comp = pd.DataFrame(index=gdf.index)
    for c in cols:
        comp[c] = coerce_binary(gdf[c], c)

    if na_as_zero:
        n_na_filled = int(comp.isna().to_numpy().sum())
        if n_na_filled:
            print(f"  --na-as-zero: {n_na_filled:,} missing component values read as 0")
        comp = comp.fillna(0.0)

    n_true = comp.sum(axis=1, skipna=True)
    n_missing = comp.isna().sum(axis=1)
    max_possible = n_true + n_missing

    group = pd.Series(np.nan, index=gdf.index, dtype=float)
    group[n_true >= min_true] = 1.0
    group[max_possible < min_true] = 0.0

    n_ambiguous = int(group.isna().sum())
    if n_ambiguous:
        print(f"  WARNING: {n_ambiguous:,} features have missing flag values and "
              f"cannot be assigned either way (they fall short of {min_true} on the "
              f"observed flags but could reach it). Dropped. Pass --na-as-zero to "
              f"read missing as 0 instead.")

    # distribution of the flag sum, and which single flag is doing the work
    print(f"  Combining {len(cols)} flags {cols} with threshold >= {min_true}:")
    dist = n_true[group.notna()].value_counts().sort_index()
    dist_text = ", ".join(f"{int(k)} set: {v:,}" for k, v in dist.items())
    print(f"    flag sum -> {dist_text}")
    marg = {c: int(comp.loc[group.notna(), c].sum(skipna=True)) for c in cols}
    print(f"    set per flag -> {marg}")
    only = {}
    for c in cols:
        others = [o for o in cols if o != c]
        is_only = (comp[c] == 1) & (comp[others].sum(axis=1, skipna=True) == 0)
        only[c] = int((is_only & group.notna()).sum())
    print(f"    the ONLY flag set -> {only}")

    gdf["_group"] = group
    gdf = gdf[gdf["_group"].notna()]

    n1 = int((gdf["_group"] == 1).sum())
    n0 = int((gdf["_group"] == 0).sum())
    joined = " + ".join(cols)
    if min_true == 1:
        lab1, lab0 = f"{joined} > 0", f"{joined} = 0"
    elif min_true == len(cols):
        lab1, lab0 = f"all of {joined}", f"not all of {joined}"
    else:
        lab1, lab0 = f"{joined} >= {min_true}", f"{joined} < {min_true}"
    print(f"  Group 1 ({lab1}): {n1:,} features | "
          f"Group 0 ({lab0}): {n0:,} features")
    if n1 == 0 or n0 == 0:
        raise ValueError(
            f"One group is empty ({n1} and {n0}). With threshold >= {min_true} over "
            f"{cols}, every feature falls on one side. Check the flag coding, or "
            f"adjust --min-true."
        )
    return gdf, lab1, lab0


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

    # --- 4. Welch t-test on the RAW values: the arithmetic-average test ---
    # This is the difference in plain averages, with a confidence interval
    # on that difference. It answers "how much bigger is the average?" --
    # a different question from the log test above, which answers "how
    # many times bigger is the typical feature?". Both are reported.
    t_raw = stats.ttest_ind(v1, v0, equal_var=False)
    diff_raw = float(v1.mean() - v0.mean())
    se_raw = float(np.sqrt(v1.var(ddof=1) / n1 + v0.var(ddof=1) / n0))
    dof_raw = float(getattr(t_raw, "df", n1 + n0 - 2))
    tcrit_raw = float(stats.t.ppf(1 - ALPHA / 2, dof_raw)) if np.isfinite(dof_raw) else np.nan
    rows.append({
        "test": "welch_t_on_raw",
        "statistic": float(t_raw.statistic),
        "pvalue": float(t_raw.pvalue),
        "dof": dof_raw,
        "effect": f"mean_difference_{unit}",
        "effect_size": diff_raw,
        "effect_ci_low": diff_raw - tcrit_raw * se_raw,
        "effect_ci_high": diff_raw + tcrit_raw * se_raw,
        "n_group_1": n1, "n_group_0": n0,
        "note": "difference in arithmetic means; sensitive to the largest features",
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
                    by_col=None, plot=False, verbose=True, group_labels=None):
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

    mean1, mean0 = float(v1.mean()), float(v0.mean())
    base.update({
        "tested": True, "reason": "",
        # --- arithmetic averages -----------------------------------------
        f"mean_1_{unit}": mean1,
        f"mean_0_{unit}": mean0,
        f"mean_difference_{unit}": t.loc["welch_t_on_raw", "effect_size"],
        f"mean_diff_ci_low_{unit}": t.loc["welch_t_on_raw", "effect_ci_low"],
        f"mean_diff_ci_high_{unit}": t.loc["welch_t_on_raw", "effect_ci_high"],
        "mean_ratio": mean1 / mean0 if mean0 > 0 else np.nan,
        "tstat_raw": t.loc["welch_t_on_raw", "statistic"],
        "pvalue_raw_t": t.loc["welch_t_on_raw", "pvalue"],
        # --- medians and the skew-robust comparison ----------------------
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
        "skew_group_1": summary.loc[0, "skewness"],
        "skew_group_0": summary.loc[1, "skewness"],
    })

    if verbose:
        mr = base["mean_ratio"]
        print(f"  {label}")
        print(f"      average   {mean1:>12,.4g} vs {mean0:>12,.4g} {unit}"
              f"   diff {base[f'mean_difference_{unit}']:>+11,.4g}"
              f"   {mr:.3g}x   p={base['pvalue_raw_t']:.3g}")
        print(f"      median    {np.median(v1):>12,.4g} vs {np.median(v0):>12,.4g} {unit}"
              f"   geometric ratio {base['geometric_mean_ratio']:.3g}x"
              f"   p={base['pvalue_log']:.3g}")
        print(f"      n = {n1:,} / {n0:,}")

    tag = f"{safe_name(var)}_{safe_name(label)}"
    summary.to_csv(outdir / f"summary_{tag}.csv", index=False)
    tests.to_csv(outdir / f"tests_{tag}.csv", index=False)

    if by_col:
        bd = breakdown(sub, by_col, unit, min_per_group=max(3, min_n // 2))
        if bd is not None:
            bd.to_csv(outdir / f"by_{safe_name(by_col)}_{tag}.csv", index=False)

    if plot:
        make_plots(v1, v0, var, measure, unit, label,
                   outdir / f"compare_{tag}.png", group_labels=group_labels)

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
def make_plots(v1, v0, var, measure, unit, label, out_path, group_labels=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lab1, lab0 = group_labels or (f"{var}=1", f"{var}=0")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    # Histogram on a log x-axis. A linear axis squashes a skewed size
    # distribution into the leftmost sliver of the plot and shows nothing.
    ax = axes[0]
    all_v = np.concatenate([v1, v0])
    bins = np.logspace(np.log10(all_v.min()), np.log10(all_v.max()), 40)
    ax.hist(v0, bins=bins, alpha=0.55, label=f"{lab0} (n={len(v0):,})", color="#4C72B0")
    ax.hist(v1, bins=bins, alpha=0.55, label=f"{lab1} (n={len(v1):,})", color="#C44E52")
    ax.axvline(np.median(v0), color="#4C72B0", linestyle="--", linewidth=1.5)
    ax.axvline(np.median(v1), color="#C44E52", linestyle="--", linewidth=1.5)
    ax.set_xscale("log")
    ax.set_xlabel(f"{measure} ({unit}, log scale)")
    ax.set_ylabel("number of features")
    ax.set_title(f"{label}\n{measure} by {var} (dashed = medians)")
    ax.legend(fontsize=9)

    ax = axes[1]
    short = [lab0 if len(lab0) <= 24 else "group 0",
             lab1 if len(lab1) <= 24 else "group 1"]
    tick_kw = {"tick_labels": short}
    flier = dict(marker=".", markersize=3, alpha=0.4)
    try:
        ax.boxplot([v0, v1], showfliers=True, flierprops=flier, **tick_kw)
    except TypeError:
        ax.boxplot([v0, v1], labels=short, showfliers=True, flierprops=flier)
    ax.set_yscale("log")
    ax.set_ylabel(f"{measure} ({unit}, log scale)")
    ax.set_title(f"{label}")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def make_overview_plot(results, var, out_path, group_labels=None):
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
    lab1, lab0 = group_labels or (f"{var}=1", f"{var}=0")
    ax.set_xlabel(f"geometric mean size ratio, [{lab1}] vs [{lab0}] (log scale)")
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
def interpret(results, var, composition, geom_info=None, inflation=None,
              group_labels=None):
    lab1, lab0 = group_labels or (f"{var}=1", f"{var}=0")
    print("\n" + "=" * 74)
    print("READING THE RESULTS")
    print("=" * 74)
    print(f"Group 1 = {lab1}   |   Group 0 = {lab0}\n")

    if geom_info:
        print(f"Size measured from bounding boxes in '{geom_info['column']}' "
              f"(axis order {geom_info['order']}), not from feature geometry.")
        if inflation and inflation.get("pvalue", 1.0) < ALPHA:
            print("Envelope inflation differs across groups, so these numbers are "
                  "partly a shape/orientation difference. Prefer the run without "
                  "--geometry-from.")
        print()

    tested = results[results["tested"]]
    if tested.empty:
        print("No stratum had enough features on both sides to test. Lower "
              "--min-n, drop --element-col, or check the flag.")
        return

    # --- average size, which is usually the headline being asked for -----
    print("AVERAGE SIZE BY GROUP")
    for _, r in tested.iterrows():
        u = r["unit"]
        mr = r.get("mean_ratio", np.nan)
        print(f"  {r['stratum']}")
        print(f"      group 1 average: {r[f'mean_1_{u}']:>14,.4g} {u}   (n = {r['n_group_1']:,})")
        print(f"      group 0 average: {r[f'mean_0_{u}']:>14,.4g} {u}   (n = {r['n_group_0']:,})")
        lo = r.get(f"mean_diff_ci_low_{u}", np.nan)
        hi = r.get(f"mean_diff_ci_high_{u}", np.nan)
        print(f"      difference:      {r[f'mean_difference_{u}']:>+14,.4g} {u}"
              f"   95% CI [{lo:,.4g}, {hi:,.4g}]   {mr:.3g}x"
              f"   p = {r['pvalue_raw_t']:.3g}")
    print()

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
            print(f"  {r['stratum']}: group 1 features are "
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
        print(f"\nNOTE: in {list(diverge['stratum'])}, the difference in AVERAGES is "
              f"significant while the skew-robust comparison is not. That gap is the "
              f"largest few features doing the work: a handful of outsized ones pull "
              f"the mean without the typical feature differing. Quote the average if "
              f"total size is what matters (how much land, how much road); quote the "
              f"median and geometric ratio if the typical feature is what matters.")

    if tested["skew_group_1"].max() > 2 or tested["skew_group_0"].max() > 2:
        print(f"\nSkewness is high (max {max(tested['skew_group_1'].max(), tested['skew_group_0'].max()):.1f}), "
              f"so the average sits well above the typical feature in both groups -- "
              f"compare the averages with the medians above. The average is the right "
              f"number for totals (how much area in all), the median and geometric "
              f"ratio for the typical feature. They are reported together because with "
              f"skew this strong they answer different questions.")

    if composition is not None and np.isfinite(composition["chi2_pvalue"].iloc[0]):
        if composition["chi2_pvalue"].iloc[0] < ALPHA:
            print(f"\nFeature-type composition differs across groups "
                  f"(Cramer's V = {composition['cramers_v'].iloc[0]:.3f}), so the "
                  f"pooled row is confounded. Per-stratum rows are the answer.")
    print("=" * 74)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def autodetect_coordinate_column(df):
    """
    Find the coordinate column in a table that has no geometry.

    This version expects one, so it is detected rather than demanded. The
    best candidate wins; if two look equally plausible the choice is
    stated along with the runner-up, because picking the wrong column
    silently would produce a confident wrong answer.
    """
    cands = coord_candidates(df, geom_name="__none__")
    if not cands:
        cols = [c for c in df.columns if not c.startswith("_")]
        raise ValueError(
            "No column in this table parses as coordinates, so there is nothing "
            f"to measure. Columns present: {cols}\n"
            "Run with --inspect to see what the file holds, or name the column "
            "with --geometry-from."
        )
    chosen = cands[0]
    print(f"  Auto-detected coordinate column '{chosen['column']}' "
          f"({chosen['shape']}, {chosen['coverage']:.0%} parseable)")
    if len(cands) > 1:
        others = ", ".join(f"'{c['column']}'" for c in cands[1:4])
        print(f"    other columns also parse as coordinates ({others}); "
              f"use --geometry-from to pick a different one")
    return chosen["column"]


def main(args):
    outdir = Path(args.outdir)
    # CSV-compatible: a table with no geometry is a normal input here, not
    # an error, because the coordinates are expected to be in a column.
    gdf = load_features(args.input, layer=args.layer,
                        geometry_from=args.geometry_from,
                        allow_tabular=True)

    has_geometry = (isinstance(gdf, gpd.GeoDataFrame)
                    and "geometry" in gdf
                    and gdf.geometry.notna().any())

    # Inspecting a bare table: show the columns so the coordinate column
    # and the flags can be found, then stop.
    if args.inspect and not has_geometry and not args.geometry_from:
        inspect_tabular(gdf)
        return

    geometry_from = args.geometry_from
    if geometry_from is None and not has_geometry:
        geometry_from = autodetect_coordinate_column(gdf)

    geom_info = None
    if geometry_from:
        gdf, geom_info = build_geometry_from_column(
            gdf, geometry_from, args.coords_as,
            args.bbox_order, args.geometry_crs)

    if not isinstance(gdf, gpd.GeoDataFrame) or gdf.geometry.isna().all():
        if args.inspect:
            inspect_tabular(gdf)
            return
        raise ValueError("Input has no usable geometry. Pass --geometry-from "
                         "COLUMN if the coordinates live in an attribute column.")

    geom_name = gdf.geometry.name
    gdf = clean_geometry(gdf)

    if args.inspect:
        inspect(gdf, geom_name)
        return

    if args.var and args.vars:
        raise ValueError("Use --var (one column) or --vars (several combined), "
                         "not both.")
    if not args.var and not args.vars:
        raise ValueError("--var or --vars is required "
                         "(or use --inspect to explore the file).")
    if args.vars and args.true_value:
        raise ValueError("--true-value applies to a single --var; with --vars "
                         "each column is coerced to 0/1 on its own.")

    group_cols = args.vars if args.vars else [args.var]
    min_true = args.min_true if args.min_true is not None else 1
    if args.vars and not (1 <= min_true <= len(args.vars)):
        raise ValueError(f"--min-true must be between 1 and {len(args.vars)} "
                         f"(got {min_true}).")

    outdir.mkdir(parents=True, exist_ok=True)

    # element-type column
    element_col = args.element_col
    if element_col is None and args.element_auto:
        cands = element_candidates(gdf, geom_name)
        cands = [c for c in cands if c["column"] not in group_cols]
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

    if args.vars:
        gdf, lab1, lab0 = prepare_groups_multi(
            gdf, group_cols, min_true=min_true, na_as_zero=args.na_as_zero)
        default_label = (f"any_of_{'_'.join(group_cols)}" if min_true == 1
                         else f"atleast{min_true}_of_{'_'.join(group_cols)}")
    else:
        gdf, lab1, lab0 = prepare_groups(gdf, args.var,
                                         true_value=args.true_value)
        default_label = args.var

    var_label = args.group_label or default_label
    group_labels = (lab1, lab0)

    inflation = None
    if geom_info and geom_info["had_true_geometry"]:
        inflation = envelope_inflation_check(gdf, var_label, args.crs)
    elif geom_info:
        print(f"\nNOTE: size comes from the bounding boxes in "
              f"'{geom_info['column']}', not from the features themselves. A box "
              f"is an upper bound on a feature's extent, and the gap between the "
              f"two depends on shape and orientation. There is no real geometry "
              f"in this input to check that against.")

    composition = composition_check(gdf, var_label, element_col)

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
        row, _, _ = compare_stratum(sub, label, measure, unit, var_label,
                                    args.min_n, outdir, by_col=args.by,
                                    plot=args.plot, group_labels=group_labels)
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
                        pooled, "POOLED (all features)", measure, unit, var_label,
                        args.min_n, outdir, by_col=args.by, plot=args.plot,
                        group_labels=group_labels)
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

    if geom_info:
        res["geometry_source"] = f"column:{geom_info['column']}"
        res["bbox_order"] = geom_info["order"]

    comp_path = outdir / f"composition_{safe_name(var_label)}.csv"
    all_path = outdir / f"all_comparisons_{safe_name(var_label)}.csv"
    composition.to_csv(comp_path, index=False)
    res.to_csv(all_path, index=False)
    if inflation:
        pd.DataFrame([inflation]).to_csv(
            outdir / f"envelope_inflation_{safe_name(var_label)}.csv", index=False)

    interpret(res, var_label, composition, geom_info, inflation, group_labels)

    print(f"\nSaved {all_path}")
    print(f"Saved {comp_path}")
    print(f"Per-stratum summary/tests files in {outdir}/")
    if skipped_points:
        print(f"({skipped_points:,} point features were counted but not sized.)")

    if args.plot:
        ov = outdir / f"overview_{safe_name(var_label)}.png"
        if make_overview_plot(res, var_label, ov, group_labels):
            print(f"Saved {ov}")


def build_parser():
    p = argparse.ArgumentParser(
        description="CSV-compatible: compare feature size between the two groups "
                    "of a binary variable, reading coordinates from a column such "
                    "as 'boundaries'. Stratified by geometry type and element type.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Start with --inspect on a file you have not seen before. "
               "For a CSV the coordinate column is found automatically.",
    )
    p.add_argument("--input", required=True,
                   help="Any GDAL-readable vector file (GeoJSON, GPKG, shapefile, ...).")
    p.add_argument("--inspect", action="store_true",
                   help="Describe the file and exit; suggests usable columns.")
    p.add_argument("--var", default=None,
                   help="Binary grouping column (e.g. is_europe).")
    p.add_argument("--vars", nargs="+", default=None, dest="vars",
                   help="Several binary columns combined into one grouping: "
                        "group 1 is a feature with at least --min-true of them "
                        "set. With the default --min-true 1 this is 'the sum of "
                        "these flags > 0'. Use instead of --var.")
    p.add_argument("--min-true", type=int, default=None, dest="min_true",
                   help="How many of the --vars columns must be set for group 1 "
                        "(default 1, i.e. sum > 0). Set it to the number of "
                        "columns to require all of them.")
    p.add_argument("--na-as-zero", action="store_true", dest="na_as_zero",
                   help="Read a missing flag value as 0. Without it, features "
                        "whose group cannot be determined from the observed "
                        "flags are dropped and counted.")
    p.add_argument("--group-label", default=None, dest="group_label",
                   help="Name used in output filenames for the grouping.")
    p.add_argument("--true-value", default=None, dest="true_value",
                   help="For a non-binary column, the value defining group 1.")
    p.add_argument("--layer", default=None, help="Layer name for multi-layer files.")
    p.add_argument("--geometry-from", default=None, dest="geometry_from",
                   help="The coordinate column to measure (e.g. --geometry-from "
                        "boundaries). Optional: for a table with no geometry it "
                        "is auto-detected. Give it to override the choice, or to "
                        "measure a coordinate column in a file that also has "
                        "real geometry.")
    p.add_argument("--coords-as", default="auto", dest="coords_as",
                   choices=["auto", "bbox", "polygon", "line", "point"],
                   help="What the numbers in that column mean. auto: 4 numbers "
                        "= bbox, 2 = point, 6+ = ring.")
    p.add_argument("--bbox-order", default="auto", dest="bbox_order",
                   choices=["auto", "xyxy", "yxyx"],
                   help="Axis order in that column. xyxy = [minx miny maxx maxy] "
                        "(lon/lat), yxyx = [miny minx maxy maxx] (lat/lon). "
                        "auto sniffs it from the values.")
    p.add_argument("--geometry-crs", default="EPSG:4326", dest="geometry_crs",
                   help="CRS of the coordinates in that column (default EPSG:4326).")
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
