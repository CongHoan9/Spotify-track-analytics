import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from music.data import prepare


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/raw/dataset.csv")
    p.add_argument("--output", default="data/events/synthetic.jsonl")
    p.add_argument("--events", type=int, default=100000)
    p.add_argument("--users", type=int, default=1000)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    if args.users < 1 or args.events < 1:
        p.error("users and events must be positive")
    rng = random.Random(args.seed)
    ids = prepare(args.csv).track_id.tolist()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with path.open("w", encoding="utf-8") as handle:
        for i in range(args.events):
            event = {"event_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"synthetic:{args.seed}:{i}")),
                     "user_id": f"sim_{rng.randrange(args.users)}", "track_id": rng.choice(ids),
                     "event_type": rng.choices(["like", "dislike", "open_spotify"], [3, 1, 6])[0],
                     "event_time": (start + timedelta(seconds=i)).isoformat(), "source": "synthetic"}
            handle.write(json.dumps(event) + "\n")
