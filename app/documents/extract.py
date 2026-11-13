from app.config import MAX_PDF_PAGES,MAX_EXTRACTED_CHARS
from io import BytesIO
from pathlib import Path
import zipfile

TEXT_EXT={'.txt','.md','.csv','.py','.cpp','.c','.java','.js','.html','.css','.json'}
def extract(filename,data):
    """Never execute file content. Return source locations, not invented page numbers."""
    suffix=Path(filename).suffix.lower()
    if suffix in {'.docx','.pptx'}:
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                entries=archive.infolist()
                if len(entries)>5000 or sum(i.file_size for i in entries)>40*1024*1024:
                    raise ValueError('Document expands beyond the safety limit.')
        except zipfile.BadZipFile: raise ValueError('Invalid Office document.')
    if suffix in TEXT_EXT:
        try:text=data.decode('utf-8-sig')
        except UnicodeDecodeError:raise ValueError('Text files must use UTF-8 encoding.')
        if '\x00' in text:raise ValueError('Binary data is not a text resource.')
        lines=text.splitlines();parts=[(f'Lines {i+1}–{min(i+35,len(lines))}','\n'.join(lines[i:i+35])) for i in range(0,len(lines),35)]
    elif suffix=='.pdf':
        from pypdf import PdfReader
        pdf=PdfReader(BytesIO(data))
        if len(pdf.pages)>MAX_PDF_PAGES:raise ValueError(f'PDF page limit is {MAX_PDF_PAGES}. Split the book into chapter files.')
        parts=[(f'Page {i+1}',p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    elif suffix=='.docx':
        from docx import Document
        doc=Document(BytesIO(data))
        parts=[(f'Paragraph {i+1}',p.text) for i,p in enumerate(doc.paragraphs)]
        parts += [(f'Table {i+1}','\n'.join(' | '.join(c.text for c in row.cells) for row in table.rows)) for i,table in enumerate(doc.tables)]
    elif suffix=='.pptx':
        from pptx import Presentation
        ppt=Presentation(BytesIO(data))
        parts=[(f'Slide {i+1}','\n'.join(shape.text for shape in slide.shapes if shape.has_text_frame)) for i,slide in enumerate(ppt.slides)]
    elif suffix in {'.png','.jpg','.jpeg','.webp'}:
        from app.documents.multimodal import image_ocr
        parts=image_ocr(data)
    elif suffix in {'.mp3','.wav','.m4a','.ogg','.webm'}:
        from app.documents.multimodal import transcribe
        parts=transcribe(data,filename)
    elif suffix=='.mp4':
        from app.documents.multimodal import video_transcript
        parts=video_transcript(data,suffix)
    else:
        raise ValueError('Unsupported format. Use documents, images, supported audio/video, text or code.')
    output=[]
    for location,text in parts:
        text=text.strip()
        for start in range(0,len(text),1400):
            segment=text[start:start+1600]
            if segment.strip():output.append((location,segment))
    if not output:raise ValueError('No readable text found. Scanned documents need OCR first.')
    if sum(len(t) for _,t in output)>MAX_EXTRACTED_CHARS:raise ValueError('Extracted text exceeds the indexing limit.')
    return output
