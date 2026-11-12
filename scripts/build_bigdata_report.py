"""Overwrite the existing report by cloning original OOXML paragraphs, rows and captions.

Uses the user's cover and original template styles/numbering; never creates replacement styles.
Run after the Spark acceptance checks and publication figure generation.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import json
import re
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.shared import Inches
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'HoangCongHoan_10123137_12423TN.docx'
QA=ROOT/'reports/template-qa';QA.mkdir(exist_ok=True,parents=True)
RESULTS=ROOT/'reports/bigdata'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'

def parts(path):
    with ZipFile(path) as z:return {n:z.read(n) for n in z.namelist()}

def value(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))

def clean_ids(element):
    for n in list(element.iter()):
        for a in list(n.attrib):
            if E.QName(a).localname in {'paraId','textId'}:del n.attrib[a]
        if E.QName(n).localname in {'bookmarkStart','bookmarkEnd','commentRangeStart','commentRangeEnd','commentReference'}:
            if n.getparent() is not None:n.getparent().remove(n)
    return element

def clone_text(template,text):
    p=clean_ids(deepcopy(template));pp=p.find('w:pPr',NS);run=p.find('.//w:r',NS)
    rp=deepcopy(run.find('w:rPr',NS)) if run is not None and run.find('w:rPr',NS) is not None else None
    for child in list(p):
        if child is not pp:p.remove(child)
    r=E.SubElement(p,W+'r')
    if rp is not None:r.append(rp)
    t=E.SubElement(r,W+'t');t.text=re.sub(r'\*\*|`','',text)
    t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return p

def prop(p,name,val):
    pp=p.find('w:pPr',NS)
    if pp is None:pp=E.SubElement(p,W+'pPr')
    item=pp.find('w:'+name,NS)
    if item is None:item=E.SubElement(pp,W+name)
    item.set(W+'val',str(val))

def sections(markdown):
    chunks=re.split(r'(?m)^## ',markdown)
    return {chunk.split('\n',1)[0]:chunk.split('\n',1)[1] for chunk in chunks[1:]}

def guide_section(secs,n):
    text=next(v for k,v in secs.items() if k.startswith(str(n)+'.'))
    text=re.sub(r'```mermaid.*?```','Luồng xử lý: CSV → driver → master và hai worker → Parquet → bảng Gold → dashboard. Event log được lưu riêng để History Server tái hiện thực thi.',text,flags=re.S)
    return re.sub(r'(?m)^### \d+\.\d+\.\s*','## ',text).strip()

def main():
    d=json.loads((RESULTS/'summary.json').read_text(encoding='utf-8'));run=d['run']
    assert 'metadata_conflicts' in run and d['model_selection']['max_iter']==50
    guide=sections((ROOT/'docs/BIGDATA_DEFENSE_GUIDE.md').read_text(encoding='utf-8'))
    evidence=sections((RESULTS/'BAO_CAO_BIGDATA.md').read_text(encoding='utf-8'))
    result_text=[]
    for name,text in evidence.items():
        if name[0].isdigit() and 2<=int(name.split('.')[0])<=7:
            result_text.append('## '+re.sub(r'^\d+\.\s*','',name)+'\n\n'+re.sub(r'(?m)^### \d+\.\d+\.\s*','### ',text.strip()))
            if name.startswith('4.'):result_text.append('@figure paper-genres.png|Popularity trung bình của các thể loại trong mẫu')
            if name.startswith('5.'):result_text.append('@figure paper-correlation.png|Ma trận tương quan Pearson của các đặc trưng')
            if name.startswith('6.'):result_text.append('@figure paper-clusters.png|Biểu diễn hai chiều của 500 bài minh họa')
            if name.startswith('7.'):result_text.append('@figure paper-benchmark.png|Trung vị và khoảng min–max của thời gian thực nghiệm')
    text='\n\n'.join([
        '# TỔNG QUAN ĐỀ TÀI',guide_section(guide,1),
        '## Câu hỏi nghiên cứu',
        'Đề tài đặt ra các câu hỏi: dữ liệu thiếu, trùng và mâu thuẫn metadata xuất hiện ở mức nào; '
        'đặc trưng danh mục khác nhau giữa các thể loại ra sao; các đặc trưng số có quan hệ tuyến tính nào; '
        'cấu hình phân cụm nào có silhouette validation phù hợp trong tập ứng viên; và thay đổi số '
        'partition tác động thế nào đến thời gian một phép tổng hợp khi giữ nguyên dữ liệu đầu vào.',
        '## Phương pháp và tổ chức báo cáo',
        'Bài làm sử dụng thực nghiệm có thể tái hiện: xác định hợp đồng dữ liệu, triển khai xử lý bằng '
        'Spark, lưu dữ liệu trung gian, đánh giá mô hình trên các tập tách biệt và kiểm tra kết quả bằng '
        'các bất biến. Chương 2 trình bày cơ sở và phương pháp; chương 3 thiết kế xử lý; chương 4 triển khai '
        'và kiểm thử; chương 5 phân tích kết quả thực đo. Kết luận chỉ áp dụng trong phạm vi dữ liệu và '
        'hạ tầng đã công bố.',
        '# CƠ SỞ LÝ THUYẾT VÀ PHƯƠNG PHÁP PHÂN TÍCH',
        '## Xử lý dữ liệu lớn và tính phù hợp của công cụ',
        'Một hệ thống xử lý dữ liệu lớn cần phân chia công việc, quản lý tài nguyên và kiểm soát chi phí '
        'truyền dữ liệu. Việc sử dụng công cụ phân tán không tự biến một tập dữ liệu nhỏ thành dữ liệu lớn. '
        'Trong bài tập, Spark được dùng để thực hành quy trình phân tán và đo các đặc điểm thực thi; '
        'không đưa ra khẳng định rằng Spark luôn nhanh hơn công cụ xử lý trên một tiến trình [2][4].',
        'Chi phí của một job bao gồm lập lịch task, đọc dữ liệu, tính toán, shuffle và ghi kết quả. '
        'Với dữ liệu nhỏ, các chi phí cố định có thể chiếm tỷ trọng lớn. Vì vậy, số core hoặc số partition '
        'tăng không bảo đảm thời gian giảm. Phân tích hiệu năng cần giữ phép tính và đầu vào tương đương, '
        'ghi cấu hình và trình bày biến thiên giữa các lần đo [5].',
        '## Mô hình thực thi Spark',
        'Spark biểu diễn quá trình tính bằng các quan hệ phụ thuộc. Driver lập kế hoạch; một job được '
        'chia thành các stage, và task xử lý các partition trong stage. Những bước cần trao đổi dữ liệu '
        'tạo ranh giới shuffle. Tính phân tán phải được kiểm chứng bằng executor, task và stage thực '
        'chạy, không chỉ bằng số container đang hoạt động [4].',
        guide_section(guide,4),guide_section(guide,5),
        '# KHẢO SÁT DỮ LIỆU VÀ THIẾT KẾ HỆ THỐNG',
        '## Nguồn dữ liệu và đơn vị phân tích',
        'Nguồn dữ liệu là Spotify Tracks Dataset do Maharshi Pandya công bố trên Kaggle [1]. '
        'Đơn vị phân tích chính là mã bài hát track_id. Thể loại có quan hệ nhiều–nhiều với bài hát. '
        'Không coi một dòng CSV là một người dùng hoặc một lượt nghe. Dữ liệu snapshot không cung cấp '
        'chuỗi sự kiện để phân tích biến động theo thời gian.',
        '| Nhóm dữ liệu | Thuộc tính | Cách sử dụng |\n|---|---|---|\n'
        '| Định danh | track_id | Khóa khử trùng và chia tập |\n'
        '| Mô tả | track_name, artists, album_name | Hiển thị và tổng hợp nghệ sĩ |\n'
        '| Phân loại | track_genre | Bảng quan hệ bài–thể loại |\n'
        '| Tỷ lệ âm nhạc | danceability, energy, speechiness, acousticness, instrumentalness, liveness, valence | Kiểm tra miền 0–1 và tạo vector |\n'
        '| Đại lượng khác | loudness, tempo, duration_ms | Đặc trưng số cần chuẩn hóa trước phân cụm |\n'
        '| Phổ biến | popularity | Điểm 0–100 tại snapshot, không phải lượt nghe |',
        guide_section(guide,2),guide_section(guide,3),
        '## Chính sách xử lý metadata mâu thuẫn',
        'Đối với một mã bài có nhiều bản ghi, pipeline ưu tiên popularity cao hơn, sau đó xét genre '
        'và hash nội dung để phá hòa một cách xác định. Quy tắc này bảo đảm khả năng tái hiện nhưng '
        'không chứng minh bản ghi được chọn mới nhất. Các mã có nhiều popularity hoặc bộ feature '
        'được lưu riêng; so sánh trung bình khi lấy min và max giúp định lượng độ nhạy của thống kê.',
        '# TRIỂN KHAI VÀ KIỂM THỬ',
        '## Phân chia mã nguồn',
        '| Thành phần | Tệp chính | Trách nhiệm |\n|---|---|---|\n'
        '| Điều phối | bigdata/analyze.py | Đọc nguồn, ETL, SQL, lưu kết quả |\n'
        '| Hợp đồng dữ liệu | bigdata/quality.py | Phát hiện lỗi, quarantine, khử trùng |\n'
        '| Thực nghiệm | bigdata/experiments.py | Chọn mô hình, test, benchmark |\n'
        '| Đóng gói | compose.bigdata.yaml | Master, worker, driver, dashboard, history |\n'
        '| Kiểm chứng | scripts/verify_bigdata.py | Đối soát số lượng, model và checksum |',
        '## Quy trình vận hành',
        'Script run-bigdata.ps1 build image, khởi động dịch vụ, chờ đủ hai worker ALIVE, chạy kiểm thử '
        'hợp đồng dữ liệu và submit job. Sau khi job thành công, chương trình kiểm tra kết quả trước '
        'khi thông báo hoàn tất. Chế độ DemoOnly mở lại dịch vụ với kết quả đã có; không tải dữ liệu '
        'hoặc huấn luyện lại trong lúc thuyết trình. Các bước thao tác chi tiết nằm trong BIGDATA.md.',
        'Dữ liệu nguồn được nhận diện bằng SHA256. run.json lưu application ID, phiên bản Spark, Java, '
        'Python, cấu hình tài nguyên và hash các mô-đun Python. Event log cho phép xem lại Jobs, Stages '
        'và SQL qua History Server. Các bảng tổng hợp được ghi CSV/JSON để đối chiếu với dashboard.',
        guide_section(guide,6),
        '## Kiểm thử hồi quy cho hợp đồng dữ liệu',
        'Bốn kiểm thử Spark đã chạy trong container: bảo toàn quan hệ thể loại khi gộp mã bài; '
        'cách ly đầy đủ dòng có số lỗi, NaN, vô cực hoặc định danh rỗng; lựa chọn metadata không phụ '
        'thuộc số partition khi khóa sắp xếp chính bằng nhau; và từ chối dữ liệu thiếu cột bắt buộc. '
        'Fixture kiểm thử chỉ dùng kiểm chứng quy tắc, không được đưa vào kết quả nghiên cứu.',
        '# KẾT QUẢ THỰC NGHIỆM VÀ ĐÁNH GIÁ','\n\n'.join(result_text),
        (RESULTS/'PHAN_TICH_THUC_THI.md').read_text(encoding='utf-8').strip(),
        '# KẾT LUẬN',
        f'Bài tập đã triển khai và chạy quy trình phân tích trên hai executor Spark trong Docker. '
        f'Từ {run["raw_rows"]:,} dòng đầu vào, hệ thống tạo danh mục {run["unique_tracks"]:,} bài hợp lệ, '
        f'bảng thống kê và mô hình phân cụm k={run["k"]} theo quy trình lựa chọn đã công bố. '
        f'Thực nghiệm tải sử dụng {run["benchmark_rows"]:,} dòng được tạo bằng nhân bản cho riêng benchmark. '
        'Các kết quả được đối soát và gắn với một application ID để kiểm tra lại.',
        'Đóng góp của bài làm là quy trình có thể tái hiện và giải thích được các quyết định xử lý. '
        'Giới hạn gồm snapshot không có hành vi người dùng, một host dùng chung tài nguyên, tập ứng '
        'viên mô hình hữu hạn và số lần đo hiệu năng còn nhỏ. Hướng phát triển là thu thập sự kiện '
        'có timestamp, thử nghiệm nhiều host với storage phù hợp và đánh giá độ ổn định qua nhiều '
        'seed. Cá nhân hóa và GPU được xem xét khi có dữ liệu tương tác phù hợp.',
        '# TÀI LIỆU THAM KHẢO',
        '[1] Maharshi Pandya. Spotify Tracks Dataset. Kaggle. https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset',
        '[2] Apache Spark 4.0.1. Spark SQL Guide. https://spark.apache.org/docs/4.0.1/sql-programming-guide.html',
        '[3] Apache Spark 4.0.1. Clustering. https://spark.apache.org/docs/4.0.1/ml-clustering.html',
        '[4] Apache Spark 4.0.1. Standalone Mode. https://spark.apache.org/docs/4.0.1/spark-standalone.html',
        '[5] Apache Spark 4.0.1. SQL Performance Tuning. https://spark.apache.org/docs/4.0.1/sql-performance-tuning.html',
    ])
    (RESULTS/'BAO_CAO_HOC_PHAN.md').write_text(text+'\n',encoding='utf-8')
    current=parts(TARGET);original=parts(QA/'original-template.docx')
    digest=sha256(TARGET.read_bytes()).hexdigest()
    backup=QA/f'before-bigdata-{datetime.now():%Y%m%d-%H%M%S}.docx'
    backup.write_bytes(TARGET.read_bytes())
    original_body=E.fromstring(original['word/document.xml']).find('w:body',NS)
    templates=original_body.findall('w:p',NS)
    table_template=original_body.find('w:tbl',NS)
    doc=E.fromstring(current['word/document.xml']);body=doc.find('w:body',NS)
    start=next(p for p in body if p.tag==W+'p' and value(p)=='TỔNG QUAN ĐỀ TÀI')
    offset=list(body).index(start);section=deepcopy(body.find('w:sectPr',NS))
    front=body.findall('w:p',NS)
    for index,new in {7:'BÀI TẬP LỚN',10:'PHÂN TÍCH DỮ LIỆU ÂM NHẠC SPOTIFY BẰNG APACHE SPARK'}.items():
        body.replace(front[index],clone_text(front[index],new))
    if not value(front[8]).strip():body.replace(front[8],clone_text(front[7],'MÔN XỬ LÝ DỮ LIỆU LỚN'))
    for p in list(body)[:offset]:
        if p.tag==W+'p' and 'Xây dựng hệ thống gợi ý âm nhạc cá nhân hóa quy mô lớn và phân tích xu hướng người dùng' in value(p):
            body.replace(p,clone_text(p,value(p).replace('Xây dựng hệ thống gợi ý âm nhạc cá nhân hóa quy mô lớn và phân tích xu hướng người dùng','Phân tích dữ liệu âm nhạc Spotify bằng Apache Spark').replace('đồ án','bài tập lớn')))
    for c in list(body)[offset:]:body.remove(c)
    rels=E.fromstring(current['word/_rels/document.xml.rels']);extra={}
    for rel in list(rels):
        if rel.get('Id','').startswith('rIdBigDataFigure'):rels.remove(rel)
    chapter=sub=minor=table_no=figure_no=0;headings=[]

    def make_table(rows):
        tbl=clean_ids(deepcopy(table_template));old=tbl.findall('w:tr',NS)
        head,detail=deepcopy(old[0]),deepcopy(old[1])
        for row in old:tbl.remove(row)
        grid=tbl.find('w:tblGrid',NS)
        for node in list(grid):grid.remove(node)
        width=9000//len(rows[0])
        for _ in rows[0]:E.SubElement(grid,W+'gridCol').set(W+'w',str(width))
        for i,items in enumerate(rows):
            row=deepcopy(head if i==0 else detail);cells=row.findall('w:tc',NS)
            for c in cells:row.remove(c)
            trpr=row.find('w:trPr',NS)
            if trpr is not None:
                for h in trpr.findall('w:trHeight',NS):trpr.remove(h)
            for j,item in enumerate(items):
                cell=deepcopy(cells[min(j,len(cells)-1)])
                tcpr=cell.find('w:tcPr',NS)
                if tcpr is not None:
                    for tag in ['gridSpan','vMerge']: 
                        for n in tcpr.findall('w:'+tag,NS):tcpr.remove(n)
                    cw=tcpr.find('w:tcW',NS)
                    if cw is not None:cw.set(W+'w',str(width));cw.set(W+'type','dxa')
                ps=cell.findall('w:p',NS);fresh=clone_text(ps[0],item)
                for p in ps:cell.remove(p)
                cell.append(fresh);row.append(cell)
            tbl.append(row)
        return tbl

    for block in text.split('\n\n'):
        block=block.strip()
        if not block:continue
        if block.startswith('#'):
            level=len(block)-len(block.lstrip('#'));title=block[level:].strip()
            unnumbered=title in {'KẾT LUẬN','TÀI LIỆU THAM KHẢO'}
            p=clone_text(templates[276 if unnumbered else {1:68,2:69,3:89}[level]],title)
            if level==1:
                if not unnumbered:chapter+=1
                sub=minor=table_no=figure_no=0;prop(p,'pageBreakBefore',1)
            elif level==2:sub+=1;minor=0
            else:minor+=1
            label=title if unnumbered else (f'CHƯƠNG {chapter}: {title}' if level==1 else f'{chapter}.{sub}'+(f'.{minor}' if level==3 else '')+' '+title)
            bookmark=f'BigDataSection{len(headings)+1}';bid=str(30000+len(headings))
            b=E.Element(W+'bookmarkStart');b.set(W+'id',bid);b.set(W+'name',bookmark);p.insert(1,b)
            E.SubElement(p,W+'bookmarkEnd').set(W+'id',bid)
            headings.append((level,label,bookmark));body.append(p)
        elif block.startswith('|'):
            rows=[[c.strip() for c in line.strip().strip('|').split('|')] for line in block.splitlines() if not re.match(r'^\|[\s:|-]+\|$',line)]
            caption=re.sub(r'^(CHƯƠNG \d+: |\d+(?:\.\d+)* )','',headings[-1][1])
            table_no+=1;body.append(clone_text(templates[187],f'Bảng {chapter}.{table_no}: {caption}'))
            body.append(make_table(rows))
        elif block.startswith('@figure '):
            name,caption=block[len('@figure '):].split('|');figure_no+=1
            path=RESULTS/'figures'/name
            helper=Document();shape=helper.add_picture(str(path),width=Inches(5.8))
            inline=deepcopy(shape._inline);rid=f'rIdBigDataFigure{chapter}_{figure_no}'
            for node in inline.iter():
                if E.QName(node).localname=='blip':node.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed',rid)
                if E.QName(node).localname=='docPr':node.set('id',str(50000+chapter*100+figure_no))
            p=clone_text(templates[187],'');prop(p,'keepNext',1)
            for r in p.findall('w:r',NS):p.remove(r)
            E.SubElement(E.SubElement(p,W+'r'),W+'drawing').append(inline);body.append(p)
            body.append(clone_text(templates[187],f'Hình {chapter}.{figure_no}: {caption}'))
            target='media/bigdata-'+name;extra['word/'+target]=path.read_bytes()
            rel=E.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
            rel.set('Id',rid);rel.set('Type','http://schemas.openxmlformats.org/officeDocument/2006/relationships/image');rel.set('Target',target)
        else:
            if block.startswith('- '):
                for line in block.splitlines():body.append(clone_text(templates[70],line.removeprefix('- ')))
            else:body.append(clone_text(templates[70],' '.join(block.splitlines())))
    body.append(section)
    toc=body.find('w:sdt',NS).find('w:sdtContent',NS)
    toc_templates={}
    for p in toc.findall('w:p',NS):
        style=p.find('w:pPr/w:pStyle',NS)
        if style is not None:toc_templates.setdefault(style.get(W+'val'),p)
    for c in list(toc):toc.remove(c)
    p=E.SubElement(toc,W+'p')
    E.SubElement(E.SubElement(p,W+'r'),W+'fldChar').set(W+'fldCharType','begin')
    E.SubElement(E.SubElement(p,W+'r'),W+'instrText').text=' TOC \\o "1-3" \\h \\z \\u '
    E.SubElement(E.SubElement(p,W+'r'),W+'fldChar').set(W+'fldCharType','separate')
    for level,label,bookmark in headings:
        template=toc_templates.get('TOC'+str(level),next(iter(toc_templates.values())))
        p=clone_text(template,label);r=p.find('w:r',NS);p.remove(r)
        link=E.SubElement(p,W+'hyperlink');link.set(W+'anchor',bookmark);link.append(r);toc.append(p)
    p=E.SubElement(toc,W+'p');E.SubElement(E.SubElement(p,W+'r'),W+'fldChar').set(W+'fldCharType','end')
    settings=E.fromstring(current['word/settings.xml']);u=settings.find('w:updateFields',NS)
    if u is not None:u.set(W+'val','false')
    ct=E.fromstring(current['[Content_Types].xml'])
    if not any(n.get('Extension')=='png' for n in ct):
        n=E.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Default');n.set('Extension','png');n.set('ContentType','image/png')
    changed={key:E.tostring(node,encoding='UTF-8',xml_declaration=True,standalone=True) for key,node in {
        'word/document.xml':doc,'word/settings.xml':settings,'word/_rels/document.xml.rels':rels,'[Content_Types].xml':ct}.items()}
    for name,data in current.items():
        if name.startswith('word/header') and name.endswith('.xml'):
            header=E.fromstring(data)
            for p in header.findall('.//w:p',NS):
                if 'Xây dựng hệ thống' in value(p):
                    nodes=p.findall('.//w:t',NS)
                    for i,node in enumerate(nodes):
                        node.text='Phân tích dữ liệu âm nhạc Spotify bằng Apache Spark' if i==0 else ''
            changed[name]=E.tostring(header,encoding='UTF-8',xml_declaration=True,standalone=True)
    assert chapter==5
    reason=text.split('## Lý do chọn đề tài')[1].split('## Mục tiêu')[0]
    assert not any(x in reason.lower() for x in ['spark','dataset','colab','114.000'])
    assert sha256(TARGET.read_bytes()).hexdigest()==digest,'Target changed concurrently'
    temp=TARGET.with_suffix('.bigdata-tmp.docx')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for name,data in current.items():z.writestr(name,extra.get(name,changed.get(name,data)))
        for name,data in extra.items():
            if name not in current:z.writestr(name,data)
    with ZipFile(temp) as z:
        for name in ['word/styles.xml','word/numbering.xml']:
            assert z.read(name)==current[name],name+' changed'
        for name in z.namelist():
            if name.endswith('.xml'):E.fromstring(z.read(name))
    temp.replace(TARGET)
    (QA/'bigdata-audit.json').write_text(json.dumps({'backup':str(backup),'original_sha256':digest,
        'application_id':run['application_id'],'chapters':chapter,'headings':len(headings),
        'styles_and_numbering_unchanged':True,'tables':len(body.findall('w:tbl',NS)),
        'figures_added':len(extra),'render_status':'pending Word rendering'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Updated original:',TARGET,'headings:',len(headings),'tables:',len(body.findall('w:tbl',NS)))

if __name__=='__main__':main()
