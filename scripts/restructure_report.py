"""Clone original Word components, rebuild the report body, and overwrite the requested file."""
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
from lxml import etree as E

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'HoangCongHoan_10123137_12423TN.docx'
QA=ROOT/'reports/template-qa'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W='{'+NS['w']+'}'
def read(path):
    with ZipFile(path) as z: return {n:z.read(n) for n in z.namelist()}
current=read(TARGET)
original=read(QA/'original-template.docx')
digest=hashlib.sha256(TARGET.read_bytes()).hexdigest()
backup=QA/('before-restructure-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.docx')
backup.write_bytes(TARGET.read_bytes())
source=E.fromstring(original['word/document.xml'])
sp=source.find('w:body',NS).findall('w:p',NS)
doc=E.fromstring(current['word/document.xml'])
body=doc.find('w:body',NS)
existing_tables=body.findall('w:tbl',NS)
def value(p): return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
def clean_ids(element):
    for n in list(element.iter()):
        for attr in list(n.attrib):
            if E.QName(attr).localname in {'paraId','textId'}: del n.attrib[attr]
        if E.QName(n).localname in {'bookmarkStart','bookmarkEnd','commentRangeStart','commentRangeEnd','commentReference'}:
            n.getparent().remove(n)
    return element
def clone_text(template,text):
    p=clean_ids(deepcopy(template))
    prop=p.find('w:pPr',NS)
    first=p.find('.//w:r',NS)
    rp=deepcopy(first.find('w:rPr',NS)) if first is not None and first.find('w:rPr',NS) is not None else None
    for child in list(p):
        if child is not prop: p.remove(child)
    r=E.SubElement(p,W+'r')
    if rp is not None:r.append(rp)
    t=E.SubElement(r,W+'t');t.text=text;t.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    return p
def prop(p,name,val):
    pp=p.find('w:pPr',NS)
    if pp is None:pp=E.SubElement(p,W+'pPr')
    node=pp.find('w:'+name,NS)
    if node is None:node=E.SubElement(pp,W+name)
    node.set(W+'val',str(val))

# Retain cover, acknowledgements, TOC control, headers, and section geometry.
start=next(c for c in body if c.tag==W+'p' and value(c)=='TỔNG QUAN ĐỀ TÀI')
offset=list(body).index(start)
section=deepcopy(body.find('w:sectPr',NS))
for c in list(body)[offset:]:body.remove(c)

