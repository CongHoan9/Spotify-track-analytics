"""Spark regression tests for data loss, malformed inputs and deterministic metadata."""
import unittest
import os
from pathlib import Path

from pyspark.sql import SparkSession
from bigdata.quality import FEATURES, REQUIRED, assess, catalog


@unittest.skipUnless(Path('/.dockerenv').exists() or os.getenv('RUN_SPARK_TESTS')=='1',
                     'Spark contract tests run in the Big Data Docker image')
class QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spark = (SparkSession.builder.master('local[2]').appName('BigData contract tests')
                     .config('spark.driver.host', '127.0.0.1')
                     .config('spark.driver.bindAddress', '0.0.0.0')
                     .config('spark.sql.shuffle.partitions', '2')
                     .config('spark.sql.ansi.enabled', 'false')
                     .config('spark.eventLog.enabled', 'false').getOrCreate())
        cls.spark.sparkContext.setLogLevel('ERROR')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()

    def frame(self, rows):
        base = {c: '0.5' for c in FEATURES}
        base.update(track_id='a', track_name='Song A', artists='Artist A',
                    track_genre='pop', popularity='40', duration_ms='200000', tempo='120', loudness='-6')
        records = [dict(base, **row) for row in rows]
        return self.spark.createDataFrame(records, ','.join(f'{c} string' for c in REQUIRED))

    def test_genre_membership_survives_dedup(self):
        valid, rejected = assess(self.frame([
            {}, {'track_genre':'rock', 'popularity':'50'},
            {'track_genre':'rock', 'popularity':'50'},
            {'track_id':'b', 'track_genre':'jazz'}]))
        tracks, genres = catalog(valid)
        self.assertEqual(rejected.count(), 0)
        self.assertEqual(tracks.count(), 2)
        self.assertEqual({(r.track_id,r.track_genre) for r in genres.collect()},
                         {('a','pop'),('a','rock'),('b','jazz')})
        self.assertEqual(tracks.filter("track_id='a'").first().popularity, 50)

    def test_quarantine_has_reasons_and_covers_every_invalid_row(self):
        valid, rejected = assess(self.frame([
            {}, {'track_name':'  '}, {'energy':'1.5'}, {'popularity':'bad'},
            {'duration_ms':'0'}, {'tempo':'NaN'}, {'tempo':'Infinity'}]))
        self.assertEqual(valid.count(), 1)
        reasons = [set(r.rejection_reasons) for r in rejected.collect()]
        self.assertEqual(len(reasons), 6)
        self.assertTrue(all(reasons))
        self.assertEqual(sum('invalid_numeric' in r for r in reasons), 3)
        self.assertTrue(any('missing_identity' in r for r in reasons))

    def test_tie_breaker_does_not_depend_on_partition_count(self):
        valid, _ = assess(self.frame([{}, {'track_name':'Alternate metadata'}]))
        left, _ = catalog(valid.repartition(1))
        right, _ = catalog(valid.repartition(3))
        self.assertEqual(left.first().track_name, right.first().track_name)

    def test_missing_columns_fail_before_analysis(self):
        with self.assertRaisesRegex(ValueError, 'Missing columns'):
            assess(self.spark.createDataFrame([('a',)], ['track_id']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
