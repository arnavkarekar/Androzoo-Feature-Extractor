import glob   # find files using wildcard patterns like "dataset/*/*/*"
import os     # file paths, listing folders, renaming files
import sys    # read command-line arguments

import pandas as pd          # tables (DataFrames) and reading/writing parquet + csv
from loguru import logger    # the logging library androguard uses internally

from extract_features import FEATURE_NAMES, get_features   # our feature extractor from extract_features.py

logger.remove()   # turn off androguard's logging; it prints thousands of debug lines per APK

DATASET_DIR = "/path/to/ANDRO"   # default dataset folder: set this to where your dataset lives
INDEX_CSV = "apk_index.csv"   # name of the csv that lists every processed file (name, filepath, month)
SAVE_EVERY = 100              # write results to disk after this many new APKs


def load(path, reader):
    # if the file already exists (from an earlier run), read it so we can keep adding to it;
    # otherwise start with an empty table
    return reader(path) if os.path.exists(path) else pd.DataFrame()


def save(df, path, writer):
    writer(df, path + ".tmp")         # write to a temporary file first
    os.replace(path + ".tmp", path)   # then swap it in, so a crash mid-write never leaves a half-written file behind


def parquet_path(out_dir, label, month):
    # one file per label per month, e.g. <out_dir>/malware_2012-01.parquet
    return os.path.join(out_dir, f"{label}_{month}.parquet")


def save_all(data, index, out_dir, month):
    for label, df in data.items():   # label is "malware" or "goodware", df is that month's table
        save(df, parquet_path(out_dir, label, month), lambda d, p: d.to_parquet(p, index=False))
    # save the list of processed files (all months) as <out_dir>/apk_index.csv
    save(index, os.path.join(out_dir, INDEX_CSV), lambda d, p: d.to_csv(p, index=False))


def main(dataset_dir, start_month=None, end_month=None):
    dataset_dir = os.path.normpath(dataset_dir)   # remove any trailing "/" so path splitting below works
    out_dir = dataset_dir   # output files go in the dataset folder, next to the month folders

    index = load(os.path.join(out_dir, INDEX_CSV), pd.read_csv)   # load the list of already-processed files
    done = set(index["filepath"]) if not index.empty else set()  # set of filepaths to skip (already processed)

    # folder layout is dataset/<month>/<malware|goodware>/<file>
    # list the month folders (e.g. 2012-01, 2012-02, ...) in date order
    months = sorted(d for d in os.listdir(dataset_dir) if os.path.isdir(os.path.join(dataset_dir, d)))
    # keep only months inside the requested range (months named YYYY-MM sort correctly as text)
    months = [m for m in months if (start_month is None or m >= start_month) and (end_month is None or m <= end_month)]
    if not months:   # nothing matched the range (e.g. a typo like 2012-1 instead of 2012-01)
        print(f"no month folders between {start_month} and {end_month}")
        return
    print(f"processing {len(months)} months: {months[0]} to {months[-1]}")

    for month in months:   # handle one month at a time so only that month's data is in memory
        # load this month's malware and goodware tables (or empty ones if this month is new)
        data = {label: load(parquet_path(out_dir, label, month), pd.read_parquet)
                for label in ("malware", "goodware")}
        # every file inside <month>/<label>/
        paths = sorted(glob.glob(os.path.join(dataset_dir, month, "*", "*")))
        print(f"{month}: {len(paths)} files")
        unsaved = 0   # how many APKs were processed since the last save

        try:
            for i, path in enumerate(paths, 1):   # go through every file, counting from 1
                _, label, name = path.split(os.sep)[-3:]   # last 3 parts of the path: month, label, file name
                short_path = "/".join(path.split(os.sep)[-4:])   # path starting at the dataset folder, e.g. ANDRO/2012-01/goodware/x.apk
                if label not in data or short_path in done:   # skip unknown folders and files done in an earlier run
                    continue

                try:
                    features, package = get_features(path)   # open the APK and pull out the 8 feature lists
                except Exception as e:
                    print(f"fail  {path}: {e}")   # broken/unreadable APK: report it and move on
                    continue

                # build one row: file info plus each feature list as its own column
                row = {"name": name, "month": month, "package": package,
                       **{f: features[f] for f in FEATURE_NAMES}}
                data[label] = pd.concat([data[label], pd.DataFrame([row])], ignore_index=True)   # add row to malware or goodware table
                # add this file to the index csv table
                index = pd.concat([index, pd.DataFrame([{"name": name, "filepath": short_path, "month": month}])],
                                  ignore_index=True)
                print(f"[{month} {i}/{len(paths)}] done  {path}")   # progress message

                unsaved += 1                  # one more APK not yet written to disk
                if unsaved >= SAVE_EVERY:     # every SAVE_EVERY APKs...
                    save_all(data, index, out_dir, month)   # ...write everything to disk
                    unsaved = 0                             # and reset the counter
        finally:
            # always save at the end of each month, even if the script crashes or you press Ctrl+C
            save_all(data, index, out_dir, month)


if __name__ == "__main__":   # only runs when the script is started directly (not when imported)
    # usage: python generate_features.py [start_month] [end_month]     (always uses DATASET_DIR)
    #   e.g. python generate_features.py 2012-02 2012-06   -> 2012-02 through 2012-06
    #        python generate_features.py 2012-02           -> just 2012-02
    #        python generate_features.py                   -> every month
    start_month = sys.argv[1] if len(sys.argv) > 1 else None          # 1st argument: first month (optional)
    end_month = sys.argv[2] if len(sys.argv) > 2 else start_month     # 2nd argument: last month (defaults to start_month)
    main(DATASET_DIR, start_month, end_month)   # start processing
