# Kiểm chứng bản bàn giao — 09/11/2026

## Đã chạy

- Tải ZIP dataset trực tiếp từ public endpoint Kaggle thành công.
- CSV gốc: 114.000 dòng, 89.741 track_id duy nhất, 114 genre.
- Sau lọc metadata/feature không hợp lệ: 89.740 track dùng được.
- Build baseline trên toàn bộ dataset, xuất và nạp bundle checksum.
- `pytest`: 5 test đạt, gồm dedup giữ genre, checksum, auth, event idempotency,
  playlist isolation, train/export/import model CPU và temporal ranking evaluation.
- Browser smoke: register → recommendations → like → playlist; desktop và mobile,
  không có JavaScript page error và không tràn ngang mobile. Dùng fixture mô phỏng riêng.
- Hai notebook: schema nbformat hợp lệ, toàn bộ code cell compile được.
- JavaScript: `node --check` đạt. Python compileall đạt.
- Docker Compose: cấu hình parse hợp lệ.

## Chưa xác minh đầy đủ

- GPU và mount/save Google Drive: cần chạy trong Colab của người dùng.
- Spark native Windows: Spark 4.0.1 khởi động và count được, nhưng pipeline ghi Parquet
  bị chặn bởi thiếu HADOOP_HOME/winutils. Notebook cung cấp Java 17 + Spark 3.5.3 trên Colab;
  chưa chạy toàn pipeline trong Colab tại phiên bàn giao này.
- Docker daemon chưa hoạt động; chưa chạy PostgreSQL/Kafka/outbox/streaming end-to-end.
- Chưa có benchmark production hoặc kết quả ranking trên lượng lớn user thật.

Các screenshot ở reports/figures là ảnh kiểm thử bằng fixture; không dùng như bằng chứng
chất lượng recommendation hoặc số liệu nghiên cứu trên dữ liệu thật.
