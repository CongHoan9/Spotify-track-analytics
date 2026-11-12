"""Spark-only analytical computation; bounded aggregates exported for the defense dashboard."""
import argparse
import contextlib
import hashlib
import io
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, functions as F
from pyspark.ml.feature import VectorAssembler
from pyspark.ml.stat import Correlation
from bigdata.quality import FEATURES, REQUIRED, assess, catalog
from bigdata.experiments import fit_clusters, benchmark

def analyze(csv, output, candidates=(3,5,7,9), scale_factor=1):
    started=time.perf_counter()
    root=Path(output); root.mkdir(parents=True,exist_ok=True)
    lake=Path('data/bigdata-lake');lake.mkdir(parents=True,exist_ok=True)
    events=Path('data/spark-events').resolve();events.mkdir(parents=True,exist_ok=True)
    spark=(SparkSession.builder.appName('Spotify Big Data Defense')
           .config('spark.sql.shuffle.partitions','8').config('spark.sql.session.timeZone','UTC')
           .config('spark.sql.ansi.enabled','false')
           .config('spark.eventLog.enabled','true').config('spark.eventLog.dir',events.as_uri()).getOrCreate())
    spark.sparkContext.setLogLevel('WARN')
    print('SPARK_APPLICATION_ID',spark.sparkContext.applicationId,flush=True)
    csv=Path(csv)
    if not csv.exists():
        from music.data import download
        download(csv)
    raw=(spark.read.option('header',True).option('multiLine',True).option('escape','"').csv(str(csv)))
    required=REQUIRED
    missing=set(required)-set(raw.columns)
    if missing:raise ValueError(f'Missing columns: {missing}')
    raw=raw.drop('_c0','', 'Unnamed: 0').cache()
    raw_partitions=raw.rdd.getNumPartitions()
    raw_count=raw.count()
    missing_values=raw.select(*[F.sum(F.when(F.col(c).isNull() | (F.trim(F.col(c))==''),1).otherwise(0)).alias(c) for c in required]).first().asDict()
    raw.write.mode('overwrite').parquet(str(lake/'bronze/tracks'))
    clean,rejected=assess(raw)
    rejected.write.mode('overwrite').parquet(str(lake/'quarantine/tracks'))
    rejection_counts=[r.asDict() for r in rejected.select(F.explode('rejection_reasons').alias('reason'))
                      .groupBy('reason').count().orderBy('reason').collect()]
    clean=clean.cache();valid_count=clean.count()
    duplicates=clean.groupBy('track_id').agg(
        F.count('*').alias('source_rows'),F.min('popularity').alias('min_popularity'),
        F.max('popularity').alias('max_popularity'),
        F.countDistinct('popularity').alias('popularity_versions'),
        F.countDistinct(F.sha2(F.to_json(F.struct(*[F.col(c) for c in FEATURES])),256)).alias('feature_versions'))
    conflict_stats=duplicates.agg(
        F.sum(F.when(F.col('popularity_versions')>1,1).otherwise(0)).alias('popularity_conflict_tracks'),
        F.sum(F.when(F.col('feature_versions')>1,1).otherwise(0)).alias('feature_conflict_tracks'),
        F.avg('min_popularity').alias('catalog_mean_if_min_popularity'),
        F.avg('max_popularity').alias('catalog_mean_if_max_popularity')).first().asDict()
    duplicates.filter('popularity_versions > 1 OR feature_versions > 1').write.mode('overwrite').parquet(
        str(lake/'silver/metadata_conflicts'))
    tracks,genres=catalog(clean)
    genres=genres.cache()
    tracks=tracks.repartition(8,'track_id').cache()
    count=tracks.count()
    silver_partitions=tracks.rdd.getNumPartitions()
    if count<max(candidates):raise ValueError('Too few unique tracks for k')
    tracks.write.mode('overwrite').parquet(str(lake/'silver/tracks'))
    genres.write.mode('overwrite').parquet(str(lake/'silver/track_genres'))
    tracks.createOrReplaceTempView('tracks');genres.createOrReplaceTempView('track_genres')
    print('CLEANED',raw_count,valid_count,count,flush=True)
    queries={
        'genre_stats':'''SELECT g.track_genre, count(*) AS tracks, avg(t.popularity) AS avg_popularity,
            avg(t.energy) AS avg_energy, avg(t.valence) AS avg_valence, avg(t.danceability) AS avg_danceability
            FROM tracks t JOIN track_genres g ON t.track_id=g.track_id GROUP BY g.track_genre
            ORDER BY avg_popularity DESC, g.track_genre''',
        'top_tracks':'''SELECT track_id, track_name, artists, popularity, energy, tempo
            FROM tracks ORDER BY popularity DESC,track_id LIMIT 30''',
        'duration_distribution':'''SELECT CASE WHEN duration_ms<120000 THEN '1. Under 2 min'
            WHEN duration_ms<240000 THEN '2. 2 to 4 min' WHEN duration_ms<360000 THEN '3. 4 to 6 min'
            ELSE '4. Over 6 min' END AS duration_group,count(*) AS tracks FROM tracks
            GROUP BY duration_group ORDER BY duration_group''',
        'popularity_distribution':'''SELECT CAST(FLOOR(popularity/10)*10 AS INT) AS popularity_bin,
            count(*) AS tracks FROM tracks GROUP BY popularity_bin ORDER BY popularity_bin'''
    }
    results={}
    def export(name, frame, maximum=1000):
        frame.write.mode('overwrite').parquet(str(lake/'gold'/name))
        rows=frame.limit(maximum+1).collect()
        if len(rows)>maximum:raise ValueError(f'{name} exceeds dashboard collection limit')
        results[name]=[r.asDict(recursive=True) for r in rows]
        frame.toPandas().to_csv(root/f'{name}.csv',index=False)
    plans=[]
    for name,query in queries.items():
        frame=spark.sql(query)
        buffer=io.StringIO()
        with contextlib.redirect_stdout(buffer):frame.explain(mode='formatted')
        plans.append(f'=== {name} ===\n{buffer.getvalue()}')
        export(name,frame)
    artists=(tracks.withColumn('artist',F.explode(F.split('artists',';'))).withColumn('artist',F.trim('artist'))
             .filter(F.col('artist')!='').groupBy('artist').agg(F.countDistinct('track_id').alias('tracks'),
             F.avg('popularity').alias('avg_popularity')).orderBy(F.desc('tracks'),'artist').limit(30))
    export('artist_stats',artists)
    assembled=VectorAssembler(inputCols=FEATURES,outputCol='raw_features').transform(tracks).cache()
    matrix=Correlation.corr(assembled,'raw_features','pearson').first()[0].toArray()
    results['correlation']={'features':FEATURES,'matrix':matrix.tolist()}
    print('SELECTING_KMEANS',candidates,flush=True)
    predictions,model_selection=fit_clusters(assembled,candidates,lake/'models')
    k=model_selection['selected_k']
    silhouette=model_selection['full_catalog_silhouette']
    results['model_selection']=model_selection
    predictions.select('track_id','prediction').write.mode('overwrite').parquet(str(lake/'gold/track_clusters'))
    export('cluster_profiles',predictions.groupBy('prediction').agg(F.count('*').alias('tracks'),
            *[F.avg(c).alias(c) for c in FEATURES],F.avg('popularity').alias('popularity')).orderBy('prediction'))
    results['scatter']=[r.asDict() for r in predictions.select('track_id','energy','valence','prediction')
                        .orderBy(F.xxhash64('track_id')).limit(500).collect()]
    # Identical query and records, repeat measurements; replicated rows are explicitly load-test data.
    bench=tracks.crossJoin(spark.range(scale_factor).withColumnRenamed('id','replica'))
    bench.write.mode('overwrite').parquet(str(lake/'benchmark/input'))
    tracks.unpersist();clean.unpersist();raw.unpersist();assembled.unpersist();predictions.unpersist();spark.catalog.clearCache()
    measurements,benchmark_design=benchmark(spark,lake/'benchmark/input')
    results['benchmark_design']=benchmark_design
    run={'run_utc':datetime.now(timezone.utc).isoformat(),'spark_version':spark.version,
         'java_version':spark.sparkContext._jvm.java.lang.System.getProperty('java.version'),
         'spark_config':{key:spark.sparkContext.getConf().get(key,'default') for key in
             ['spark.cores.max','spark.executor.cores','spark.executor.memory','spark.driver.memory','spark.sql.shuffle.partitions']},
         'active_executors':max(0,spark.sparkContext._jsc.sc().getExecutorMemoryStatus().size()-1),
         'application_id':spark.sparkContext.applicationId,'master':spark.sparkContext.master,
         'python':platform.python_version(),'dataset_sha256':hashlib.sha256(csv.read_bytes()).hexdigest(),
         'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob('*.py'))},
         'raw_rows':raw_count,'valid_rows':valid_count,'unique_tracks':count,'invalid_rows':raw_count-valid_count,
         'raw_input_partitions':raw_partitions,'silver_partitions':silver_partitions,
         'duplicate_track_rows':valid_count-count,'genres':genres.select('track_genre').distinct().count(),
         'missing_values':missing_values,'rejection_counts':rejection_counts,'metadata_conflicts':conflict_stats,
         'k':k,'silhouette_squared_euclidean':silhouette,
         'scale_factor':scale_factor,'benchmark_rows':count*scale_factor,'benchmark':measurements,
         'elapsed_seconds':time.perf_counter()-started}
    results['run']=run
    assert sum(r['tracks'] for r in results['cluster_profiles'])==count
    assert all(abs(m['checksum']-measurements[0]['checksum'])<.001 for m in measurements)
    # Publish the summary only after all outputs and model have succeeded.
    temp=root/'summary.pending.json';temp.write_text(json.dumps(results,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    temp.replace(root/'summary.json')
    (root/'queries.sql').write_text('\n\n'.join('-- '+n+'\n'+q+';' for n,q in queries.items()),encoding='utf-8')
    (root/'query-plans.txt').write_text('\n\n'.join(plans),encoding='utf-8')
    (root/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
    (root/'data-schema.json').write_text(raw.schema.json(),encoding='utf-8')
    (root/'model-selection.json').write_text(json.dumps(model_selection,indent=2),encoding='utf-8')
    from bigdata.report import write_report
    write_report(root)
    print('SUCCESS',json.dumps(run),flush=True)
    spark.stop()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--csv',default='data/raw/dataset.csv')
    p.add_argument('--output',default='reports/bigdata')
    p.add_argument('--k-candidates',default='3,5,7,9',help='Comma-separated k values selected on validation only')
    p.add_argument('--scale-factor',type=int,default=10)
    a=p.parse_args()
    try:candidates=tuple(sorted(set(int(k) for k in a.k_candidates.split(','))))
    except ValueError:p.error('k-candidates must be comma-separated integers')
    if min(candidates)<2 or a.scale_factor<1:p.error('k >= 2 and scale-factor >= 1 required')
    analyze(a.csv,a.output,candidates,a.scale_factor)
