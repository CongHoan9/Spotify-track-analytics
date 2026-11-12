"""Create an evidence-based defense report from a successful Spark run."""
import json
from pathlib import Path


def write_report(directory):
    root=Path(directory)
    d=json.loads((root/'summary.json').read_text(encoding='utf-8'))
    r=d['run'];genres=d['genre_stats'];features=d['correlation']['features'];matrix=d['correlation']['matrix']
    selection=d['model_selection'];design=d['benchmark_design']
    pairs=sorted([(abs(matrix[i][j]),features[i],features[j],matrix[i][j])
                  for i in range(len(features)) for j in range(i)],reverse=True)[:5]
    sections=[
        '# Phân tích dữ liệu âm nhạc Spotify bằng Apache Spark',
        '## 1. Mục tiêu và câu hỏi nghiên cứu',
        'Nghiên cứu cấu trúc danh mục âm nhạc: dữ liệu thiếu/trùng như thế nào; đặc trưng khác nhau ra sao giữa '
        'các thể loại; các thuộc tính có tương quan gì; có thể nhóm bài bằng đặc trưng âm nhạc như thế nào. '
        'Phần kỹ thuật kiểm chứng xử lý Spark trong Docker và ảnh hưởng của partition lên một phép tổng hợp.',
        '## 2. Dữ liệu và môi trường',
        f'Nguồn: Spotify Tracks Dataset của Maharshi Pandya trên Kaggle. Run UTC: {r["run_utc"]}. '
        f'Spark {r["spark_version"]}; Python {r["python"]}; master `{r["master"]}`. '
        f'Application ID: `{r["application_id"]}`. SHA256: `{r["dataset_sha256"]}`.',
        'Docker Compose gồm master, hai worker và driver riêng. Storage là thư mục host mount chung. '
        'Các container chia sẻ một máy; đây không phải bằng chứng hiệu năng nhiều host hoặc HDFS.',
        f'CSV nguồn có {r["raw_input_partitions"]} partition khi đọc với multiLine; '
        f'danh mục Silver được phân vùng lại thành {r["silver_partitions"]} phần. '
        'Đọc một file CSV có trường nhiều dòng là giới hạn ở bước nhập liệu; các bước Spark SQL/MLlib '
        'phía sau mới khai thác các partition trên hai executor. Khi tăng nguồn dữ liệu cần cân nhắc '
        'nhiều file đầu vào hoặc chuyển sớm sang Parquet, thay vì tuyên bố mọi bước đều song song.',
        '## 3. Chất lượng dữ liệu và ETL',
        f'Đọc {r["raw_rows"]:,} dòng; giữ {r["valid_rows"]:,} dòng hợp lệ; loại {r["invalid_rows"]:,} dòng. '
        f'Gộp {r["duplicate_track_rows"]:,} dòng lặp mã bài; còn {r["unique_tracks"]:,} bài và {r["genres"]} genre.',
        'Các bước: schema validation → ép kiểu → kiểm tra null và miền giá trị → group genre theo track '
        '→ chọn metadata bằng Window row_number → ghi Silver Parquet. Bronze giữ dữ liệu nguồn; Gold lưu bảng tổng hợp. '
        'Không gộp bài theo tên vì có thể là bản thu khác. Không cộng tổng các nhóm genre thành số bài duy nhất.',
        '### 3.1. Truy nguyên bản ghi bị loại',
        'Các bản ghi không hợp lệ được lưu ở data/bigdata-lake/quarantine/tracks, kèm rejection_reasons. '
        'Một dòng có thể vi phạm nhiều quy tắc; vì vậy tổng lượt vi phạm không nhất thiết bằng số dòng bị loại.',
        '| Quy tắc | Số dòng vi phạm |\n|---|---:|\n'+'\n'.join(
            f'| {x["reason"]} | {x["count"]} |' for x in r['rejection_counts']),
        '### 3.2. Metadata mâu thuẫn và độ nhạy của chính sách khử trùng',
        f'Có {r["metadata_conflicts"]["popularity_conflict_tracks"]:,} mã bài có nhiều popularity và '
        f'{r["metadata_conflicts"]["feature_conflict_tracks"]:,} mã có nhiều bộ feature. '
        'Chọn dòng popularity cao nhất là chính sách của pipeline, không có nghĩa dòng đó là bản cập nhật mới nhất '
        'vì dataset không cung cấp timestamp cập nhật cho từng dòng. Bảng metadata_conflicts giữ các mã để kiểm tra.',
        f'Kiểm tra độ nhạy trên cùng tập mã bài: popularity trung bình toàn danh mục nếu lấy min là '
        f'{r["metadata_conflicts"]["catalog_mean_if_min_popularity"]:.4f}; nếu lấy max là '
        f'{r["metadata_conflicts"]["catalog_mean_if_max_popularity"]:.4f}. '
        'Khoảng này định lượng ảnh hưởng của hai chính sách lên trung bình chung; chưa chứng minh thứ hạng '
        'của từng genre hoặc từng nghệ sĩ không đổi.',
        '## 4. Phân tích bằng Spark SQL',
        f'Thể loại đứng đầu theo popularity trung bình trong run là **{genres[0]["track_genre"]}**, '
        f'giá trị {genres[0]["avg_popularity"]:.3f}, trên {genres[0]["tracks"]:,} track thuộc nhóm.',
        'Đây là thống kê trong mẫu tại snapshot, không phải thị phần nghe hoặc bảng xếp hạng Spotify hiện tại. '
        'Bảng đầy đủ nằm trong genre_stats.csv; truy vấn tái hiện nằm trong queries.sql. '
        'Các truy vấn khác phân tích phân bố thời lượng, popularity và nghệ sĩ sau khi tách cộng tác.',
        '## 5. Tương quan đặc trưng',
        '| Đặc trưng A | Đặc trưng B | Pearson r |\n|---|---|---:|\n'+'\n'.join(
            f'| {a} | {b} | {v:.4f} |' for _,a,b,v in pairs),
        'Các cặp được xếp theo trị tuyệt đối của hệ số, bỏ đường chéo. Dấu của hệ số mô tả chiều biến thiên tuyến tính. '
        'Tương quan không chứng minh nguyên nhân và không khẳng định người dùng sẽ thích một bài hát.',
        '## 6. Phân cụm bằng MLlib',
        '### 6.1. Chia dữ liệu và chọn tham số',
        f'Chia theo hash của track_id sau khử trùng: train {selection["split_rows"]["train"]:,}, '
        f'validation {selection["split_rows"]["validation"]:,}, test {selection["split_rows"]["test"]:,}. '
        'Ngưỡng bucket 70/85 tạo tỷ lệ xấp xỉ 70%/15%/15%, không ép số lượng chính xác theo tỷ lệ. '
        'StandardScaler chỉ fit trên train, sau đó áp dụng cùng phép biến đổi lên validation và test.',
        'Cần scale vì duration_ms và tempo có đơn vị khác các thuộc tính tỷ lệ. '
        'Chọn k theo silhouette validation lớn nhất; nếu bằng nhau ưu tiên k nhỏ hơn. Test chỉ được đánh giá '
        f'sau khi chọn mô hình, không dùng để chọn k. Seed=42, maxIter={selection["max_iter"]}, '
        f'tol={selection["tol"]} được giữ cố định giữa các ứng viên. Số vòng thực chạy được ghi bên dưới; '
        'ứng viên đạt giới hạn vòng lặp không được tuyên bố đã hội tụ chỉ từ việc fit thành công.',
        '| k | Silhouette validation | Chi phí train | Số vòng |\n|---:|---:|---:|---:|\n'+'\n'.join(
            f'| {t["k"]} | {t["validation_silhouette"]:.6f} | {t["train_cost"]:.3f} | {t["iterations"]} |'
            for t in selection['trials'] if t['validation_silhouette'] is not None),
        '### 6.2. Đánh giá độc lập và mô hình danh mục',
        f'k được chọn: **{r["k"]}**. Silhouette trên test: **{selection["test_silhouette"]:.6f}**. '
        f'Sau đó refit trên toàn bộ danh mục để xuất nhãn; silhouette mô tả toàn bộ dữ liệu là '
        f'**{r["silhouette_squared_euclidean"]:.6f}**. Hai điểm số thuộc hai bối cảnh đánh giá khác nhau.',
        'Silhouette phản ánh sự tách cụm theo squared Euclidean, không phải accuracy hay độ chính xác gợi ý. '
        'Tập test cùng nguồn snapshot nên chưa chứng minh khả năng khái quát sang danh mục ở thời điểm khác. '
        'Tập ứng viên k hữu hạn và một seed chưa chứng minh tối ưu toàn cục hoặc độ ổn định giữa mọi khởi tạo.',
        '### 6.3. Đặc trưng cụm và kiểm tra lưu mô hình',
        '| Cụm | Số bài | Energy | Valence | Danceability | Tempo |\n|---:|---:|---:|---:|---:|---:|\n'+'\n'.join(
            f'| {c["prediction"]} | {c["tracks"]:,} | {c["energy"]:.3f} | {c["valence"]:.3f} | {c["danceability"]:.3f} | {c["tempo"]:.2f} |'
            for c in d['cluster_profiles']),
        f'Mô hình đánh giá được lưu ở models/evaluation; mô hình refit ở models/kmeans. '
        f'Đã nạp lại mô hình refit và đối chiếu nhãn trên {selection["reload_prediction_check_rows"]} bài chọn theo mã; '
        'kết quả trước và sau nạp phải giống nhau. Nhãn cụm chỉ là định danh, không có thứ tự tốt–xấu.',
        '## 7. Thực nghiệm hiệu năng',
        f'Input benchmark gồm {r["benchmark_rows"]:,} dòng; hệ số nhân tải {r["scale_factor"]}. '
        'Cùng phép tổng hợp tổng popularity theo artists, sau đó tổng kiểm tra; các checksum phải bằng nhau. '
        'Mỗi mức partition có một lượt warm-up không đưa vào thống kê thời gian. Ba vòng đo tiếp theo '
        'xáo trộn thứ tự cấu hình với seed=42. AQE tắt trong benchmark để giữ số phân vùng yêu cầu; '
        'repartition theo artists và shuffle.partitions cùng đặt 2, 4 hoặc 8. Thời gian bao gồm đọc và action.',
        '| Partitions | Trung vị giây | Nhỏ nhất | Lớn nhất | Số lần đo |\n|---:|---:|---:|---:|---:|\n'+'\n'.join(
            f'| {m["partitions"]} | {m["median_seconds"]:.4f} | {m["min_seconds"]:.4f} | {m["max_seconds"]:.4f} | {m["repetitions"]} |'
            for m in design['summary']),
        '| Partitions | Lần chạy | Thời gian giây |\n|---:|---:|---:|\n'+'\n'.join(
            f'| {m["partitions"]} | {m["repeat"]} | {m["seconds"]:.4f} |' for m in r['benchmark']),
        'Không kết luận cấu hình nhanh nhất từ một lần chạy. JVM warm-up, OS cache, shuffle và tài nguyên dùng chung '
        'ảnh hưởng kết quả. Nhân tải không tạo thêm bài thật; chỉ dùng để thử hệ thống.',
        '## 8. Kết luận và giới hạn',
        f'Pipeline hoàn thành trong {r["elapsed_seconds"]:.2f} giây, gồm ETL, ghi kết quả, phân cụm và benchmark. '
        'Các tổng kiểm tra bảo đảm số track trong các cụm khớp catalog và phép tính benchmark có cùng kết quả.',
        'Dataset chưa chứa lịch sử nghe hoặc timestamp hành vi nên báo cáo chỉ kết luận về danh mục. '
        'Hướng phát triển: thêm event thật, phân tích theo thời gian, kiểm thử storage nhiều host và so sánh các k. '
        'Mô hình gợi ý cá nhân hóa và huấn luyện GPU thuộc giai đoạn tiếp theo của hệ thống lớn.',
        '## Tài liệu tham khảo',
        '- https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset\n'
        '- https://spark.apache.org/docs/4.0.1/\n'
        '- https://spark.apache.org/docs/4.0.1/ml-clustering.html\n'
        '- https://spark.apache.org/docs/4.0.1/sql-performance-tuning.html'
    ]
    (root/'BAO_CAO_BIGDATA.md').write_text('\n\n'.join(sections)+'\n',encoding='utf-8')


if __name__=='__main__':write_report('reports/bigdata')
