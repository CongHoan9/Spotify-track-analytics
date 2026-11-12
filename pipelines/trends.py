import argparse
from pyspark.sql import SparkSession, functions as F


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/events/*.jsonl")
    p.add_argument("--format", choices=["json", "parquet"], default="json")
    p.add_argument("--output", default="data/lake/gold/trends")
    args = p.parse_args()
    spark = SparkSession.builder.appName("music-trends").getOrCreate()
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    events = spark.read.format(args.format).load(args.input).dropDuplicates(["event_id"])
    events = events.withColumn("event_time", F.to_timestamp("event_time")).dropna(subset=["event_time", "user_id"])
    daily = events.groupBy(F.to_date("event_time").alias("day"), "source", "event_type").agg(
        F.count("*").alias("events"), F.countDistinct("user_id").alias("active_users"))
    daily.write.mode("overwrite").parquet(args.output)
    spark.stop()
