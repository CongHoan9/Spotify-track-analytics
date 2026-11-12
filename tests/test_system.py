import json
import uuid

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import create_app
from music.baseline import build
from music.data import FEATURES, prepare
from music.recommender import Recommender


@pytest.fixture
def bundle(tmp_path):
    rows=[]
    for i in range(30):
        row = dict.fromkeys(FEATURES, .1 + (i % 8) / 10)
        row.update(track_id=f"track{i}", track_name=f"Song {i}", artists=f"Artist {i}",
                   track_genre="rock" if i % 2 else "pop", popularity=i+30, duration_ms=180000+i*100,
                   tempo=80+i, loudness=-20+i/2)
        rows.append(row)
    rows.append(dict(rows[0], track_genre="jazz"))
    csv=tmp_path/'tracks.csv'
    pd.DataFrame(rows).to_csv(csv,index=False)
    root=tmp_path/'model'
    build(csv,root)
    return root,csv


def test_track_dedup_retains_genres(bundle):
    root,csv=bundle
    tracks=prepare(csv)
    assert len(tracks)==30
    assert set(tracks.loc[tracks.track_id=='track0','genres'].iloc[0].split('|'))=={'pop','jazz'}


def test_bundle_integrity_and_filtering(bundle):
    root,_=bundle
    model=Recommender(root)
    result=model.recommend(['track0'],['track1'],limit=10)
    assert len(result)==10
    assert not {'track0','track1'} & {r['track_id'] for r in result}
    assert all(np.isfinite(r['score']) for r in result)
    (root/'tracks.csv').write_text('tampered')
    with pytest.raises(ValueError,match='checksum'):
        Recommender(root)


def test_auth_feedback_idempotency_and_playlist_isolation(bundle,tmp_path):
    root,_=bundle
    app=create_app(f'sqlite:///{tmp_path / "app.db"}',str(root),'x'*40)
    with TestClient(app) as client:
        assert client.get('/api/recommendations').status_code==401
        assert client.get('/').status_code==200
        def signup(name):
            r=client.post('/api/auth/register',json={'username':name,'password':'password123'})
            assert r.status_code==201
            return {'Authorization':'Bearer '+r.json()['token']}
        a,b=signup('alice'),signup('bob')
        assert client.post('/api/auth/login',json={'username':'alice','password':'wrongpass'}).status_code==401
        assert client.put('/api/me/preferences',headers=a,json={'genres':['unknown']}).status_code==422
        assert client.put('/api/me/preferences',headers=a,json={'genres':['rock']}).status_code==200
        event={'event_id':str(uuid.uuid4()),'track_id':'track0','event_type':'like'}
        assert client.post('/api/events',headers=a,json=event).status_code==201
        assert client.post('/api/events',headers=a,json=event).json()['duplicate']
        assert client.post('/api/events',headers=b,json=event).status_code==409
        counts=client.get('/api/analytics/me',headers=a).json()['counts']
        assert counts=={'like':1}
        assert 'track0' not in {t['track_id'] for t in client.get('/api/recommendations',headers=a).json()}
        playlist=client.post('/api/playlists',headers=a,json={'name':'Favorites'}).json()['id']
        endpoint=f'/api/playlists/{playlist}/tracks/track0'
        assert client.put(endpoint,headers=b).status_code==404
        assert client.put(endpoint,headers=a).status_code==200
        assert client.put(endpoint,headers=a).status_code==200
        assert len(client.get('/api/playlists',headers=a).json()[0]['tracks'])==1
        assert client.get('/api/playlists',headers=b).json()==[]


def test_gpu_model_cpu_smoke(bundle,tmp_path):
    pytest.importorskip('torch')
    from music.train import train
    _,csv=bundle
    metrics=train(csv,tmp_path/'trained',epochs=2,batch_size=8)
    assert np.isfinite(metrics['test_mse'])
    model=Recommender(tmp_path/'trained')
    assert len(model.recommend(['track0'],limit=5))==5


def test_temporal_evaluation_ignores_synthetic_and_seen_items(bundle,tmp_path):
    from music.evaluate import evaluate
    root,_=bundle
    records = [
        {'event_id':'a','user_id':'u','track_id':'track0','event_type':'like','source':'real','event_time':'2026-01-01T00:00:00Z'},
        {'event_id':'b','user_id':'u','track_id':'track1','event_type':'like','source':'real','event_time':'2026-01-03T00:00:00Z'},
        {'event_id':'c','user_id':'sim','track_id':'track2','event_type':'like','source':'synthetic','event_time':'2026-01-03T00:00:00Z'}]
    path=tmp_path/'events.jsonl'
    path.write_text('\n'.join(json.dumps(r) for r in records),encoding='utf-8')
    result=evaluate(root,path,'2026-01-02',k=30)
    assert result['evaluated_users']==1
    assert result['recall_at_k']==1
    assert 0 < result['ndcg_at_k'] <= 1
