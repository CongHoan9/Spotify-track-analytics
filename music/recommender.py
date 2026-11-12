import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from music.bundle import normalize


class Recommender:
    def __init__(self, directory):
        root = Path(directory)
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        for name, digest in self.manifest["sha256"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Artifact checksum mismatch: {name}")
        self.tracks = pd.read_csv(root / "tracks.csv").fillna("")
        self.vectors = np.load(root / "embeddings.npz", allow_pickle=False)["embeddings"]
        if len(self.tracks) != len(self.vectors) or not np.isfinite(self.vectors).all():
            raise ValueError("Invalid model bundle")
        self.index = {str(track): i for i, track in enumerate(self.tracks.track_id)}

    def records(self, indices):
        columns = ["track_id", "track_name", "artists", "genres", "popularity"]
        return self.tracks.iloc[list(indices)][columns].to_dict("records")

    def recommend(self, liked, blocked=(), genres=(), limit=20):
        seeds = [self.index[item] for item in liked if item in self.index]
        if seeds:
            profile = normalize(self.vectors[seeds].mean(axis=0))
            scores = self.vectors @ profile
            reason = "Có đặc trưng âm nhạc gần với các bài bạn thích"
        else:
            scores = self.tracks.popularity.to_numpy(dtype=float) / 100
            reason = "Khám phá theo thể loại đã chọn và độ phổ biến trong dataset"
        if genres:
            matches = self.tracks.genres.str.split("|").apply(lambda tags: bool(set(tags) & set(genres)))
            scores = scores + .15 * matches.to_numpy()
        excluded = set(liked) | set(blocked)
        result, artist_counts = [], {}
        for i in np.argsort(-scores, kind="stable"):
            row = self.tracks.iloc[i]
            artist = str(row.artists).split(";")[0]
            if row.track_id in excluded or artist_counts.get(artist, 0) >= 2:
                continue
            item = self.records([i])[0]
            item.update(score=float(scores[i]), reason=reason)
            result.append(item)
            artist_counts[artist] = artist_counts.get(artist, 0) + 1
            if len(result) == limit:
                break
        return result
