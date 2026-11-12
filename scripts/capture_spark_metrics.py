"""Export benchmark execution evidence from the completed application's History REST API."""
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import json
import urllib.request

root=Path('reports/bigdata')
summary=json.loads((root/'summary.json').read_text(encoding='utf-8'))
run=summary['run'];base='http://localhost:18080/api/v1/applications/'+run['application_id']

def get(path):
    with urllib.request.urlopen(base+path,timeout=60) as response:return json.load(response)

jobs=get('/jobs');stages=get('/stages?status=complete&length=10000')
by_id={s['stageId']:s for s in stages}
groups=defaultdict(list)
for job in jobs:
    if job.get('jobGroup','').startswith('benchmark-measured-'):groups[job['jobGroup']].append(job)

def seconds(start,end):
    return (datetime.fromisoformat(end.replace('GMT','+00:00'))-
            datetime.fromisoformat(start.replace('GMT','+00:00'))).total_seconds()

rows=[]
for measurement in run['benchmark']:
    key=f'benchmark-measured-p{measurement["partitions"]}-r{measurement["repeat"]}'
    selected=groups[key]
    stage_ids=sorted({sid for j in selected for sid in j['stageIds']})
    executed=[by_id[sid] for sid in stage_ids if sid in by_id]
    assert selected and executed and all(j['status']=='SUCCEEDED' for j in selected)
    rows.append(dict(measurement,job_group=key,job_ids=sorted(j['jobId'] for j in selected),
                     stage_ids=stage_ids,job_wall_seconds=sum(seconds(j['submissionTime'],j['completionTime']) for j in selected),
                     task_count=sum(s['numCompleteTasks'] for s in executed),
                     executor_run_seconds=sum(s['executorRunTime'] for s in executed)/1000,
                     executor_cpu_seconds=sum(s['executorCpuTime'] for s in executed)/1e9,
                     task_gc_seconds=sum(s['jvmGcTime'] for s in executed)/1000,
                     disk_spill_bytes=sum(s['diskBytesSpilled'] for s in executed),
                     shuffle_write_bytes=sum(s['shuffleWriteBytes'] for s in executed)))
assert len(rows)==9
(root/'execution-metrics.json').write_text(json.dumps({'application_id':run['application_id'],'benchmark':rows},indent=2),encoding='utf-8')
slow=max(rows,key=lambda x:x['seconds'])
text=(
    '## Dấu vết thực thi và giới hạn suy luận hiệu năng\n\n'
    f'Lượt chậm nhất là partition={slow["partitions"]}, lần {slow["repeat"]}: {slow["seconds"]:.3f} giây. '
    f'Spark History ghi nhận {slow["task_count"]} task hoàn tất, tổng thời gian executor theo task '
    f'{slow["executor_run_seconds"]:.3f} giây và tổng CPU executor {slow["executor_cpu_seconds"]:.3f} giây. '
    f'Thời gian GC cộng theo task là {slow["task_gc_seconds"]:.3f} giây; disk spill '
    f'{slow["disk_spill_bytes"]:,} byte. Các tổng theo task có thể chồng lấn khi chạy song song, '
    'không phải thời gian đồng hồ của toàn job.\n\n'
    'Các chỉ số này cho phép đối chiếu thời gian đo với thực thi Spark nhưng chưa tách riêng chi phí '
    'I/O, lập lịch của hệ điều hành, chờ tài nguyên và lập kế hoạch ở driver. Không quy toàn bộ biến thiên '
    'cho số partition hoặc tuyên bố nguyên nhân cụ thể khi chưa có profiling bổ sung. '
    'Ba lượt đo chỉ là thực nghiệm ban đầu trên một máy; biểu đồ min–max không phải khoảng tin cậy. '
    'Dữ liệu được nhân bản có thể nén tốt và không mô phỏng đầy đủ độ đa dạng hoặc độ lệch của dữ liệu thực.\n\n'
    'execution-metrics.json lưu job group và stage ID để mở lại trong History Server; '
    f'application ID: {run["application_id"]}.\n')
(root/'PHAN_TICH_THUC_THI.md').write_text(text,encoding='utf-8')
print('Captured 9 measured job groups; slowest:',slow['job_group'],slow['seconds'])
