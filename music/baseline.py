import argparse
import json
from pathlib import Path

from sklearn.preprocessing import StandardScaler

from music.bundle import save_bundle
from music.data import FEATURES, prepare


def build(csv, output):
    tracks = prepare(csv)
    scaler = StandardScaler()
    vectors = scaler.fit_transform(tracks[FEATURES])
    save_bundle(output, tracks, vectors, {"model_type": "standardized_audio", "features": FEATURES})
    (Path(output) / "scaler.json").write_text(json.dumps({
        "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(), "features": FEATURES
    }), encoding="utf-8")
    return tracks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="data/raw/dataset.csv")
    parser.add_argument("--output", default="artifacts/baseline")
    args = parser.parse_args()
    print(f"Exported {len(build(args.csv, args.output))} tracks")
