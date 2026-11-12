# Vận hành

## Môi trường

Python 3.11; Spark 3.5.3 + Java 17 trên WSL/Linux/Colab. Cài `.[spark]` riêng khi cần để không
bắt API kéo runtime Spark. PyTorch dùng bản có CUDA sẵn trên Colab; notebook kiểm tra GPU trước train.
Các dependency ứng dụng có version range; notebook lưu `pip freeze` của mỗi run.

## Kafka / streaming local

```bash
docker compose --profile streaming up --build -d
pip install -e '.[spark]'
# Compose đã chạy outbox publisher cho PostgreSQL.
# Chỉ chạy lệnh dưới nếu API đang chạy local SQLite, không dùng publisher Compose:
python -m pipelines.outbox
```

Trong terminal khác, từ repository root (đặt PYTHONPATH=. nếu spark-submit không thấy module):

```bash
spark-submit --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 pipelines/stream.py
python -m pipelines.trends --format parquet --input data/lake/bronze/events
```

Kafka Compose quảng bá localhost:9092 cho Spark chạy trên host và kafka:29092 cho publisher trong Compose.
Giữ checkpoint ổn định, không dùng chung checkpoint giữa hai query, không xóa khi restart bình thường.
Không coi Kafka single broker là HA. Topic mặc định có thể được auto-create cho demo.

## Export event không cần Kafka

```bash
python -m pipelines.export_events
python -m pipelines.trends
```

## Kiểm thử tải có kiểm soát

Sinh 100K, 1M, 10M events bằng simulator seed cố định. Đo wall time, peak memory, shuffle,
số partition, CPU, dung lượng, số worker. Dùng cùng input và cùng phép tính khi so sánh.
Không đưa số giả định vào báo cáo kết quả. UI/API exact retrieval có giới hạn riêng với Spark ETL.

## Sao lưu và triển khai

Backup PostgreSQL bằng pg_dump; backup model bundle theo run ID. Thử restore trước buổi demo.
Public deployment cần TLS reverse proxy, rate limiting auth, quản lý secrets, migration DB và giám sát.
Không bật `--reload` trên production. Upload model mới vào thư mục khác rồi chuyển MODEL_DIR và restart.
