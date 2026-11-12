"""Optional: reuse an installed official PySpark 4.0.1 distribution when building offline."""
from pathlib import Path
import hashlib
import json
import shutil
import pyspark

assert pyspark.__version__=='4.0.1','The Big Data image requires exactly PySpark 4.0.1'
source=Path(pyspark.__file__).parent
target=Path('docker/vendor/pyspark')
shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
manifest={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (target/'jars').glob('*.jar')}
Path('docker/vendor/cache-manifest.json').write_text(json.dumps({'version':pyspark.__version__,'jars':manifest},indent=2))
print('Cached',pyspark.__version__,len(manifest),'JARs. This cache is excluded from Git.')
