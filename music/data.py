"""Versioned download and deterministic track-level preparation."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd
import requests

DATA_URL = "https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset/resolve/635b034f69257814eff850a5c2b3346fe458134f/dataset.csv?download=true"
KAGGLE_URL = "https://www.kaggle.com/api/v1/datasets/download/maharshipandya/-spotify-tracks-dataset"
FEATURES = ["danceability", "energy", "loudness", "speechiness", "acousticness",
            "instrumentalness", "liveness", "valence", "tempo", "duration_ms"]


def download(destination, source="kaggle"):
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    url = KAGGLE_URL if source == "kaggle" else DATA_URL
    archive = path.with_suffix(".download")
    with requests.get(url, stream=True, timeout=(30, 90)) as response:
        response.raise_for_status()
        with archive.open("wb") as handle:
            for chunk in response.iter_content(64 * 1024):
                handle.write(chunk)
    if source == "kaggle":
        if not zipfile.is_zipfile(archive):
            raise ValueError("Kaggle did not return a ZIP. Retry with --source huggingface.")
        with zipfile.ZipFile(archive) as zipped:
            filename = next(name for name in zipped.namelist() if Path(name).name == "dataset.csv")
            temporary.write_bytes(zipped.read(filename))
        archive.unlink()
    else:
        archive.replace(temporary)
    # Validate before replacing an existing dataset.
    prepare(temporary)
    temporary.replace(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    path.with_suffix(".source.json").write_text(json.dumps({
        "url": url, "sha256": digest,
        "original": "https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset"
    }, indent=2), encoding="utf-8")
    return path


def prepare(path):
    df = pd.read_csv(path)
    required = set(FEATURES + ["track_id", "track_name", "artists", "track_genre", "popularity"])
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    df = df.dropna(subset=["track_id", "track_name", "artists"]).copy()
    for column in FEATURES + ["popularity"]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=FEATURES + ["popularity"])
    df = df[(df.duration_ms > 0) & df.popularity.between(0, 100)]
    for column in ["danceability", "energy", "speechiness", "acousticness",
                   "instrumentalness", "liveness", "valence"]:
        df = df[df[column].between(0, 1)]
    genres = df.groupby("track_id")["track_genre"].agg(
        lambda x: "|".join(sorted(set(x.dropna().astype(str)))))
    # Preserve all genre memberships while choosing a deterministic metadata row.
    df = df.sort_values(["track_id", "popularity", "track_genre"], ascending=[True, False, True])
    df = df.drop_duplicates("track_id").copy()
    df["genres"] = df.track_id.map(genres)
    return df.drop(columns=["Unnamed: 0"], errors="ignore").reset_index(drop=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/dataset.csv")
    parser.add_argument("--source", choices=["kaggle", "huggingface"], default="kaggle")
    args = parser.parse_args()
    print(download(args.output, args.source))
