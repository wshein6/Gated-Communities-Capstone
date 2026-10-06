"""
attach_flag_positional.py

Attach a single column of binary values from a CSV onto a GeoJSON BY ROW
ORDER: row 1 of the CSV becomes the first feature, row 2 the second, and
so on. No key column is needed.

    python attach_flag_positional.py --geojson clusters.geojson --csv flag.csv
    python attach_flag_positional.py --geojson clusters.geojson --csv flag.csv --field DP

The GeoJSON is edited as JSON rather than rebuilt through a geometry
library, so feature order, coordinate precision, property order and every
existing field survive untouched. Only the one new property is added, to
every feature.

THE RISK, STATED PLAINLY
------------------------
A positional join cannot be verified from the data. If the rows and the
features are not in the same order, every value lands on the wrong
feature and NOTHING LOOKS WRONG: the file is valid, the counts are
right, the analysis runs, and the answer is nonsense. A key join can
detect a mismatch; this cannot.

So two guards are built in, and a third is available:

  * Row count must equal feature count exactly. Off by even one and the
    run stops, because an off-by-one shifts every subsequent value.
  * A header row is detected by counting, not by guessing: if the CSV
    holds exactly one row more than the file has features, the first row
    is the header.
  * --verify-against turns the blind join into a checked one. Put a
    second column in the CSV holding a field that already exists in the
    GeoJSON (an id, a name, anything), and the two are compared row by
    row. Any disagreement stops the run and reports the first few
    positions. If you can export such a column, use this.

Order is only trustworthy if the CSV came from this same GeoJSON and was
never sorted or filtered in between. Sorting a spreadsheet by any column
breaks it silently.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

TRUE_TOKENS = {"1", "1.0", "true", "t", "yes", "y"}
FALSE_TOKENS = {"0", "0.0", "false", "f", "no", "n"}

# Cells that mean "no value". A cell holding only whitespace counts here
# too, which matters because a spreadsheet's empty-looking cells are often
# not empty -- a formula returning "" writes a quoted empty string, and
# clearing a cell with the space bar leaves a space behind. These are
# deliberate blanks, not coding errors, so they are reported as blanks and
# do not raise the "unrecognised value" warning.
NULL_TOKENS = {
    "", "na", "n/a", "n.a.", "nan", "null", "none", "nil", "missing",
    "-", "--", "---", ".", "..", "?", "unknown", "unk", "tbd", "n\\a",
    "#n/a", "#na", "#null!", "#value!", "#ref!", "#div/0!", "#name?",
}
TABLE_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def read_csv_raw(path):
    """Read with no header assumption, so row counting can decide."""
    suffix = Path(path).suffix.lower()
    sep = {".tsv": "\t", ".psv": "|"}.get(suffix, ",")
    for enc in TABLE_ENCODINGS:
        try:
            # skip_blank_lines=False is essential: in a ONE-COLUMN csv an
            # empty cell is an empty line, and pandas drops those by
            # default -- silently removing rows and destroying the
            # positional alignment this whole script depends on.
            df = pd.read_csv(path, sep=sep, encoding=enc, header=None,
                             dtype=str, keep_default_na=False, na_values=[""],
                             skip_blank_lines=False)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if enc != TABLE_ENCODINGS[0]:
            print(f"  NOTE: CSV is not UTF-8; read as {enc}.")
        return df
    raise ValueError("Could not read the CSV in any supported encoding.")


def coerce_binary(series, extra_nulls=()):
    """
    Map a column to 1 / 0 / blank.

    Returns (values, blank_mask, unmapped_mask, blank_token_counts).

    Three outcomes, kept apart on purpose:
      - 1 or 0:   a usable value
      - blank:    the cell is empty, whitespace-only, or a recognised
                  null marker. An intended non-answer.
      - unmapped: the cell holds something else entirely. A data problem
                  worth seeing, which is why it is not folded into blank.
    """
    nulls = set(NULL_TOKENS) | {str(t).strip().casefold() for t in extra_nulls}

    raw = series.astype("string").str.strip()
    folded = raw.str.casefold()
    numeric = pd.to_numeric(raw, errors="coerce")

    out = pd.Series(np.nan, index=series.index, dtype=float)
    out[numeric == 1.0] = 1.0
    out[numeric == 0.0] = 0.0
    out[out.isna() & folded.isin(TRUE_TOKENS)] = 1.0
    out[out.isna() & folded.isin(FALSE_TOKENS)] = 0.0

    # A missing cell, or one that strips to nothing, or a null marker.
    blank_mask = series.isna() | folded.isna() | folded.isin(nulls)
    unmapped_mask = out.isna() & ~blank_mask

    blank_tokens = (series[blank_mask & series.notna()]
                    .astype(str).value_counts().to_dict())
    return out, blank_mask, unmapped_mask, blank_tokens


def main(args):
    # ---- the GeoJSON, as raw JSON so nothing else is disturbed ----------
    with open(args.geojson, encoding="utf-8") as f:
        gj = json.load(f)
    if gj.get("type") != "FeatureCollection" or "features" not in gj:
        raise ValueError("Input is not a GeoJSON FeatureCollection.")
    feats = gj["features"]
    n_feat = len(feats)
    print(f"GeoJSON : {Path(args.geojson).name}  {n_feat:,} features")

    # ---- the CSV, with the header decided by arithmetic -----------------
    raw = read_csv_raw(args.csv)
    n_raw = len(raw)
    print(f"CSV     : {Path(args.csv).name}  {n_raw:,} rows (before header check)")

    if args.header is True:
        has_header = True
    elif args.header is False:
        has_header = False
    elif n_raw == n_feat + 1:
        has_header = True
    elif n_raw == n_feat:
        has_header = False
    else:
        raise ValueError(
            f"The CSV has {n_raw:,} rows but the GeoJSON has {n_feat:,} "
            f"features.\nA positional join needs them equal (or one extra row "
            f"for a header).\nOff-by-one shifts every value onto the wrong "
            f"feature, so this cannot be guessed.\nCheck the CSV for a trailing "
            f"blank line, a filtered export, or a stray total row."
        )

    header_names = None
    if has_header:
        header_names = [str(v).strip() for v in raw.iloc[0].tolist()]
        raw = raw.iloc[1:].reset_index(drop=True)
        print(f"  Header row detected: {header_names}")
    else:
        print("  No header row (CSV row count equals feature count).")

    if len(raw) != n_feat:
        raise ValueError(f"After the header check the CSV has {len(raw):,} "
                         f"rows against {n_feat:,} features.")

    # ---- which column is the flag ---------------------------------------
    if raw.shape[1] == 1:
        flag_idx = 0
    elif args.flag_column is not None:
        if header_names and args.flag_column in header_names:
            flag_idx = header_names.index(args.flag_column)
        else:
            try:
                flag_idx = int(args.flag_column)
            except ValueError:
                raise KeyError(f"--flag-column '{args.flag_column}' is neither a "
                               f"header name {header_names} nor a column index.")
    else:
        raise ValueError(
            f"The CSV has {raw.shape[1]} columns. Name the one to attach with "
            f"--flag-column (a header name, or a 0-based index)."
        )

    values, blank_mask, unmapped_mask, blank_tokens = coerce_binary(
        raw.iloc[:, flag_idx], extra_nulls=args.null_values or ())
    n_blank = int(blank_mask.sum())
    n_unmapped = int(unmapped_mask.sum())

    field = args.field or (header_names[flag_idx] if header_names else "flag")
    field = str(field).strip() or "flag"
    if any(field in (feat.get("properties") or {}) for feat in feats):
        if not args.overwrite:
            raise ValueError(f"Property '{field}' already exists on some "
                             f"features. Pass --overwrite to replace it, or "
                             f"--field to use a different name.")
        print(f"  NOTE: overwriting the existing '{field}' property.")

    # ---- optional verification against an existing field ----------------
    if args.verify_against:
        if args.verify_column is None:
            if raw.shape[1] < 2:
                raise ValueError("--verify-against needs a second CSV column; "
                                 "name it with --verify-column.")
            verify_idx = 1 if flag_idx == 0 else 0
        elif header_names and args.verify_column in header_names:
            verify_idx = header_names.index(args.verify_column)
        else:
            verify_idx = int(args.verify_column)

        csv_vals = raw.iloc[:, verify_idx].astype("string").str.strip()
        geo_vals = pd.Series(
            [str((f.get("properties") or {}).get(args.verify_against, "")).strip()
             for f in feats], dtype="string")
        # compare numerically where both sides are numeric, else as text
        cn, gn = pd.to_numeric(csv_vals, errors="coerce"), pd.to_numeric(geo_vals, errors="coerce")
        if cn.notna().all() and gn.notna().all():
            mismatch = cn.ne(gn)
        else:
            mismatch = csv_vals.str.casefold().ne(geo_vals.str.casefold())
        n_bad = int(mismatch.sum())
        if n_bad:
            where = mismatch[mismatch].index[:5].tolist()
            raise ValueError(
                f"ORDER CHECK FAILED: {n_bad:,} of {n_feat:,} rows disagree with "
                f"'{args.verify_against}'.\nFirst mismatches at row positions "
                f"{where} (0-based).\nThe CSV is not in the same order as the "
                f"GeoJSON. Nothing written."
            )
        print(f"  ORDER VERIFIED against '{args.verify_against}': "
              f"all {n_feat:,} rows agree.")
    else:
        print("  Order NOT verified -- no --verify-against given. The join "
              "assumes the CSV\n  is in the GeoJSON's original order.")

    # ---- attach ----------------------------------------------------------
    for feat, v in zip(feats, values.tolist()):
        props = feat.get("properties")
        if props is None:
            props = {}
            feat["properties"] = props
        props[field] = None if pd.isna(v) else int(v)

    n_one = int((values == 1).sum())
    n_zero = int((values == 0).sum())
    print(f"\nATTACHED '{field}' to all {n_feat:,} features")
    print(f"  1      : {n_one:>8,}")
    print(f"  0      : {n_zero:>8,}")
    print(f"  blank  : {n_blank:>8,}   (empty, whitespace-only, or a null marker)")
    if n_unmapped:
        print(f"  unmapped: {n_unmapped:>7,}   *** neither binary nor a null marker")

    if blank_tokens:
        shown = {("'" + k + "'" if k.strip() != k or k == "" else k): v
                 for k, v in list(blank_tokens.items())[:8]}
        print(f"      blanks came from: {shown}")
        print(f"      (quoted entries contain whitespace)")
    if n_blank + n_one + n_zero != n_feat or n_unmapped:
        print(f"      note: 1 + 0 + blank + unmapped = "
              f"{n_one + n_zero + n_blank + n_unmapped:,} of {n_feat:,}")
    if n_unmapped:
        bad = raw.iloc[:, flag_idx][unmapped_mask]
        print(f"\n  WARNING: {n_unmapped:,} cells were neither binary nor a "
              f"recognised null marker\n  and were written as null: "
              f"{sorted(bad.astype(str).unique())[:6]}")
        print(f"  If those are meant to be blanks, add them with "
              f"--null-values, e.g. --null-values \"n/a\" \"pending\"")

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(gj, f, indent=2 if args.indent else None)
    print(f"\nWritten: {args.out}  ({n_feat:,} features, order unchanged)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Attach one column of binary values from a CSV onto a "
                    "GeoJSON by row order.")
    ap.add_argument("--geojson", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--field", default=None,
                    help="Name for the new property (default: the CSV header, "
                         "else 'flag').")
    ap.add_argument("--flag-column", default=None, dest="flag_column",
                    help="Which CSV column to attach, if it has more than one.")
    ap.add_argument("--header", default=None, action=argparse.BooleanOptionalAction,
                    help="Force header/no-header instead of deciding by row count.")
    ap.add_argument("--verify-against", default=None, dest="verify_against",
                    help="An existing GeoJSON property to check the CSV order "
                         "against, row by row. Strongly recommended.")
    ap.add_argument("--verify-column", default=None, dest="verify_column",
                    help="Which CSV column holds that check value.")
    ap.add_argument("--null-values", nargs="+", default=None, dest="null_values",
                    help="Extra cell values to treat as blank, beyond the "
                         "built-in set (empty, whitespace, NA, N/A, NULL, "
                         "NONE, -, ., ?, Excel error codes).")
    ap.add_argument("--overwrite", action="store_true",
                    help="Replace the property if it already exists.")
    ap.add_argument("--indent", action="store_true",
                    help="Pretty-print the output (roughly doubles file size).")
    ap.add_argument("--out", default="with_flag.geojson")
    a = ap.parse_args()
    try:
        main(a)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
