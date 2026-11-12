"""Run with spark-submit or python -m pipelines.batch; outputs are distributed directories."""
import argparse
from pyspark.sql import SparkSession, functions as F, Window
from pyspark.ml import Pipeline
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.clustering import KMeans
from music.data import FEATURES


def run(csv, output):
    spark = SparkSession.builder.appName("music-batch").getOrCreate()
    raw = spark.read.option("header", True).option("multiLine", True).option("escape", '"').csv(csv)
    raw.write.mode("overwrite").parquet(f"{output}/bronze/tracks")
    clean = raw.drop("_c0", "").dropna(subset=["track_id", "track_name", "artists"])
    for c in FEATURES + ["popularity"]:
        clean = clean.withColumn(c, F.col(c).cast("double"))
    clean = clean.dropna(subset=FEATURES + ["popularity"])
    clean = clean.filter((F.col("duration_ms") > 0) & F.col("popularity").between(0, 100))
    for c in ["danceability", "energy", "speechiness", "acousticness", "instrumentalness", "liveness", "valence"]:
        clean = clean.filter(F.col(c).between(0, 1))
    genres = clean.select("track_id", "track_genre").dropna().distinct()
    order = Window.partitionBy("track_id").orderBy(F.desc("popularity"), "track_genre")
    tracks = clean.withColumn("rn", F.row_number().over(order)).filter("rn = 1").drop("rn", "track_genre")
    tracks.write.mode("overwrite").parquet(f"{output}/silver/tracks")
    genres.write.mode("overwrite").parquet(f"{output}/silver/track_genres")
    stats = tracks.join(genres, "track_id").groupBy("track_genre").agg(
        F.countDistinct("track_id").alias("tracks"), F.avg("popularity").alias("avg_popularity"),
        F.avg("energy").alias("avg_energy"), F.avg("valence").alias("avg_valence"))
    stats.write.mode("overwrite").parquet(f"{output}/gold/genre_stats")
    assembler = VectorAssembler(inputCols=FEATURES, outputCol="raw_features")
    scaler = StandardScaler(inputCol="raw_features", outputCol="features", withMean=True, withStd=True)
    pipeline = Pipeline(stages=[assembler, scaler, KMeans(k=8, seed=42, featuresCol="features")])
    model = pipeline.fit(tracks)
    model.write().overwrite().save(f"{output}/models/kmeans")
    model.transform(tracks).select("track_id", "prediction").write.mode("overwrite").parquet(f"{output}/gold/clusters")
    profile = [(raw.count(), clean.count(), tracks.count(), genres.count())]
    spark.createDataFrame(profile, ["raw_rows", "valid_rows", "unique_tracks", "genre_memberships"]).write.mode("overwrite").json(f"{output}/gold/data_quality")
    spark.stop()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/raw/dataset.csv")
    p.add_argument("--output", default="data/lake")
    a = p.parse_args()
    run(a.csv, a.output)
