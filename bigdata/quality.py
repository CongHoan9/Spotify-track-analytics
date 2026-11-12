"""Data contract, quarantine and track-grain deduplication using Spark expressions."""
from functools import reduce
from operator import or_

from pyspark.sql import functions as F, Window

FEATURES = ['danceability', 'energy', 'loudness', 'speechiness', 'acousticness',
            'instrumentalness', 'liveness', 'valence', 'tempo', 'duration_ms']
RATIOS = ['danceability', 'energy', 'speechiness', 'acousticness',
          'instrumentalness', 'liveness', 'valence']
REQUIRED = FEATURES + ['track_id', 'track_name', 'artists', 'track_genre', 'popularity']


def assess(raw):
    """Return valid typed rows and quarantined rows; one row may violate several rules."""
    missing = set(REQUIRED) - set(raw.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')
    typed = raw
    for column in FEATURES + ['popularity']:
        typed = typed.withColumn(column, F.col(column).cast('double'))
    rules = {
        'missing_identity': reduce(or_, [F.col(c).isNull() | (F.trim(c) == '')
                                        for c in ['track_id', 'track_name', 'artists']]),
        'invalid_numeric': reduce(or_, [F.col(c).isNull() | F.isnan(c) |
                                       (F.abs(F.col(c)) == float('inf'))
                                       for c in FEATURES + ['popularity']]),
        'invalid_duration': F.col('duration_ms') <= 0,
        'invalid_popularity': ~F.col('popularity').between(0, 100),
        'invalid_ratio': reduce(or_, [~F.col(c).between(0, 1) for c in RATIOS]),
    }
    reasons = F.filter(F.array(*[F.when(condition, F.lit(name))
                                for name, condition in rules.items()]), lambda x: x.isNotNull())
    audited = typed.withColumn('rejection_reasons', reasons)
    valid = audited.filter(F.size('rejection_reasons') == 0).drop('rejection_reasons')
    rejected = audited.filter(F.size('rejection_reasons') > 0)
    return valid, rejected


def catalog(valid):
    """Preserve multiple genres while retaining exactly one metadata row per track."""
    genres = (valid.select('track_id', F.trim('track_genre').alias('track_genre'))
              .filter(F.col('track_genre').isNotNull() & (F.col('track_genre') != '')).distinct())
    # Complete tie breaker keeps the choice stable when popularity/genre match but metadata differ.
    tie = F.sha2(F.to_json(F.struct(*[F.col(c) for c in sorted(valid.columns)])), 256)
    order = Window.partitionBy('track_id').orderBy(F.desc('popularity'), 'track_genre', tie)
    tracks = (valid.withColumn('_rank', F.row_number().over(order)).filter('_rank = 1')
              .drop('_rank', 'track_genre'))
    return tracks, genres
