"""Temporal evaluation of content recommendations on real application feedback."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from music.recommender import Recommender


def evaluate(bundle, events_path, cutoff, k=20):
    model = Recommender(bundle)
    events = pd.read_json(events_path, lines=True)
    events = events[events.source == "real"].drop_duplicates("event_id").copy()
    events["event_time"] = pd.to_datetime(events.event_time, utc=True)
    timestamp = pd.Timestamp(cutoff)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    train = events[events.event_time < timestamp]
    test = events[events.event_time >= timestamp]
    scores, recommended, skipped = [], set(), 0
    for user_id, future in test.groupby("user_id"):
        past = train[train.user_id == user_id]
        states = past[past.event_type.isin(["like", "dislike", "unlike"])].sort_values(
            ["event_time", "event_id"]).drop_duplicates("track_id", keep="last")
        likes = states[states.event_type == "like"].track_id.tolist()
        blocked = states[states.event_type == "dislike"].track_id.tolist()
        seen = set(past.track_id)
        truth = set(future[future.event_type == "like"].track_id) - seen
        truth &= set(model.index)
        if not truth:
            skipped += 1
            continue
        result = model.recommend(likes, set(blocked) | seen, limit=k)
        ids = [r["track_id"] for r in result]
        hits = np.array([item in truth for item in ids], dtype=float)
        dcg = float(np.sum(hits / np.log2(np.arange(len(hits)) + 2)))
        ideal = float(np.sum(1 / np.log2(np.arange(min(k, len(truth))) + 2)))
        scores.append({"recall": float(hits.sum()/len(truth)), "ndcg": dcg/ideal,
                       "cold_user": not bool(likes)})
        recommended.update(ids)
    if not scores:
        raise ValueError("No evaluable users with new positive real interactions after cutoff")
    return {"model": model.manifest["model_type"], "k": k, "cutoff": str(timestamp),
            "evaluated_users": len(scores), "skipped_users": skipped,
            "cold_users": sum(s["cold_user"] for s in scores),
            "recall_at_k": float(np.mean([s["recall"] for s in scores])),
            "ndcg_at_k": float(np.mean([s["ndcg"] for s in scores])),
            "catalog_coverage": len(recommended)/len(model.tracks),
            "note": "Fixed historical catalog; verify catalog/model availability before cutoff. No playback claims."}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bundle", default="artifacts/baseline")
    p.add_argument("--events", default="data/events/real.jsonl")
    p.add_argument("--cutoff", required=True)
    p.add_argument("--k", type=int, default=20)
    p.add_argument("--output", default="reports/ranking-metrics.json")
    args = p.parse_args()
    if args.k < 1:
        p.error("k must be positive")
    result = evaluate(args.bundle, args.events, args.cutoff, args.k)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