custom={
'features':('Các nhóm thuộc tính của danh mục',[
['Nhóm','Thuộc tính tiêu biểu','Vai trò'],
['Định danh','track_id','Liên kết catalog, feedback và event.'],
['Mô tả','track_name, artists, album_name','Tìm kiếm và hiển thị.'],
['Thể loại','track_genre, genres','Khởi tạo sở thích và phân tích nhóm.'],
['Đặc trưng âm nhạc','energy, valence, tempo và các biến âm thanh','Tạo vector và phân cụm.'],
['Độ dài','duration_ms','Đặc trưng số; kiểm tra giá trị dương.'],
['Phổ biến','popularity','Fallback từ snapshot, không phải nhãn user.']]),
'usecases':('Đặc tả các luồng sử dụng chính',[
['Luồng','Điều kiện và thao tác','Kết quả hoặc ngoại lệ'],
['Nhận gợi ý','Đăng nhập; mở trang dành cho bạn.','Top-K đã lọc; fallback khi chưa có like.'],
['Thích hoặc ẩn bài','Track hợp lệ; gửi event_id mới.','Feedback và event được ghi cùng transaction.'],
['Gửi lại sự kiện','Giữ nguyên event_id và payload.','Không tăng đếm; khác payload trả xung đột.'],
['Thêm vào playlist','Playlist thuộc tài khoản; track có trong catalog.','Thêm một lần; sai chủ sở hữu bị từ chối.'],
['Xem hoạt động','Token hợp lệ.','Chỉ trả thống kê của chính tài khoản.']]),
'architecture':('Phân chia thành phần và trách nhiệm',[
['Thành phần','Trách nhiệm','Dữ liệu trao đổi'],
['Giao diện','Hiển thị và tiếp nhận thao tác.','Request và phản hồi JSON.'],
['API','Xác thực, nghiệp vụ, quyền sở hữu.','Tài khoản, feedback, playlist, event.'],
['Gợi ý','Profile, truy hồi và lọc.','Catalog, vector, trạng thái sở thích.'],
['Huấn luyện','Tạo biểu diễn và xuất artifact.','Model, scaler, embeddings, metrics.'],
['Spark','ETL, thống kê và phân cụm.','CSV, Parquet và kết quả Gold.'],
['Thu thập event','Outbox và truyền Kafka.','Event có ID và thời gian UTC.']]),
'tests':('Các nhóm kiểm thử tự động đã thực hiện',[
['Nhóm','Nội dung kiểm tra','Kết quả'],
['Dữ liệu','Khử trùng track và giữ các genre.','Đạt trên fixture.'],
['Artifact','Checksum, lọc like/dislike và vector hữu hạn.','Đạt trên fixture.'],
['API','Auth, event trùng và quyền playlist.','Đạt với database kiểm thử.'],
['Train và nạp','Hai epoch CPU, export và inference.','Đạt; chưa phải GPU đầy đủ.'],
['Ranking','Temporal cutoff, loại synthetic và bài đã thấy.','Đạt trên tình huống kiểm thử.']])
}
table_names={0:'Các tình huống nghiệp vụ',1:'Các yêu cầu chức năng',2:'Các thực thể và miền lưu trữ',3:'Cấu trúc Feedback',4:'Cấu trúc Users',5:'Cấu trúc Playlists',6:'Cấu trúc Events',7:'Thuộc tính chính của catalog Tracks',8:'Cấu trúc Playlist_Items',9:'Cấu trúc Track_Genres',10:'Các quan hệ giữa thực thể'}
def make_table(rows):
    tbl=clean_ids(deepcopy(existing_tables[0]))
    old=tbl.findall('w:tr',NS); template=deepcopy(old[1])
    for r in old[1:]:tbl.remove(r)
    for _ in rows[1:]:tbl.append(deepcopy(template))
    for r,values in zip(tbl.findall('w:tr',NS),rows):
        for cell,txt in zip(r.findall('w:tc',NS),values):
            paras=cell.findall('w:p',NS)
            new=clone_text(paras[0],str(txt))
            cell.insert(list(cell).index(paras[0]),new)
            for p in paras:cell.remove(p)
    return tbl
chap=0;sub=0;minor=0;table_no=0;headings=[];clones=[]
for item in (ROOT/'reports/report-restructured.md').read_text(encoding='utf-8').split('\n\n'):
    # Heading directives can follow each other with a single newline.
    lines=item.strip().splitlines()
    while lines and (lines[0].startswith('#') or lines[0].startswith('@')):
        line=lines.pop(0)
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#'));title=line[level:].strip()
            unnumbered=title in {'KẾT LUẬN','TÀI LIỆU THAM KHẢO'}
            template=sp[276] if unnumbered else sp[{1:68,2:69,3:89}[level]]
            p=clone_text(template,title)
            if level==1:
                if not unnumbered:chap+=1
                sub=minor=table_no=0
                prop(p,'pageBreakBefore',1)
            elif level==2:sub+=1;minor=0
            else:minor+=1
            label=title if unnumbered else (f'CHƯƠNG {chap}: {title}' if level==1 else f'{chap}.{sub}'+(f'.{minor}' if level==3 else '')+' '+title)
            bookmark=f'MusicSection{len(headings)+1}'
            bid=str(20000+len(headings))
            b=E.Element(W+'bookmarkStart');b.set(W+'id',bid);b.set(W+'name',bookmark);p.insert(1,b)
            b=E.SubElement(p,W+'bookmarkEnd');b.set(W+'id',bid)
            headings.append((level,label,bookmark))
            body.append(p);clones.append((title,level))
        else:
            if line.startswith('@reuse'):
                index=int(line.split()[1]);tbl=clean_ids(deepcopy(existing_tables[index]));caption=table_names.get(index)
            else:
                caption,rows=custom[line.split()[1]];tbl=make_table(rows)
            if caption:
                table_no+=1;body.append(clone_text(sp[187],f'Bảng {chap}.{table_no}: {caption}'))
            body.append(tbl)
    if lines:body.append(clone_text(sp[70],' '.join(lines)))
