"""Publication figures from measured Spark output; no recomputation of source analytics."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

root=Path('reports/bigdata')
d=json.loads((root/'summary.json').read_text(encoding='utf-8'))
out=root/'figures';out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'figure.dpi':160,'savefig.bbox':'tight'})

rows=d['genre_stats'][:12][::-1]
fig,ax=plt.subplots(figsize=(8,4.7))
ax.barh([r['track_genre'] for r in rows],[r['avg_popularity'] for r in rows],color='#236b8e')
ax.set(xlabel='Popularity trung bình trong mẫu (0–100)',title='12 thể loại có popularity trung bình cao nhất')
ax.set_xlim(0,100);ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
fig.savefig(out/'paper-genres.png');plt.close(fig)

fig,ax=plt.subplots(figsize=(8,6.5))
m=np.array(d['correlation']['matrix']);names=d['correlation']['features']
im=ax.imshow(m,cmap='RdBu_r',vmin=-1,vmax=1)
ax.set_xticks(range(len(names)),names,rotation=45,ha='right')
ax.set_yticks(range(len(names)),names)
for i in range(len(names)):
    for j in range(len(names)):
        ax.text(j,i,f'{m[i,j]:.2f}',ha='center',va='center',fontsize=8,
                color='white' if abs(m[i,j])>.6 else 'black')
ax.set_title('Tương quan Pearson trên danh mục đã làm sạch')
fig.colorbar(im,ax=ax,label='Pearson r',shrink=.7)
fig.savefig(out/'paper-correlation.png');plt.close(fig)

fig,ax=plt.subplots(figsize=(8,4.6))
for k in range(d['run']['k']):
    points=[p for p in d['scatter'] if p['prediction']==k]
    ax.scatter([p['energy'] for p in points],[p['valence'] for p in points],s=15,alpha=.65,label=f'Cụm {k}')
ax.set(xlabel='Energy',ylabel='Valence',xlim=(0,1),ylim=(0,1),
       title='Minh họa 500 bài theo hash, mô hình học trên 10 chiều')
ax.legend(loc='center left',bbox_to_anchor=(1, .5),frameon=False);ax.grid(alpha=.15)
fig.savefig(out/'paper-clusters.png');plt.close(fig)

fig,ax=plt.subplots(figsize=(8,4.4))
rows=d['benchmark_design']['summary'];med=np.array([r['median_seconds'] for r in rows])
err=np.array([med-np.array([r['min_seconds'] for r in rows]),np.array([r['max_seconds'] for r in rows])-med])
ax.bar([str(r['partitions']) for r in rows],med,color='#236b8e',yerr=err,capsize=7)
ax.set(xlabel='Số hash partition theo artists',ylabel='Thời gian (giây)',
       title=f'Benchmark {d["run"]["benchmark_rows"]:,} dòng: trung vị và min–max của 3 lượt')
ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
fig.savefig(out/'paper-benchmark.png');plt.close(fig)
print('Saved four publication figures from',d['run']['application_id'])
