"""Patch report content in place; retain original OOXML formatting and untouched ZIP parts."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from copy import deepcopy
import hashlib
import json
import shutil
from lxml import etree as E

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'BuiThiThanhTuyen_12523091_12423TN.docx'
QA = ROOT / 'reports/template-qa'
QA.mkdir(parents=True, exist_ok=True)
BACKUP = QA / 'original-template.docx'
if not BACKUP.exists():
    shutil.copy2(TARGET, BACKUP)
with ZipFile(BACKUP) as z:
    parts = {n: z.read(n) for n in z.namelist()}
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{'+NS['w']+'}'
doc = E.fromstring(parts['word/document.xml'])
body = doc.find('w:body', NS)
paragraphs = body.findall('w:p', NS)
tables = body.findall('w:tbl', NS)
def text(p):
    return ''.join(p.xpath('.//w:t/text()', namespaces=NS))
dump = [{'index': i, 'text': text(p), 'xml': E.tostring(p, encoding='unicode')} for i,p in enumerate(paragraphs)]
(QA/'source-dump.json').write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding='utf-8')
def put(p, value):
    nodes = p.findall('.//w:t', NS)
    if not nodes:
        run = E.SubElement(p,W+'r'); nodes=[E.SubElement(run,W+'t')]
    nodes[0].text=value
    nodes[0].set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    for t in nodes[1:]: t.text=''
def block(start, end, values):
    assert len(values)<=end-start+1,(start,end,len(values))
    for i,value in enumerate(values): put(paragraphs[start+i],value)
    for p in paragraphs[start+len(values):end+1]:
        # Preserve section geometry if a section boundary happens to be in this slot.
        if p.find('.//w:sectPr',NS) is not None: put(p,'')
        else: body.remove(p)
def one(i,value): put(paragraphs[i],value)
title='Xây dựng hệ thống gợi ý âm nhạc cá nhân hóa quy mô lớn và phân tích xu hướng người dùng'
one(10,title.upper())
one(47,f'Em xin cam đoan đồ án với đề tài “{title}” được trình bày trên cơ sở quá trình nghiên cứu, xây dựng và kiểm thử hệ thống. Các nguồn dữ liệu, tài liệu tham khảo và kết quả thực nghiệm được phân biệt rõ; những chức năng chưa được kiểm chứng đầy đủ được nêu trong phạm vi và giới hạn của đề tài.')
block(70,76,[
'Danh mục âm nhạc trực tuyến có nhiều bài hát và thể loại, trong khi thời gian tìm kiếm của mỗi người dùng có giới hạn. Việc chỉ hiển thị danh sách phổ biến khó phản ánh đầy đủ sở thích cá nhân. Hệ thống gợi ý có vai trò lựa chọn các bài hát phù hợp từ danh mục, hỗ trợ khám phá và giảm công sức tìm kiếm.',
'Sở thích âm nhạc có thể được biểu diễn thông qua các đặc trưng như mức năng lượng, nhịp độ, sắc thái cảm xúc và tính chất âm thanh. Khi kết hợp các đặc trưng này với phản hồi thích hoặc không quan tâm, hệ thống có thể xây dựng hồ sơ sở thích và điều chỉnh danh sách gợi ý theo từng người dùng.',
'Đề tài sử dụng Spotify Tracks Dataset của Maharshi Pandya [1]. Tệp dữ liệu được tải trong quá trình triển khai có 114.000 dòng, 114 thể loại và 89.741 mã bài hát phân biệt. Sau kiểm tra dữ liệu thiếu và tính hợp lệ, danh mục phục vụ mô hình còn 89.740 bài. Số dòng dữ liệu không đồng nhất với số bài hát do một bài có thể xuất hiện dưới nhiều thể loại.',
'Dataset cung cấp metadata và đặc trưng âm nhạc nhưng không có lịch sử nghe của người dùng. Vì vậy, cá nhân hóa ban đầu dựa trên sở thích khai báo và phản hồi thu thập trong ứng dụng. Phân tích xu hướng theo thời gian sử dụng sự kiện có timestamp của ứng dụng; không suy diễn xu hướng nghe toàn bộ Spotify từ một snapshot popularity.',
'Apache Spark hỗ trợ xử lý dữ liệu theo mô hình phân tán, phù hợp để tổ chức quy trình làm sạch, thống kê và phân cụm [2]. PyTorch được sử dụng cho thí nghiệm học biểu diễn trên GPU Colab [3]. Hai thành phần cùng phục vụ một hệ thống, trong đó xử lý dữ liệu và huấn luyện được tách khỏi luồng phản hồi trực tiếp cho người dùng.',
f'Vì các lý do trên, đề tài “{title}” được lựa chọn để kết hợp nội dung môn Big Data với xây dựng ứng dụng. Quy mô lớn là định hướng kiến trúc và mục tiêu đánh giá tải; khả năng đáp ứng thực tế phải được chứng minh bằng benchmark trên cấu hình được công bố.',
'Kết quả hướng đến một quy trình xuyên suốt từ dữ liệu đầu vào, phân tích Spark, học biểu diễn, xuất mô hình đến cung cấp gợi ý trên web và thu thập phản hồi. Hệ thống tạo cơ sở để nghiên cứu tiếp collaborative filtering, chỉ mục tìm kiếm gần đúng và hạ tầng xử lý nhiều máy.'
])
one(78,'Mục tiêu tổng quát là xây dựng nền tảng gợi ý âm nhạc theo sở thích cá nhân và phân tích hành vi người dùng, sử dụng Apache Spark cho xử lý dữ liệu và hỗ trợ huấn luyện mô hình biểu diễn âm nhạc trên Google Colab GPU.')
block(80,87,[
'Khảo sát nhu cầu khám phá âm nhạc, xác định người sử dụng và các tình huống nghiệp vụ.',
'Tổ chức pipeline tải dữ liệu, kiểm tra chất lượng, khử trùng theo track_id và bảo toàn các thể loại của mỗi bài hát.',
'Xây dựng baseline gợi ý dựa trên đặc trưng âm nhạc chuẩn hóa và độ tương đồng cosine.',
'Nghiên cứu denoising autoencoder bằng PyTorch, chia tập dữ liệu và xuất artifact phục vụ suy luận.',
'Xây dựng ứng dụng cho phép đăng ký, chọn sở thích, tìm kiếm, phản hồi và quản lý playlist.',
'Phân tích dữ liệu bằng Spark SQL, phân cụm KMeans và tổng hợp sự kiện theo thời gian.',
'Đánh giá tính đúng của hệ thống, chất lượng xếp hạng khi đủ tương tác thật và hiệu năng xử lý theo từng mức tải.',
'Kết quả mong đợi là repository có khả năng tái hiện, notebook Colab, ứng dụng demo và tài liệu phân tích. Các metric chưa đo không được trình bày như kết quả thực nghiệm.'
])
block(91,96,[
'Tải Spotify Tracks Dataset và kiểm tra cấu trúc dữ liệu đầu vào.',
'Cho phép đăng ký, đăng nhập, chọn thể loại và tìm bài hát hoặc nghệ sĩ.',
'Cung cấp danh sách gợi ý kèm lý do dựa trên hồ sơ sở thích hiện tại.',
'Ghi nhận thích, bỏ thích, không quan tâm và thao tác mở liên kết Spotify.',
'Tạo playlist cá nhân, thêm bài hát và xem thống kê tương tác của chính tài khoản.',
'Thực hiện ETL, thống kê và phân cụm bằng Spark; hỗ trợ xuất dữ liệu sự kiện để phân tích.'
])
one(98,'Đối tượng trực tiếp là người dùng muốn khám phá và lưu bài hát theo sở thích. Người phát triển và người phân tích dữ liệu vận hành pipeline, huấn luyện và đánh giá mô hình thông qua notebook hoặc công cụ dòng lệnh. Môi trường triển khai gồm ứng dụng web local, PostgreSQL trong Docker, Spark trên Linux hoặc Colab và GPU Colab cho thí nghiệm PyTorch.')
block(100,104,[
'Dataset không chứa file âm thanh, lịch sử nghe, thông tin tài khoản Spotify hoặc nhãn đánh giá người dùng. Ứng dụng mở liên kết Spotify và không quan sát được thời lượng nghe thực tế.',
'Popularity là thuộc tính tại thời điểm thu thập dữ liệu; không đại diện cho xu hướng hiện tại hoặc chuỗi thời gian nghe.',
'Dữ liệu mô phỏng chỉ dùng kiểm thử pipeline và tải. Các thống kê từ dữ liệu mô phỏng phải được tách khỏi dữ liệu thật.',
'MSE tái tạo của autoencoder phản ánh khả năng học biểu diễn, không phải độ chính xác gợi ý. Recall@K và NDCG@K cần tương tác thật cùng giao thức đánh giá theo thời gian.',
'Bản hiện tại dùng truy hồi vector chính xác và chạy demo local. Chưa chứng minh tải production, chưa hoàn tất kiểm thử Kafka nhiều dịch vụ và chưa chạy GPU Colab trong phiên kiểm chứng local.'
])
block(106,114,[
'Nghiên cứu gợi ý dựa trên nội dung, hồ sơ sở thích, cosine similarity và cách đánh giá hệ thống xếp hạng.',
'Khảo sát chức năng, tác nhân, dữ liệu đầu vào và các ràng buộc của ứng dụng.',
'Thu thập dữ liệu từ Kaggle, lưu nguồn và SHA256; kiểm tra miền giá trị và các mã bài hát lặp.',
'Xây dựng baseline, notebook autoencoder và quy trình lưu model, scaler, vector, metrics vào Drive.',
'Tổ chức pipeline Spark theo các lớp Bronze, Silver, Gold và phân cụm KMeans.',
'Thiết kế dữ liệu tài khoản, phản hồi, playlist và sự kiện; tách dữ liệu phục vụ API khỏi dữ liệu phân tích.',
'Xây dựng FastAPI và giao diện web, tích hợp gợi ý và vòng phản hồi cá nhân hóa.',
'Kiểm thử quyền truy cập, sự kiện trùng, checksum artifact, train và nạp model; chuẩn bị đánh giá xếp hạng theo thời gian.',
'Tổng hợp kết quả đã đo, công bố giới hạn môi trường và đề xuất lộ trình mở rộng.'
])
one(117,'Khảo sát luồng khám phá bài hát, xác định nhu cầu của người dùng mới và người dùng đã có phản hồi. Phân tích dataset để phân biệt dữ liệu danh mục với hành vi người dùng; từ đó lập các yêu cầu chức năng, data contract và kịch bản kiểm thử.')
one(119,'Lựa chọn content-based làm baseline vì dataset có đặc trưng bài hát nhưng thiếu lịch sử nghe. Autoencoder có kiến trúc 10–64–8–64–10, dùng nhiễu Gaussian trong train và tối ưu AdamW. Dữ liệu được chia 80/10/10 theo track duy nhất, scaler chỉ fit trên train, early stopping dùng validation. Mô hình được so sánh với baseline trước khi quyết định sử dụng [3].')
one(121,'Hệ thống tách thành các thành phần tải và chuẩn hóa dữ liệu, xử lý Spark, huấn luyện, quản lý artifact, API và giao diện. API đọc vector đã xuất thay vì chạy Spark theo từng request. Sự kiện được ghi cùng transaction với phản hồi; publisher có thể chuyển chúng sang Kafka để phục vụ pipeline phân tích.')
block(123,124,[
'Kiểm thử chức năng gồm đăng ký, đăng nhập, sở thích, playlist, gợi ý và ghi sự kiện. Kiểm thử dữ liệu gồm khử trùng track, bảo toàn genre và phát hiện artifact bị sửa. Năm test tự động đã đạt; kiểm thử trình duyệt bằng fixture đã kiểm tra luồng sử dụng trên desktop và mobile.',
'Đánh giá mô hình dự kiến sử dụng Recall@K, NDCG@K và catalog coverage với tương tác thật chia theo thời gian. Đánh giá hạ tầng đo thời gian ETL, throughput, độ trễ và tài nguyên trên cấu hình công bố. Spark local không thay thế benchmark cluster; dữ liệu mô phỏng không chứng minh sở thích người dùng thực.'
])
block(129,133,[
'Trong phạm vi khảo sát bài toán, người dùng có thể tìm bài theo tên hoặc nghệ sĩ, duyệt danh mục và lưu playlist. Khi danh mục tăng, việc khám phá các bài chưa biết đòi hỏi cơ chế lựa chọn dựa trên tín hiệu sở thích.',
'Danh sách phổ biến có ưu điểm dễ xây dựng nhưng cung cấp kết quả tương tự cho nhiều người. Hồ sơ sở thích có thể giúp thay đổi thứ tự bài hát, song cần xử lý trường hợp chưa có phản hồi và tránh lặp lại quá nhiều bài của cùng nghệ sĩ.',
'Nguồn dữ liệu ban đầu chỉ mô tả bài hát. Để nghiên cứu hành vi, ứng dụng phải tự ghi nhận sự kiện với mã người dùng và thời gian. Sự kiện mở liên kết chỉ thể hiện hành động trong ứng dụng, không được xem như xác nhận đã nghe nhạc.',
'Đề tài kết hợp Spark SQL để phân tích danh mục, KMeans để khảo sát cấu trúc đặc trưng và mô hình content-based để cung cấp gợi ý. Khi có tương tác thật đủ lớn, collaborative filtering và hybrid có thể được bổ sung và đánh giá trên cùng giao thức.',
'Bài toán thiết kế gồm hai yêu cầu liên quan: phản hồi gợi ý nhanh trên web và xử lý dữ liệu có thể mở rộng phía sau. Vì vậy, artifact và dữ liệu phục vụ API được tách khỏi các job phân tích, huấn luyện chạy theo lô.'
])
one(135,'Các đối tượng và thành phần tham gia được phân biệt theo chức năng. Bản hiện tại có tài khoản người dùng trên web; vai trò vận hành và phân tích thực hiện qua công cụ phát triển, chưa có giao diện quản trị phân quyền riêng.')
block(136,141,['a) Người vận hành hệ thống','Người vận hành tổ chức dữ liệu và duy trì môi trường chạy. Các nhiệm vụ bao gồm:','Thiết lập database, biến môi trường và bảo vệ secret.','Tải, kiểm tra và cập nhật danh mục bài hát.','Chọn model bundle và kiểm tra tính toàn vẹn trước khi triển khai.','Theo dõi log, sao lưu dữ liệu và kiểm tra các pipeline.'])
block(142,148,['b) Người dùng khám phá âm nhạc','Người dùng trực tiếp tương tác với giao diện. Các chức năng chính bao gồm:','Đăng ký, đăng nhập và chọn thể loại quan tâm.','Tìm kiếm và xem danh sách gợi ý.','Thích, bỏ thích hoặc ẩn bài không phù hợp.','Tạo playlist và lưu các bài hát đã chọn.','Xem thống kê tương tác cá nhân và mở liên kết Spotify.'])
one(149,'c) Thành phần gợi ý và học máy')
one(150,'Thành phần gợi ý nạp vector bài hát và tạo profile từ các bài đang được thích. Hệ thống tính cosine similarity, bổ sung ưu tiên thể loại, loại bài đã thích hoặc đã ẩn và giới hạn số bài cùng nghệ sĩ chính. Với người dùng mới, thứ tự được khởi tạo từ popularity snapshot và sở thích khai báo.')
one(151,'d) Nguồn dữ liệu và hệ thống phân tích')
one(152,'CSV Spotify cung cấp danh mục; API cung cấp sự kiện hành vi; Spark tiếp nhận dữ liệu phục vụ làm sạch, thống kê và phân cụm. Colab GPU là môi trường huấn luyện mô hình PyTorch, không phải thành phần bắt buộc của luồng phục vụ API.')
one(154,'Quy trình nghiệp vụ được tổ chức từ chuẩn bị danh mục đến cá nhân hóa và tiếp nhận phản hồi. Các bước đề xuất như sau:')
block(155,172,[
'Bước 1: Chuẩn bị dữ liệu âm nhạc','Tải CSV, xác nhận các cột bắt buộc, lưu nguồn và checksum. Những dòng không hợp lệ được loại trước khi tạo danh mục phục vụ mô hình.',
'Bước 2: Xây dựng đặc trưng','Chuẩn hóa các biến âm nhạc và gộp metadata theo track_id. Tập thể loại được giữ đầy đủ; vector cùng metadata được lưu theo thứ tự hàng thống nhất.',
'Bước 3: Khởi tạo hồ sơ sở thích','Người dùng đăng nhập và chọn thể loại. Các tín hiệu được sử dụng gồm:','Thể loại khai báo khi bắt đầu sử dụng.','Danh sách bài đang được thích.','Danh sách bài không quan tâm để loại khỏi gợi ý.',
'Bước 4: Lựa chọn và xếp hạng','Tính điểm phù hợp giữa profile và vector bài hát, kết hợp ưu tiên thể loại. Khi chưa có like, hệ thống dùng popularity trong dataset làm phương án khởi đầu.',
'Các bài đã thích hoặc đã ẩn bị loại; danh sách được giới hạn số bài cùng nghệ sĩ để tăng độ đa dạng.',
'Bước 5: Hiển thị gợi ý','Ứng dụng hiển thị tên bài, nghệ sĩ, thể loại, lý do gợi ý và thao tác mở Spotify. Điểm tương đồng không được diễn giải như xác suất người dùng sẽ thích.',
'Bước 6: Ghi nhận phản hồi','Thao tác thích, bỏ thích hoặc không quan tâm cập nhật trạng thái feedback và ghi sự kiện trong cùng transaction. API tạo thời gian UTC và lấy user_id từ token đăng nhập.',
'Bước 7: Phân tích hành vi','Sự kiện được xuất JSONL hoặc chuyển qua Kafka. Spark khử trùng event_id và tổng hợp theo ngày, nguồn dữ liệu và loại tương tác để phục vụ phân tích.'
])
block(175,179,['a) Dữ liệu đầu vào','Danh mục bài hát: track_id, track_name, artists, popularity, track_genre và các đặc trưng âm nhạc.','Sở thích người dùng: thể loại khai báo và trạng thái phản hồi trên từng bài.','Artifact mô hình: metadata, vector, manifest và checksum; mô hình GPU có thêm state_dict và scaler.','Dữ liệu tài khoản và sự kiện: thông tin đăng nhập, event_id, loại hành động và timestamp UTC.'])
block(181,185,['Danh sách gợi ý: Top-K bài hát và lý do phù hợp với profile hiện tại.','Playlist: danh sách bài được người dùng lựa chọn và lưu riêng theo tài khoản.','Dữ liệu phân tích: bảng thống kê genre, chất lượng dữ liệu và nhãn cụm KMeans.','Dữ liệu hành vi: số tương tác theo ngày, loại sự kiện và nguồn real hoặc synthetic.','Artifact huấn luyện: model, scaler, embeddings, metrics và thông tin môi trường phục vụ tái hiện.'])
one(191,'Hai nhóm tác nhân được phân biệt ở mức nghiệp vụ; quyền quản trị web là hướng mở rộng. Trong bản triển khai hiện tại, API xác thực tài khoản và kiểm tra quyền sở hữu dữ liệu cá nhân.')
block(192,198,['a) Người vận hành và phân tích dữ liệu','Nhóm này sử dụng notebook và công cụ dòng lệnh để thực hiện:','Thiết lập môi trường và database.','Kiểm tra nguồn và chất lượng dataset.','Chạy Spark ETL, thống kê và phân cụm.','Huấn luyện trên Colab, lưu artifact vào Drive và nạp model.','Đánh giá, sao lưu và theo dõi vận hành.'])
block(199,206,['b) Người dùng','Người dùng thao tác trên web với các chức năng:','Đăng ký, đăng nhập và đăng xuất.','Chọn thể loại, tìm kiếm bài hát hoặc nghệ sĩ.','Xem danh sách gợi ý và lý do gợi ý.','Phản hồi thích, bỏ thích hoặc không quan tâm.','Tạo playlist và thêm bài vào playlist thuộc sở hữu.','Xem hoạt động cá nhân và mở bài trên Spotify.'])
block(211,217,[
'Hiệu năng: API phục vụ từ vector đã xuất; đo latency theo tải thực tế. Các job Spark và huấn luyện không chạy trong từng request.',
'Chất lượng gợi ý: so sánh baseline và mô hình học biểu diễn bằng cùng tập đánh giá. Chỉ kết luận hiệu quả khi có metric từ tương tác thật.',
'Tính ổn định: mỗi sự kiện có event_id duy nhất, hỗ trợ retry mà không tăng đếm; streaming giữ checkpoint riêng cho từng query.',
'Bảo mật: mật khẩu băm có salt, token hết hạn và kiểm tra quyền sở hữu playlist. Secret được giữ ngoài Git.',
'Tính dễ sử dụng: giao diện hỗ trợ desktop và mobile, có trạng thái lỗi và hướng dẫn khi chưa đăng nhập.',
'Khả năng mở rộng: tách API, lưu trữ và pipeline; ANN, cache và cluster nhiều máy được bổ sung theo kết quả benchmark.',
'Khả năng bảo trì: mã nguồn tách theo chức năng, có kiểm thử, data contract, notebook và artifact version theo run.'
])
block(219,234,[
'Quy trình kỹ thuật gồm chuẩn bị dữ liệu, huấn luyện ngoại tuyến, phục vụ trực tuyến và phân tích sự kiện.',
'Bước 1: Tiếp nhận dữ liệu','Tải dataset qua endpoint công khai của Kaggle; có nguồn dự phòng cùng tác giả trên Hugging Face. URL và SHA256 được lưu để truy vết.',
'Bước 2: Tiền xử lý','Ép kiểu số, kiểm tra miền giá trị, loại dòng thiếu thông tin thiết yếu và khử trùng theo track_id. Spark lưu lớp Bronze, Silver và Gold bằng Parquet.',
'Bước 3: Tạo mô hình và artifact','Baseline chuẩn hóa 10 đặc trưng; phương án GPU dùng denoising autoencoder. Notebook chia dữ liệu, fit scaler trên train, chọn model theo validation và đánh giá test sau cùng.',
'Bước 4: Nạp và kiểm tra model','Backend xác minh SHA256 của catalog và embeddings, kiểm tra số hàng và giá trị vector trước khi khởi động.',
'Model mới được đặt trong thư mục riêng; thay MODEL_DIR và khởi động lại API để chuyển phiên bản.',
'Bước 5: Phục vụ gợi ý','API đọc feedback hiện tại, tạo profile, tính độ tương đồng và lọc danh sách. Frontend hiển thị kết quả cùng các thao tác phản hồi.',
'Bước 6: Lưu trạng thái và sự kiện','Feedback và event được ghi nguyên tử. Outbox gửi event đến Kafka theo cơ chế at-least-once; consumer phải khử trùng bằng event_id [4].',
'Bước 7: Tổng hợp và đánh giá','Spark tổng hợp sự kiện từ dữ liệu đã lưu. Bản hiện tại lưu raw bằng streaming và tính trend theo batch; chưa triển khai dashboard streaming tức thời. Script đánh giá xếp hạng chỉ dùng source real và chia theo thời gian.'
])
one(236,'Thiết kế dữ liệu gồm hai miền: dữ liệu giao dịch phục vụ ứng dụng và dữ liệu danh mục, phân tích phục vụ mô hình. Bản hiện tại dùng SQLAlchemy với SQLite khi chạy local hoặc PostgreSQL khi chạy Compose; catalog và vector nằm trong artifact, các bảng phân tích nằm trong Parquet.')
one(239,'Các thực thể dưới đây mô tả mô hình logic. Feedback, Users, Playlists, Events và Playlist_Items đã có trong database ứng dụng; Tracks và Track_Genres được lưu ở artifact hoặc Spark Silver, chưa phải bảng SQL của backend.')
one(240,'Events giữ lịch sử hành động, còn Feedback giữ trạng thái hiện tại của một cặp người dùng và bài hát. Tracks định danh bài hát; Track_Genres bảo toàn quan hệ nhiều thể loại. Cách tách này tránh suy diễn trạng thái hiện tại chỉ bằng cách đếm toàn bộ sự kiện lịch sử.')
one(242,'Các thuộc tính sau bám theo dữ liệu của bản triển khai. Ràng buộc tham chiếu catalog được API kiểm tra vì catalog và database được lưu ở hai miền khác nhau.')
for a,b,c,d in [
(243,244,'a) Feedback – Trạng thái sở thích','Lưu phản hồi hiện tại trên từng cặp người dùng và bài hát; khóa ghép ngăn xuất hiện nhiều trạng thái đồng thời.'),
(246,247,'b) Users – Tài khoản người dùng','Lưu tài khoản, mật khẩu băm và thể loại khai báo. Tên trường khớp với mô hình SQLAlchemy của backend.'),
(249,250,'c) Playlists – Danh sách phát cá nhân','Lưu playlist và chủ sở hữu. Mọi thao tác thêm bài đều phải kiểm tra user_id của playlist.'),
(252,253,'d) Events – Lịch sử tương tác','Lưu sự kiện bất biến theo event_id, hỗ trợ tổng hợp hành vi và cơ chế outbox.'),
(255,256,'e) Tracks – Danh mục bài hát','Thực thể danh mục nằm trong tracks.csv và Spark Silver. Bảng dưới mô tả nhóm thuộc tính chính; các audio feature là số thực.'),
(258,259,'f) Playlist_Items – Bài hát trong playlist','Bảng liên kết playlist với catalog; khóa ghép ngăn một bài được thêm lặp trong cùng playlist.'),
(261,262,'g) Track_Genres – Quan hệ bài hát và thể loại','Bảng logic trong Spark Silver gồm các cặp track_id và track_genre khác nhau; artifact thể hiện tập này bằng cột genres.')]:
    one(a,c); one(b,d)
one(245,'state nhận các giá trị like, dislike hoặc unlike. unlike làm mất tác dụng của like trong profile, đồng thời giữ lịch sử trong Events.')
one(248,'password lưu chuỗi salt và mã băm PBKDF2-SHA256, không lưu mật khẩu gốc. genres lưu danh sách thể loại dạng JSON; id là UUID dạng chuỗi.')
one(251,'Playlist chỉ được truy cập bởi chủ sở hữu qua API. Bản hiện tại chưa cung cấp chia sẻ playlist công khai hoặc phân quyền cộng tác.')
one(254,'published thể hiện trạng thái đã gửi Kafka. Nếu publisher dừng sau khi Kafka xác nhận nhưng trước khi commit database, event có thể được gửi lại; bước tổng hợp phải deduplicate theo event_id.')
one(257,'Vector đầu vào gồm danceability, energy, loudness, speechiness, acousticness, instrumentalness, liveness, valence, tempo và duration_ms. Popularity phục vụ fallback, không được dùng làm nhãn sở thích người dùng.')
one(260,'playlist_id tham chiếu Playlists; track_id được đối chiếu với catalog khi thêm bài. Việc kiểm tra quyền sở hữu vẫn cần thực hiện ngay cả khi mã playlist hợp lệ.')
one(263,'Một track có thể thuộc nhiều genre. Khi thống kê theo genre, một track được tính ở mỗi genre tương ứng; không cộng tổng các nhóm để suy ra số track phân biệt trong danh mục.')
one(266,'Quan hệ SQL được khai báo cho dữ liệu giao dịch. Các quan hệ tới Tracks được đảm bảo bằng kiểm tra API và kiểm tra chất lượng trong pipeline. Không mặc định rằng khóa ngoại database bao phủ catalog nằm ngoài database.')
block(270,274,[
'Hạn chế dữ liệu trùng: track_id định danh catalog, event_id định danh hành động; Feedback và Playlist_Items sử dụng khóa ghép phù hợp.',
'Tính hợp lệ: đặc trưng tỷ lệ nằm trong khoảng 0 đến 1, duration_ms dương và popularity nằm trong khoảng 0 đến 100; vector nạp vào phải hữu hạn.',
'Bảo mật: mật khẩu được băm; user_id lấy từ phiên đăng nhập; tài khoản khác không được thêm bài vào playlist không thuộc sở hữu.',
'Hỗ trợ tra cứu: tạo chỉ mục cho user_id, track_id và event_time của Events. Khi tăng quy mô cần đánh giá thêm kế hoạch truy vấn và chính sách lưu trữ.',
'Lưu trữ artifact: database không chứa model binary. Bundle lưu catalog, vector và manifest có checksum; Spark dùng Parquet cho phân tích. Data và model được loại khỏi Git.'
])

def table(index, rows):
    tbl=tables[index]; old=tbl.findall('w:tr',NS); prototype=deepcopy(old[1] if len(old)>1 else old[0])
    while len(old)<len(rows):
        r=deepcopy(prototype);tbl.append(r);old.append(r)
    for r in old[len(rows):]: tbl.remove(r)
    for r,values in zip(old,rows):
        cells=r.findall('w:tc',NS); assert len(cells)==len(values),(index,len(cells),values)
        for cell,value in zip(cells,values):
            ps=cell.findall('w:p',NS)
            put(ps[0],str(value))
            for p in ps[1:]: put(p,'')

table(0,[['STT','Tình huống','Cách xử lý'],[1,'Người dùng mới','Chọn genre; gợi ý từ popularity snapshot.'],[2,'Người dùng thích bài','Cập nhật profile và loại bài đã thích khỏi đề xuất.'],[3,'Bài không phù hợp','Ghi dislike và loại bài khỏi gợi ý.'],[4,'Bỏ thích','Cập nhật trạng thái unlike; giữ event lịch sử.'],[5,'Tạo playlist','Tạo playlist gắn với tài khoản hiện tại.'],[6,'Thêm trùng bài','Khóa ghép giữ một bản ghi duy nhất.'],[7,'Retry sự kiện','Cùng event_id và payload trả duplicate.'],[8,'Truy cập chéo tài khoản','Từ chối truy cập playlist không thuộc sở hữu.']])
table(1,[['Mã','Chức năng','Yêu cầu'],['F01','Tài khoản','Đăng ký, đăng nhập, token có thời hạn.'],['F02','Sở thích','Chọn tối đa 20 genre hợp lệ.'],['F03','Tìm kiếm','Tìm theo tên bài hoặc nghệ sĩ.'],['F04','Gợi ý','Tạo Top-K từ profile; có fallback cho người mới.'],['F05','Phản hồi','Like, dislike, unlike; ghi event nguyên tử.'],['F06','Playlist','Tạo danh sách và thêm bài theo quyền sở hữu.'],['F07','Hoạt động','Thống kê tương tác của chính tài khoản.'],['F08','Spark ETL','Chuẩn hóa và lưu Bronze, Silver, Gold.'],['F09','Huấn luyện','Notebook GPU xuất model và metadata vào Drive.'],['F10','Phân tích event','Tách real/synthetic và khử trùng event_id.']])
entities=[('Feedback','Trạng thái phản hồi hiện tại.'),('Users','Tài khoản và thể loại quan tâm.'),('Playlists','Playlist và người sở hữu.'),('Events','Lịch sử tương tác và outbox.'),('Tracks','Danh mục bài hát ngoài database ứng dụng.'),('Playlist_Items','Các bài được lưu vào playlist.'),('Track_Genres','Quan hệ nhiều thể loại trong Spark Silver.')]
table(2,[['STT','Thực thể','Ý nghĩa']]+[[i+1,*r] for i,r in enumerate(entities)])
header=['Thuộc tính','Kiểu dữ liệu','Ràng buộc','Mô tả']
schemas=[
[['user_id','STRING','PK, FK','Mã người dùng.'],['track_id','STRING','PK','Mã bài trong catalog.'],['state','STRING','NOT NULL','like, dislike, unlike.']],
[['id','STRING','PK','UUID tài khoản.'],['username','VARCHAR(64)','UNIQUE, NOT NULL','Tên đăng nhập.'],['password','STRING','NOT NULL','Salt và mã băm.'],['genres','STRING','NOT NULL','Danh sách JSON, mặc định [].']],
[['id','STRING','PK','UUID playlist.'],['user_id','STRING','FK, NOT NULL','Chủ sở hữu.'],['name','VARCHAR(100)','NOT NULL','Tên playlist.']],
[['event_id','VARCHAR(36)','PK','UUID sự kiện.'],['user_id','STRING','FK, NOT NULL','Tài khoản thực hiện.'],['track_id','STRING','NOT NULL','Bài trong catalog.'],['event_type','STRING','NOT NULL','Loại tương tác.'],['event_time','TIMESTAMP','NOT NULL','Thời gian UTC phía server.'],['source','STRING','NOT NULL','real ở API; synthetic ở mô phỏng.'],['published','BOOLEAN','NOT NULL','Đã gửi Kafka, mặc định false.']],
[['track_id','STRING','Khóa logic','Mã Spotify duy nhất.'],['track_name','STRING','Không thiếu','Tên bài hát.'],['artists','STRING','Không thiếu','Nghệ sĩ biểu diễn.'],['album_name','STRING','Metadata','Tên album khi có.'],['popularity','NUMBER','0 đến 100','Popularity snapshot.'],['duration_ms','NUMBER','Lớn hơn 0','Độ dài bản ghi.'],['audio_features','Nhóm số thực','Kiểm tra miền','Các đặc trưng âm nhạc đã mô tả.'],['genres','STRING','Tập thể loại','Các genre, phân cách bằng |.']],
[['playlist_id','STRING','PK, FK','Playlist sở hữu bài.'],['track_id','STRING','PK','Bài thuộc catalog.']],
[['track_id','STRING','Khóa ghép logic','Mã bài hát.'],['track_genre','STRING','Khóa ghép logic','Một thể loại của bài.']]
]
for i,s in enumerate(schemas): table(i+3,[header]+s)
table(10,[['STT','Thực thể nguồn','Quan hệ','Thực thể đích','Ý nghĩa'],[1,'Users','1 - N','Feedback','Một người có phản hồi trên nhiều bài.'],[2,'Users','1 - N','Events','Một người phát sinh nhiều sự kiện.'],[3,'Users','1 - N','Playlists','Một người sở hữu nhiều playlist.'],[4,'Playlists','1 - N','Playlist_Items','Một playlist chứa nhiều bài.'],[5,'Tracks','1 - N','Track_Genres','Một bài có nhiều genre.'],[6,'Tracks','1 - N','Feedback / Events','Tham chiếu catalog được kiểm tra ở API.']])
table(11,[['[1]','Maharshi Pandya. Spotify Tracks Dataset. Kaggle. https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset'],['[2]','Apache Software Foundation. Apache Spark 3.5.3 Documentation. https://spark.apache.org/docs/3.5.3/'],['[3]','PyTorch. Documentation. https://docs.pytorch.org/docs/stable/'],['[4]','Apache Software Foundation. Structured Streaming Programming Guide. https://spark.apache.org/docs/3.5.3/structured-streaming-programming-guide.html'],['[5]','Maharshi Pandya. Spotify Tracks Dataset mirror. https://huggingface.co/datasets/maharshipandya/spotify-tracks-dataset']])

# Keep the TOC field and its original style; mark cached page numbers for refresh in Word.
settings=E.fromstring(parts['word/settings.xml'])
update=settings.find('w:updateFields',NS)
if update is None: update=E.SubElement(settings,W+'updateFields')
update.set(W+'val','true')
for begin in doc.findall('.//w:fldChar',NS):
    if begin.get(W+'fldCharType')=='begin': begin.set(W+'dirty','true')
modified={'word/document.xml':E.tostring(doc,encoding='UTF-8',xml_declaration=True,standalone=True),
          'word/settings.xml':E.tostring(settings,encoding='UTF-8',xml_declaration=True,standalone=True)}
temp=TARGET.with_suffix('.working.docx')
with ZipFile(temp,'w',ZIP_DEFLATED) as out:
    for name,content in parts.items(): out.writestr(name,modified.get(name,content))
with ZipFile(temp) as out:
    assert all(out.read(n)==v for n,v in parts.items() if n not in modified)
    xml=out.read('word/document.xml').decode()
    for forbidden in ['Bounding Box','Detection_Events','camera_id','YOLO','khói','đám cháy']:
        assert forbidden not in ''.join(doc.xpath('//w:t/text()',namespaces=NS)),forbidden
assert hashlib.sha256(BACKUP.read_bytes()).hexdigest()==hashlib.sha256(TARGET.read_bytes()).hexdigest(), 'Original changed concurrently'
temp.replace(TARGET)
inventory={n:{'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v),'preserved':n not in modified} for n,v in parts.items()}
(QA/'package-audit.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
(QA/'artifact.md').write_text('Reference: original-template.docx\nOriginal SHA256: '+hashlib.sha256(BACKUP.read_bytes()).hexdigest()+'\nTwo chapters, original cover and identity retained. Original paragraph/run properties reused. Table cell and grid styles retained; rows resized to actual schema. All ZIP parts except document.xml and settings.xml are byte-identical. Section properties remain unchanged. TOC marked for refresh. Rendering unavailable: bundled LibreOffice is absent.\n',encoding='utf-8')
print('UPDATED',TARGET)
print('BACKUP',BACKUP)
print('Preserved package parts:',len(parts)-len(modified))
