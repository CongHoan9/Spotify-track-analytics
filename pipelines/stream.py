"""Raw durable ingestion; aggregates recomputed from raw events by trends.py."""
import argparse
from pyspark.sql import SparkSession, functions as F, types as T


SCHEMA = T.StructType([T.StructField(c, T.StringType()) for c in
                       ["event_id", "user_id", "track_id", "event_type", "event_time", "source"]])

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", default="localhost:9092")
    p.add_argument("--output", default="data/lake/bronze/events")
    p.add_argument("--checkpoint", default="data/checkpoints/events-v1")
    args = p.parse_args()
    spark = SparkSession.builder.appName("music-event-ingest").getOrCreate()
    kafka = spark.readStream.format("kafka").option("kafka.bootstrap.servers", args.bootstrap).option(
        "subscribe", "music-events").option("startingOffsets", "earliest").load()
    events = kafka.select(F.from_json(F.col("value").cast("string"), SCHEMA).alias("event")).select("event.*")
    events = events.withColumn("event_time", F.to_timestamp("event_time")).filter(
        F.col("event_id").isNotNull() & F.col("event_time").isNotNull())
    events = events.withColumn("event_date", F.to_date("event_time"))
    query = events.writeStream.format("parquet").outputMode("append").partitionBy("event_date").option(
        "path", args.output).option("checkpointLocation", args.checkpoint).trigger(processingTime="10 seconds").start()
    query.awaitTermination()
