"""Optional official PyPI wheel cache for slow Docker networking (Linux x86_64)."""
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

PACKAGES = {'numpy':'1.26.4','pandas':'2.2.3','requests':'2.32.3',
            'python-dateutil':'2.9.0.post0','pytz':'2025.2','tzdata':'2025.2',
            'charset-normalizer':'3.4.2','idna':'3.10','urllib3':'2.4.0',
            'certifi':'2025.4.26','six':'1.17.0'}

def main():
    dest=Path('docker/vendor/wheels');dest.mkdir(parents=True,exist_ok=True)
    manifest={}
    for name,version in PACKAGES.items():
        response=requests.get(f'https://pypi.org/pypi/{name}/{version}/json',timeout=30)
        response.raise_for_status()
        candidates=[f for f in response.json()['urls'] if f['filename'].endswith('.whl') and
                    ('py3-none-any' in f['filename'] or 'py2.py3-none-any' in f['filename'] or
                     ('cp311-cp311-manylinux' in f['filename'] and 'x86_64' in f['filename']))]
        f=candidates[0];target=dest/f['filename']
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=f['digests']['sha256']:
            print('Downloading',f['filename'],flush=True)
            chunk_size=65536
            def fetch(start):
                end=min(start+chunk_size,f['size'])-1
                for attempt in range(4):
                    try:
                        r=requests.get(f['url']+f'?chunk={start}',
                            headers={'Range':f'bytes={start}-{end}'},timeout=(10,15))
                        r.raise_for_status()
                        if r.status_code!=206 or len(r.content)!=end-start+1:
                            raise ValueError('Invalid ranged download')
                        return r.content
                    except Exception:
                        if attempt==3:raise
            with ThreadPoolExecutor(max_workers=12) as pool, target.open('wb') as out:
                for chunk in pool.map(fetch,range(0,f['size'],chunk_size)):out.write(chunk)
            assert hashlib.sha256(target.read_bytes()).hexdigest()==f['digests']['sha256']
        manifest[f['filename']]=f['digests']['sha256']
        print('Verified',target.name,target.stat().st_size,flush=True)
    (dest/'SHA256.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
