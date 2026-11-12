"""Single publisher: at-least-once delivery; consumers deduplicate event_id."""
import json
import os
import time
from kafka import KafkaProducer
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.app import Event
from pipelines.export_events import serialize


def main():
    engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///./data/app.db"))
    producer = KafkaProducer(bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
                             acks="all", retries=5, value_serializer=lambda x: json.dumps(x).encode())
    try:
        while True:
            with Session(engine) as session:
                events = session.scalars(select(Event).where(Event.published.is_(False)).limit(500)).all()
                for event in events:
                    producer.send("music-events", key=event.user_id.encode(), value=serialize(event)).get(timeout=30)
                    event.published = True
                session.commit()
            time.sleep(1)
    finally:
        producer.close()


if __name__ == "__main__":
    main()
