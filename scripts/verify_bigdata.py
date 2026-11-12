"""Verify the completed analytical outputs without requiring Spark on the host."""
import json
import math
from pathlib import Path

root=Path('reports/bigdata')
d=json.loads((root/'summary.json').read_text(encoding='utf-8'))
r=d['run']
assert r['raw_rows']>=r['valid_rows']>=r['unique_tracks']>0
assert r['raw_rows']-r['valid_rows']==r['invalid_rows']
assert r['valid_rows']-r['unique_tracks']==r['duplicate_track_rows']
assert r['master']=='spark://master:7077','Expected the Docker Standalone cluster'
assert r['active_executors']==2,'Expected work on both worker executors'
assert r['benchmark_rows']==r['unique_tracks']*r['scale_factor']
conflicts=r['metadata_conflicts']
assert conflicts['catalog_mean_if_min_popularity']<=conflicts['catalog_mean_if_max_popularity']
assert 0<=conflicts['popularity_conflict_tracks']<=r['unique_tracks']
assert abs(r['benchmark'][0]['checksum']/r['benchmark_rows']-conflicts['catalog_mean_if_max_popularity'])<1e-7
assert len(r['benchmark'])==9
selection=d['model_selection']
assert sum(selection['split_rows'].values())==r['unique_tracks']
assert all(n>0 for n in selection['split_rows'].values())
assert selection['reload_prediction_check_rows']==100
eligible=[t for t in selection['trials'] if t['validation_silhouette'] is not None]
winner=sorted(eligible,key=lambda t:(-t['validation_silhouette'],t['k']))[0]
assert winner['k']==r['k']==selection['selected_k']
assert -1<=selection['test_silhouette']<=1
assert len(d['benchmark_design']['warmups'])==3
assert d['benchmark_design']['aqe_enabled'] is False
assert all(abs(w['checksum']-r['benchmark'][0]['checksum'])<.001 for w in d['benchmark_design']['warmups'])
for p in [2,4,8]:
    assert len([m for m in r['benchmark'] if m['partitions']==p])==3
for table in ['duration_distribution','popularity_distribution','cluster_profiles']:
    assert sum(x['tracks'] for x in d[table])==r['unique_tracks'],table
assert len(d['genre_stats'])==r['genres']
assert len(d['cluster_profiles'])==r['k']
assert -1<=r['silhouette_squared_euclidean']<=1
m=d['correlation']['matrix']
for i,row in enumerate(m):
    for j,v in enumerate(row):
        assert math.isfinite(v) and abs(v)<=1.000001
        assert abs(v-m[j][i])<1e-9
assert all(abs(x['checksum']-r['benchmark'][0]['checksum'])<.001 for x in r['benchmark'])
assert (root/'BAO_CAO_BIGDATA.md').is_file()
assert Path('data/bigdata-lake/models/kmeans/metadata').is_dir()
assert (root/'query-plans.txt').stat().st_size>100
print('PASS: row accounting, partitions, cluster coverage, correlation, benchmark checksums, model and report.')
