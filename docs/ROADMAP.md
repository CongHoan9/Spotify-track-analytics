# Lộ trình kỹ thuật

| Giai đoạn | Đầu ra | Trạng thái source |
|---|---|---|
| 1. Data foundation | Download versioned, quality, track/genre dedup | Đã có |
| 2. App MVP | Auth, onboarding, search, like/dislike, playlist | Đã có |
| 3. Recommendation | Standardized cosine, profile, filtering | Đã có |
| 4. GPU experiment | Autoencoder, split, early stopping, Drive export | Đã có notebook/code; GPU do người dùng chạy |
| 5. Spark analytics | Bronze/Silver/Gold, genre stats, KMeans | Đã có code/notebook |
| 6. Events | Transactional outbox, Kafka raw ingestion, batch trends | Đã có code; cần kiểm thử dịch vụ thực |
| 7. Academic evaluation | Real temporal holdout, Recall/NDCG, ablation | Cần dữ liệu tương tác thật |
| 8. Scale | ANN, Redis, S3/Delta, orchestration, multi-host benchmark | Chưa triển khai |
| 9. Production | Migrations, TLS, rate limits, backups, monitoring | Chưa hoàn tất |

## Gợi ý lịch 12 tuần

Tuần 1–2: khảo sát dữ liệu, tái hiện pipeline, đọc data contract.
Tuần 3–4: demo app, thu phản hồi thử nghiệm có đồng ý, kiểm tra lỗi UI/API.
Tuần 5–6: chạy Colab GPU, so sánh baseline, kiểm tra export/import và tài liệu.
Tuần 7–8: Spark EDA, streaming, benchmark với dữ liệu thật/mô phỏng tách biệt.
Tuần 9–10: đánh giá theo thời gian, thêm ALS/BPR nếu đủ dữ liệu; chọn cải tiến có bằng chứng.
Tuần 11–12: kiểm thử phục hồi, báo cáo kết quả, hoàn thiện slide và video demo.

## Tiêu chí nghiệm thu

- Người mới chọn genre, like bài, nhận gợi ý không chứa bài đã like/dislike.
- Retry cùng event không tăng đếm; tài khoản khác không sửa playlist.
- Tải dataset, train, lưu Drive, đưa model về ứng dụng theo hướng dẫn.
- Spark xuất bảng Gold và model KMeans; báo số dòng trước/sau cleaning.
- Báo cáo chỉ chứa kết quả đo thật; công bố CPU/GPU, RAM, version và dataset hash.
- Không có secret, model binary, dữ liệu người dùng trong Git.
