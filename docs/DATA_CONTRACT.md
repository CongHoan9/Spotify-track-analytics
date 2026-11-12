# Data contracts

## Catalog

Khóa: track_id. Bắt buộc track_name, artists, track_genre, popularity và 10 audio feature.
Genre nhiều giá trị lưu trong cột `genres` ngăn bằng `|` ở artifact, bảng bridge ở Spark Silver.
Không xem số dòng CSV là số bài duy nhất. Các thống kê luôn công bố đơn vị đếm.

## Event v1

| Field | Quy tắc |
|---|---|
| event_id | UUID, định danh một hành động, reuse khi retry |
| user_id | Backend lấy từ token; client không được tự nhận user_id |
| track_id | Phải có trong catalog |
| event_type | like, dislike, unlike, open_spotify |
| event_time | Backend tạo UTC; không tin timestamp client |
| source | Backend real; simulator synthetic |

Không gọi `open_spotify` là lượt nghe. Không có telemetry về nghe hết, skip hay duration nghe.
Một event_id trùng payload trả duplicate; trùng ID khác payload trả 409.
`source` luôn nằm trong khóa groupBy của trend để tách số liệu mô phỏng và thực.

## Artifact schema v1

tracks.csv và embeddings.npz có cùng thứ tự hàng. manifest.json ghi số hàng, chiều vector,
model_type, feature list và SHA256 của cả hai. Vectors float32 đã L2 normalize.
Inference kiểm tra checksum trước khi nạp. Tải NPZ bằng allow_pickle=False.
Bundle là artifact bất biến theo run ID; không chỉnh riêng catalog hoặc embedding.

## Chất lượng gợi ý

Reconstruction MSE chỉ dùng kiểm tra mô hình biểu diễn. Với tương tác thật:
chia toàn cục theo thời gian; fit/preprocess chỉ dùng dữ liệu khả dụng trước cutoff;
profile lấy like trước cutoff; positive test lấy like mới sau cutoff;
loại track đã thấy theo cùng một quy tắc ở mọi baseline; báo số user/item cold-start;
đo Recall@K, NDCG@K, coverage, diversity trên cùng candidate catalog.
Chưa có dữ liệu thật đủ lớn để đưa ra các metric này trong bản bàn giao.
