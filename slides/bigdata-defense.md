# Kịch bản bảo vệ 10 slide

1. Tên đề tài, phạm vi môn học và câu hỏi phân tích.
2. Dataset: nguồn, các nhóm feature, số dòng và số track khác nhau.
3. Kiến trúc Docker: driver, master, hai worker, storage mount chung.
4. ETL: null/cast/range, dedup track, bảng track_genres.
5. Spark SQL: mở queries.sql và giải thích JOIN/GROUP BY.
6. Phân tích trực quan: genre, nghệ sĩ, popularity, duration, correlation.
7. MLlib: train/validation/test → scaler fit train → chọn k → test → refit danh mục; đọc profile.
8. Benchmark: warm-up, ba vòng đo xáo trộn, trung vị thời gian, checksum và tài nguyên chung.
9. Demo: docker compose ps → Master UI → dashboard → artifact.
10. Giới hạn, kết luận từ kết quả thật, hướng phát triển cá nhân hóa.

# Demo 5 phút

- 0:00: Mở Spark UI, chỉ ra hai worker ALIVE và application đã hoàn thành.
- 0:45: Mở run.json, giải thích checksum, raw/valid/unique.
- 1:30: Mở dashboard, diễn giải hai biểu đồ và một tương quan.
- 2:30: Giải thích vì sao cần scale trước KMeans, đọc silhouette và profile.
- 3:30: So sánh các lần benchmark, giải thích vì sao nhiều partition có thể chậm hơn.
- 4:30: Mở thư mục Parquet và model, nêu giới hạn dataset snapshot.

# Câu hỏi thường gặp

**Vì sao dùng Spark khi dataset nhỏ?** Để triển khai, kiểm chứng quy trình xử lý phân tán;
không khẳng định Spark nhanh hơn pandas trên 114K dòng. Tải lớn hơn phải thử riêng.

**Phân tán ở đâu?** Driver tạo DAG; master phân bổ executor trên hai worker;
tasks xử lý partition. Hai worker container vẫn cùng phần cứng.

**Tại sao không xóa trùng theo tên?** Cùng tên có thể là bản thu khác; track_id là khóa catalog.

**Có phân tích xu hướng người dùng chưa?** Dataset không có sự kiện người dùng.
Bản môn Big Data phân tích đặc trưng danh mục; hệ thống lớn sẽ bổ sung event timestamp.

**Silhouette cao có nghĩa gợi ý tốt?** Không. Nó đánh giá cấu trúc cụm theo metric đã chọn.
Chất lượng cá nhân hóa phải đánh giá bằng tương tác thật và metric ranking.

**Có HDFS không?** Không; demo dùng thư mục host mount cùng đường dẫn cho các container.
Triển khai nhiều host cần storage chung phù hợp như HDFS hoặc object storage.