body.append(section)

# Rebuild the cached outline using original TOC paragraph styles and a live Word field.
sdt=body.find('w:sdt',NS)
toc=sdt.find('w:sdtContent',NS)
old_toc=deepcopy(toc)
toc_templates={}
for p in old_toc.findall('w:p',NS):
    st=p.find('w:pPr/w:pStyle',NS)
    if st is not None:toc_templates.setdefault(st.get(W+'val'),p)
for c in list(toc):toc.remove(c)
toc_field=E.SubElement(toc,W+'p')
r=E.SubElement(toc_field,W+'r');f=E.SubElement(r,W+'fldChar');f.set(W+'fldCharType','begin');f.set(W+'dirty','true')
r=E.SubElement(toc_field,W+'r');E.SubElement(r,W+'instrText').text=' TOC \\o "1-3" \\h \\z \\u '
r=E.SubElement(toc_field,W+'r');E.SubElement(r,W+'fldChar').set(W+'fldCharType','separate')
for level,label,bookmark in headings:
    template=toc_templates.get('TOC'+str(level),next(iter(toc_templates.values())))
    p=clone_text(template,label)
    # Do not preserve stale page numbers or old hyperlink targets.
    r=p.find('w:r',NS);p.remove(r)
    link=E.SubElement(p,W+'hyperlink');link.set(W+'anchor',bookmark);link.append(r)
    toc.append(p)
p=E.SubElement(toc,W+'p');r=E.SubElement(p,W+'r');E.SubElement(r,W+'fldChar').set(W+'fldCharType','end')

settings=E.fromstring(current['word/settings.xml'])
u=settings.find('w:updateFields',NS)
if u is None:u=E.SubElement(settings,W+'updateFields')
u.set(W+'val','true')
changed={'word/document.xml':E.tostring(doc,encoding='UTF-8',xml_declaration=True,standalone=True),'word/settings.xml':E.tostring(settings,encoding='UTF-8',xml_declaration=True,standalone=True)}
original_sections=E.fromstring(current['word/document.xml']).xpath('//w:sectPr',namespaces=NS)
assert [E.tostring(s) for s in original_sections]==[E.tostring(s) for s in doc.xpath('//w:sectPr',namespaces=NS)]
reason=(ROOT/'reports/report-restructured.md').read_text(encoding='utf-8').split('## Lý do chọn đề tài')[1].split('## Mục tiêu')[0]
assert not any(w in reason.lower() for w in ['dataset','spark','pytorch','colab','114.000'])
assert chap==5
assert len(doc.xpath('//w:bookmarkStart/@w:id',namespaces=NS))==len(set(doc.xpath('//w:bookmarkStart/@w:id',namespaces=NS)))
temporary=TARGET.with_suffix('.restructured.docx')
with ZipFile(temporary,'w',ZIP_DEFLATED) as z:
    for name,data in current.items():z.writestr(name,changed.get(name,data))
with ZipFile(temporary) as z:
    assert all(z.read(n)==v for n,v in current.items() if n not in changed)
assert hashlib.sha256(TARGET.read_bytes()).hexdigest()==digest,'Document changed concurrently'
temporary.replace(TARGET)
(QA/'restructured-outline.json').write_text(json.dumps(headings,ensure_ascii=False,indent=2),encoding='utf-8')
(QA/'restructured-content-dump.txt').write_text('\n'.join(value(p) for p in doc.xpath('//w:body//w:p',namespaces=NS)),encoding='utf-8')
(QA/'restructure-audit.json').write_text(json.dumps({'source_sha256':digest,'backup':str(backup),'chapters':chap,'headings':len(headings),'tables':len(body.findall('w:tbl',NS)),'styles_preserved':True,'numbering_preserved':True,'sections_preserved':True,'changed_parts':list(changed),'toc':'Live field rebuilt with new outline; page numbers require Word update','render':'Not verified; bundled LibreOffice unavailable'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Updated original file:',TARGET)
print('Chapters:',chap,'Headings:',len(headings),'Tables:',len(body.findall('w:tbl',NS)))
