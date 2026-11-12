"""Rebuild committed notebooks without storing execution output or credentials."""
import json
from pathlib import Path


def write(name, cells):
    result = []
    for i, (kind, source) in enumerate(cells):
        cell = {"cell_type": kind, "id": f"cell-{i:03}", "metadata": {}, "source": source.splitlines(True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        result.append(cell)
    notebook = {"nbformat": 4, "nbformat_minor": 5, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}, "colab": {"provenance": []}}, "cells": result}
    Path("notebooks").mkdir(exist_ok=True)
    Path("notebooks", name).write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")


write("01_colab_gpu_training.ipynb", [
    ("markdown", """# Music Insight — GPU training trên Google Colab
Chọn **Runtime → Change runtime type → GPU**, sau đó chạy các cell theo thứ tự.
Notebook tải trực tiếp dataset Kaggle, xử lý trùng track,
train denoising autoencoder và lưu bundle vào Google Drive. URL và SHA256 được ghi lại cho mỗi lần tải.
Đây là học biểu diễn content-based: reconstruction MSE không phải Recall/NDCG trên người dùng.
Điền URL Git repository của bạn sau khi push. Có thể giữ trống để upload ZIP repository.
"""),
    ("code", """from google.colab import drive
drive.mount('/content/drive')
from pathlib import Path
import subprocess, sys, os, shutil, datetime
REPO_URL = ''  # Ví dụ: https://github.com/your-name/music-insight.git
REPO_REF = 'main'  # Có thể thay bằng commit SHA để tái hiện chính xác
ROOT = Path('/content/music-insight')
if not ROOT.exists():
    if REPO_URL:
        subprocess.run(['git', 'clone', REPO_URL, str(ROOT)], check=True)
        subprocess.run(['git', '-C', str(ROOT), 'checkout', REPO_REF], check=True)
    else:
        from google.colab import files
        import zipfile, io
        uploaded = files.upload()  # Upload ZIP source repository, không chứa credentials
        archive = next(iter(uploaded.values()))
        unpack = Path('/content/music-source')
        unpack.mkdir(exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            base = unpack.resolve()
            for entry in z.infolist():
                if not (base / entry.filename).resolve().is_relative_to(base):
                    raise ValueError('Unsafe ZIP path')
            z.extractall(unpack)
        project = next(unpack.rglob('pyproject.toml')).parent
        shutil.copytree(project, ROOT)
os.chdir(ROOT)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-e', '.[train]'], check=True)
print('Repository:', ROOT)
"""),
    ("code", """import torch
assert torch.cuda.is_available(), 'Hãy chọn GPU runtime rồi chạy lại.'
print('PyTorch:', torch.__version__)
print('GPU:', torch.cuda.get_device_name(0))
RUN_ID = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
DRIVE_ROOT = Path('/content/drive/MyDrive/MusicInsight')
DRIVE_RUN = DRIVE_ROOT / 'runs' / RUN_ID
DRIVE_RUN.mkdir(parents=True, exist_ok=False)
"""),
    ("code", """from music.data import download, prepare
# Nếu Kaggle không khả dụng, đổi DATA_SOURCE thành 'huggingface' để dùng snapshot cùng tác giả.
DATA_SOURCE = 'kaggle'
DATASET = download(ROOT / 'data/raw/dataset.csv', source=DATA_SOURCE)
tracks = prepare(DATASET)
print('Số bài duy nhất:', len(tracks))
display(tracks[['track_name','artists','genres','popularity']].head())
shutil.copy2(DATASET.with_suffix('.source.json'), DRIVE_RUN / 'dataset.source.json')
"""),
    ("markdown", """## Baseline và GPU model
Baseline dùng vector đặc trưng chuẩn hóa. Autoencoder chia train/validation/test theo track duy nhất;
scaler chỉ fit trên train; early stopping dùng validation, test chỉ đánh giá sau chọn model.
Popularity không được đưa vào encoder. Không tạo user giả để báo cáo chất lượng cá nhân hóa.
"""),
    ("code", """from music.baseline import build
from music.train import train
LOCAL_RUN = ROOT / 'artifacts' / RUN_ID
build(DATASET, LOCAL_RUN / 'baseline')
metrics = train(DATASET, LOCAL_RUN / 'autoencoder', epochs=30,
                batch_size=1024, seed=42, require_gpu=True)
print('Validation MSE:', metrics['validation_mse'])
print('Test MSE:', metrics['test_mse'])
"""),
    ("code", """# Lưu ngay sau train, trước các cell trực quan hóa.
import json
shutil.copytree(LOCAL_RUN, DRIVE_RUN / 'artifacts')
environment = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True)
(DRIVE_RUN / 'requirements-resolved.txt').write_text(environment)
commit = subprocess.run(['git','rev-parse','HEAD'], capture_output=True, text=True)
(DRIVE_RUN / 'run.json').write_text(json.dumps({'run_id':RUN_ID, 'git_commit':commit.stdout.strip(),
    'torch':torch.__version__, 'gpu':torch.cuda.get_device_name(0)}, indent=2))
from music.recommender import Recommender
loaded = Recommender(DRIVE_RUN / 'artifacts/autoencoder')
print('Bundle đã kiểm tra checksum:', len(loaded.tracks), 'bài')
shutil.make_archive(str(DRIVE_RUN / 'autoencoder-bundle'), 'zip', LOCAL_RUN / 'autoencoder')
print('Đã lưu vào:', DRIVE_RUN)
"""),
    ("code", """import matplotlib.pyplot as plt
history = metrics['history']
plt.plot([h['epoch'] for h in history], [h['train_mse'] for h in history], label='Train denoising MSE')
plt.plot([h['epoch'] for h in history], [h['validation_mse'] for h in history], label='Validation clean MSE')
plt.xlabel('Epoch'); plt.ylabel('MSE'); plt.legend(); plt.grid(alpha=.2)
plt.savefig(DRIVE_RUN / 'training-curve.png', dpi=150, bbox_inches='tight')
plt.show()
seed_track = loaded.tracks.iloc[0].track_id
print('Seed:', loaded.tracks.iloc[0].track_name)
display(__import__('pandas').DataFrame(loaded.recommend([seed_track], limit=10)))
"""),
    ("markdown", """## Đưa model về ứng dụng
Tải `autoencoder-bundle.zip` từ thư mục run trên Drive, giải nén thành `artifacts/autoencoder/`.
Đặt `MODEL_DIR=artifacts/autoencoder`, rồi restart API. API dùng embeddings đã xuất, không cần GPU.
`model.pt` chứa state_dict để tiếp tục nghiên cứu; tải bằng `torch.load(path, weights_only=True)` với file tin cậy.
Muốn đánh giá Recall@K/NDCG@K: thu thập tương tác thật, chia theo thời gian, xây profile chỉ từ train
và đo trên positive tương lai. Không diễn giải reconstruction MSE thành độ chính xác gợi ý.
""")
])

