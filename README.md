# AndroZoo Feature Extractor

Extracts static features from Android APKs (such as those downloaded from [AndroZoo](https://androzoo.uni.lu/)) using [Androguard](https://github.com/androguard/androguard). It's intended for building malware/goodware datasets for research.

## Features

Each APK yields its package name plus eight lists of strings:

| Feature | Source |
| --- | --- |
| `resource.entry` | Public resources, as `type/name` |
| `source.class.package` | Java packages of every class in the DEX files |
| `source.method.name` | Names of every method in the DEX files |
| `manifest.permission` | Requested permissions |
| `manifest.activity` | Declared activities |
| `manifest.action` | Intent-filter actions |
| `manifest.category` | Intent-filter categories |
| `manifest.feature` | `uses-feature` entries |

## Project layout

```
src/
  extract_features.py   # core feature extraction; also a CLI that writes features.json
  generate_features.py  # batch-processes a month-organized dataset into parquet files
  decompile.py          # decompiles a single APK to Java source + readable manifest
logs/                   # run logs (git-ignored)
samples/                # sample APKs and decompiled output (git-ignored)
```

## Setup

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install androguard lxml pandas pyarrow loguru
```

## Usage

### Batch-process a dataset: `generate_features.py`

The dataset should be organized by month and label:

```
/path/to/ANDRO/
  2012-01/
    malware/
      <sha256>.apk
    goodware/
      <sha256>.apk
  2012-02/
    ...
```

Set `DATASET_DIR` at the top of `src/generate_features.py` to your dataset folder, then run:

```bash
python src/generate_features.py                   # every month
python src/generate_features.py 2012-02           # just 2012-02
python src/generate_features.py 2012-02 2012-06   # 2012-02 through 2012-06
```

The script writes its output into the dataset folder:

- `malware_<YYYY-MM>.parquet` and `goodware_<YYYY-MM>.parquet` contain one row per APK, with `name`, `month`, `package`, and one column per feature.
- `apk_index.csv` lists every processed file (`name`, `filepath`, `month`).

Progress is saved every 100 APKs and at the end of each month, including after a crash or Ctrl+C. Files already listed in `apk_index.csv` are skipped, so re-running the script resumes where it left off. Paths in the index are stored relative to the dataset folder's parent (for example `ANDRO/2012-01/goodware/x.apk`), so keep the dataset folder's name the same between runs.

To keep a log:

```bash
python src/generate_features.py 2012-01 2012-03 2>&1 | tee logs/run.log
```

### Extract features from individual APKs: `extract_features.py`

```bash
python src/extract_features.py app1.apk app2.apk /path/to/apk_folder
```

This writes the results to `features.json` in the current directory, keyed by each APK's uppercase SHA-256 (the same format AndroZoo uses). APKs already in the file are skipped.

### Decompile one APK: `decompile.py`

Set `apk_path` at the top of `src/decompile.py`, then run:

```bash
python src/decompile.py
```

The script creates `<apk name>_decompiled/` in the current directory, containing `AndroidManifest.xml` and the decompiled Java sources under `src/`.
