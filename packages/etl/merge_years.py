"""merge_year.py - fold a year-only output folder into the full clean_output_national files.

Usage:
    python3 merge_year.py clean_output_national/year_2025/
"""
import os
import shutil
import sys
import pandas as pd

FULL_DIR = "clean_output_national/"
CHUNK = 500_000


def merge(full_path, new_path, key_cols):
    """Replace any rows in full_path whose year appears in new_path, then add new_path's rows."""
    new = pd.read_csv(new_path, dtype=str)
    full_cols = list(pd.read_csv(full_path, nrows=0).columns)

    if set(new.columns) != set(full_cols):
        sys.exit(f"Column mismatch for {new_path}:\n"
                 f"  only in full: {sorted(set(full_cols) - set(new.columns))}\n"
                 f"  only in new:  {sorted(set(new.columns) - set(full_cols))}")
    new = new[full_cols]

    years = set(new['year'])
    print(f"{os.path.basename(full_path)}: adding {len(new):,} rows for year(s) {sorted(years)}")

    backup = full_path + ".bak"
    shutil.copy2(full_path, backup)          # keep the original until the merge succeeds
    tmp = full_path + ".tmp"

    kept = removed = 0
    with open(tmp, 'w', newline='') as out:
        first = True
        for chunk in pd.read_csv(full_path, dtype=str, chunksize=CHUNK):
            mask = chunk['year'].isin(years)
            removed += int(mask.sum())
            chunk = chunk[~mask]
            kept += len(chunk)
            chunk.to_csv(out, index=False, header=first)
            first = False
        new.to_csv(out, index=False, header=first)   # header only if the file was empty

    os.replace(tmp, full_path)
    print(f"  kept {kept:,}, replaced {removed:,}, added {len(new):,}  (backup: {backup})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    year_dir = sys.argv[1]

    for name in ("geographies.csv", "results.csv"):
        new_path = os.path.join(year_dir, name)
        full_path = os.path.join(FULL_DIR, name)
        if not os.path.exists(new_path):
            sys.exit(f"{new_path} not found")
        if not os.path.exists(full_path):
            sys.exit(f"{full_path} not found")
        merge(full_path, new_path, None)