"""Held-out clustering evaluation and controlled, repeated partition benchmarks."""
import random
import statistics
import time

from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.clustering import KMeans
from pyspark.ml.evaluation import ClusteringEvaluator
from pyspark.ml.feature import StandardScaler
from pyspark.sql import functions as F

MAX_ITER = 50
TOLERANCE = 1e-4


def fit_clusters(assembled, candidates, model_path):
    # Hash by stable track_id after deduplication: a track cannot leak across splits.
    bucket = F.pmod(F.xxhash64('track_id'), F.lit(100))
    split = assembled.withColumn('_bucket', bucket)
    train = split.filter('_bucket < 70')
    validation = split.filter('_bucket >= 70 AND _bucket < 85')
    test = split.filter('_bucket >= 85')
    sizes = {'train': train.count(), 'validation': validation.count(), 'test': test.count()}
    if min(sizes.values()) <= max(candidates):
        raise ValueError(f'Insufficient rows for requested k candidates: {sizes}')
    scaler = StandardScaler(inputCol='raw_features', outputCol='features',
                            withMean=True, withStd=True).fit(train)
    train_scaled = scaler.transform(train).select('track_id', 'features').cache()
    val_scaled = scaler.transform(validation).select('track_id', 'features').cache()
    train_scaled.count(); val_scaled.count()
    evaluator = ClusteringEvaluator(featuresCol='features', predictionCol='prediction',
                                    distanceMeasure='squaredEuclidean')
    trials = []
    winner = None
    best = float('-inf')
    for k in sorted(set(candidates)):
        started = time.perf_counter()
        model = KMeans(k=k, seed=42, maxIter=MAX_ITER, tol=TOLERANCE, featuresCol='features').fit(train_scaled)
        predicted = model.transform(val_scaled)
        occupied = predicted.select('prediction').distinct().count()
        score = evaluator.evaluate(predicted) if occupied >= 2 else None
        trials.append({'k': k, 'validation_silhouette': score,
                       'train_cost': float(model.summary.trainingCost),
                       'iterations': int(model.summary.numIter),
                       'stopped_at_iteration_limit': int(model.summary.numIter) >= MAX_ITER,
                       'validation_occupied_clusters': occupied,
                       'seconds': time.perf_counter()-started})
        print('K_SELECTION', trials[-1], flush=True)
        # Exact ties prefer smaller k because the candidates are sorted.
        if score is not None and score > best:
            best = score
            winner = model
    if winner is None:
        raise ValueError('Every candidate collapsed to a single validation cluster')
    selected_k = winner.getK()
    test_predictions = winner.transform(scaler.transform(test))
    if test_predictions.select('prediction').distinct().count() < 2:
        raise ValueError('Selected model produces fewer than two clusters on test')
    test_score = evaluator.evaluate(test_predictions)
    evaluation_model = PipelineModel(stages=[scaler, winner])
    evaluation_model.write().overwrite().save(str(model_path / 'evaluation'))
    train_scaled.unpersist(); val_scaled.unpersist()
    # Refit for descriptive catalog analysis only, after finishing held-out evaluation.
    final = Pipeline(stages=[
        StandardScaler(inputCol='raw_features', outputCol='features', withMean=True, withStd=True),
        KMeans(k=selected_k, seed=42, maxIter=MAX_ITER, tol=TOLERANCE, featuresCol='features')]).fit(assembled)
    predictions = final.transform(assembled).cache()
    full_score = evaluator.evaluate(predictions)
    final.write().overwrite().save(str(model_path / 'kmeans'))
    # Verify persistence by reloading and comparing predictions on stable IDs.
    probe = assembled.orderBy('track_id').limit(100).cache()
    before = {r.track_id: r.prediction for r in final.transform(probe).select('track_id', 'prediction').collect()}
    restored = PipelineModel.load(str(model_path / 'kmeans'))
    after = {r.track_id: r.prediction for r in restored.transform(probe).select('track_id', 'prediction').collect()}
    if before != after:
        raise AssertionError('Saved model changed predictions after reload')
    probe.unpersist()
    return predictions, {
        'selected_k': selected_k, 'seed': 42, 'max_iter': MAX_ITER, 'tol': TOLERANCE,
        'split_method': 'pmod(xxhash64(track_id),100): train<70, validation<85, test>=85',
        'split_rows': sizes, 'selection_metric': 'validation silhouette, squaredEuclidean',
        'trials': trials, 'test_silhouette': test_score,
        'full_catalog_silhouette': full_score, 'reload_prediction_check_rows': len(before),
    }


def benchmark(spark, input_path, repetitions=3):
    """Warm each configuration, then interleave measured runs; no Spark DataFrame cache."""
    old_aqe = spark.conf.get('spark.sql.adaptive.enabled')
    old_shuffle = spark.conf.get('spark.sql.shuffle.partitions')
    spark.conf.set('spark.sql.adaptive.enabled', 'false')
    measured, warmups = [], []
    randomizer = random.Random(42)

    def execute(partitions, repeat, phase):
        spark.conf.set('spark.sql.shuffle.partitions', str(partitions))
        spark.sparkContext.setJobGroup(f'benchmark-{phase}-p{partitions}-r{repeat}',
                                       'Identical aggregation; hash partition by artists')
        started = time.perf_counter()
        frame = spark.read.parquet(str(input_path)).select('artists', 'popularity')
        checksum = (frame.repartition(partitions, 'artists').groupBy('artists')
                    .agg(F.sum('popularity').alias('s')).agg(F.sum('s')).first()[0])
        return {'partitions': partitions, 'repeat': repeat, 'seconds': time.perf_counter()-started,
                'checksum': checksum}

    try:
        for partitions in [2, 4, 8]:
            warmups.append(execute(partitions, 0, 'warmup'))
        for repeat in range(1, repetitions+1):
            order = [2, 4, 8]
            randomizer.shuffle(order)
            for partitions in order:
                result = execute(partitions, repeat, 'measured')
                measured.append(result)
                print('BENCHMARK', result, flush=True)
    finally:
        spark.conf.set('spark.sql.adaptive.enabled', old_aqe)
        spark.conf.set('spark.sql.shuffle.partitions', old_shuffle)
        spark.sparkContext.setLocalProperty('spark.jobGroup.id', None)
        spark.sparkContext.setLocalProperty('spark.job.description', None)
    if any(abs(r['checksum']-measured[0]['checksum']) > .001 for r in measured+warmups):
        raise AssertionError('Benchmark configurations produced different checksums')
    summary = []
    for partitions in [2, 4, 8]:
        times = [r['seconds'] for r in measured if r['partitions'] == partitions]
        summary.append({'partitions': partitions, 'median_seconds': statistics.median(times),
                        'min_seconds': min(times), 'max_seconds': max(times), 'repetitions': len(times)})
    return measured, {'warmups': warmups, 'summary': summary, 'aqe_enabled': False,
                      'partition_key': 'artists', 'repetitions': repetitions,
                      'measurement_order': [r['partitions'] for r in measured]}