write("02_colab_spark_analysis.ipynb", [
    ("markdown", """# Phân tích Spotify bằng Apache Spark
Chạy cell thiết lập repository của notebook 01 trong runtime này trước (không cần GPU).
Notebook này chạy Spark local trên Colab. Đây không phải benchmark cluster nhiều máy.
"""),
    ("code", """import subprocess, sys, os
from pathlib import Path
ROOT = Path('/content/music-insight')
assert (ROOT/'pyproject.toml').exists(), 'Chạy cell thiết lập repository trong notebook 01 trước'
os.chdir(ROOT)
subprocess.run(['apt-get','update','-qq'], check=True)
subprocess.run(['apt-get','install','-y','openjdk-17-jdk-headless'], check=True)
os.environ['JAVA_HOME']='/usr/lib/jvm/java-17-openjdk-amd64'
subprocess.run([sys.executable,'-m','pip','install','-q','-e','.[spark]'], check=True)
from music.data import download
download('data/raw/dataset.csv')
"""),
    ("code", """from pipelines.batch import run
run('data/raw/dataset.csv', 'data/lake')
"""),
    ("code", """from pyspark.sql import SparkSession, functions as F
spark = SparkSession.builder.master('local[*]').appName('spotify-eda').getOrCreate()
tracks = spark.read.parquet('data/lake/silver/tracks')
genres = spark.read.parquet('data/lake/gold/genre_stats')
tracks.printSchema()
tracks.select('energy','valence','tempo','popularity').summary().show()
print('Energy/loudness correlation:', tracks.stat.corr('energy','loudness'))
display(genres.orderBy(F.desc('avg_popularity')).limit(20).toPandas())
"""),
    ("code", """import matplotlib.pyplot as plt
chart = genres.orderBy(F.desc('avg_popularity')).limit(20).toPandas().sort_values('avg_popularity')
chart.plot.barh(x='track_genre', y='avg_popularity', figsize=(9,7), legend=False)
plt.xlabel('Popularity trung bình tại snapshot'); plt.tight_layout()
Path('reports/figures').mkdir(parents=True, exist_ok=True)
plt.savefig('reports/figures/genre-popularity.png', dpi=150)
plt.show()
"""),
    ("code", """# Ghi nhận benchmark thực đo: cùng input và cùng phép tính.
import time, json
results=[]
for partitions in [2,4,8]:
    start=time.perf_counter()
    count=tracks.repartition(partitions).groupBy('artists').agg(F.avg('energy')).count()
    results.append({'partitions':partitions,'seconds':time.perf_counter()-start,'artist_groups':count})
print(results)
Path('reports/benchmark-local.json').write_text(json.dumps(results,indent=2))
spark.stop()
"""),
    ("code", """from google.colab import drive
drive.mount('/content/drive')
import shutil, datetime
target=Path('/content/drive/MyDrive/MusicInsight/spark')/datetime.datetime.now().strftime('%Y%m%dT%H%M%S')
target.mkdir(parents=True)
shutil.copytree('data/lake/gold',target/'gold')
shutil.copytree('reports/figures',target/'figures')
shutil.copy2('reports/benchmark-local.json',target/'benchmark-local.json')
print(target)
""")
])
