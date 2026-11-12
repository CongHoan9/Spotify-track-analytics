import hashlib
import json
from pathlib import Path

import numpy as np


def normalize(vectors):
    vectors = np.asarray(vectors, dtype=np.float32)
    return vectors / np.maximum(np.linalg.norm(vectors, axis=-1, keepdims=True), 1e-8)


def save_bundle(directory, tracks, embeddings, metadata):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    vectors = normalize(embeddings)
    if len(tracks) != len(vectors) or not np.isfinite(vectors).all():
        raise ValueError("Invalid embedding alignment or nonfinite values")
    tracks.to_csv(root / "tracks.csv", index=False)
    np.savez_compressed(root / "embeddings.npz", embeddings=vectors)
    manifest = {"schema_version": 1, **metadata, "rows": len(tracks), "dimension": vectors.shape[1]}
    manifest["sha256"] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in ["tracks.csv", "embeddings.npz"]}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
