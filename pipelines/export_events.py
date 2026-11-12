"""Export real events as JSONL for reproducible batch analytics."""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app import Event


def serialize(event):
    return {key: getattr(event, key) for key in ["event_id", "user_id", "track_id", "event_type", "source"]} | {
        "event_time": event.event_time.isoformat()}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="data/events/real.jsonl")
    args = p.parse_args()
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with Session(create_engine(os.getenv("DATABASE_URL", "sqlite:///./data/app.db"))) as session:
        with path.open("w", encoding="utf-8") as handle:
            for event in session.scalars(select(Event).execution_options(yield_per=1000)):
                handle.write(json.dumps(serialize(event)) + "\n")
