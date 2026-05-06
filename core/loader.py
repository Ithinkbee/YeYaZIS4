"""
loader.py — загрузка текста из DOC, DOCX, TXT, PDF, RTF, HTML.
"""
import os, re, subprocess
from pathlib import Path


def load_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    dispatch = {
        '.docx': _docx, '.doc': _doc,
        '.txt':  _txt,  '.pdf': _pdf,
        '.rtf':  _rtf,  '.html': _html, '.htm': _html,
    }
    fn = dispatch.get(ext)
    if fn is None:
        raise ValueError(f'Формат «{ext}» не поддерживается.')
    return fn(path)


def _docx(path):
    from docx import Document
    doc = Document(path)
    return '\n'.join(p.text.strip() for p in doc.paragraphs if p.text.strip())


def _doc(path):
    # 1. LibreOffice
    try:
        import tempfile, shutil
        tmp = tempfile.mkdtemp()
        subprocess.run(
            ['soffice', '--headless', '--convert-to', 'txt:Text', '--outdir', tmp, path],
            capture_output=True, timeout=30
        )
        txts = list(Path(tmp).glob('*.txt'))
        if txts:
            t = txts[0].read_text(encoding='utf-8', errors='replace')
            shutil.rmtree(tmp, ignore_errors=True)
            return t
    except Exception:
        pass
    # 2. antiword
    try:
        r = subprocess.run(['antiword', path], capture_output=True, timeout=30)
        if r.returncode == 0:
            return r.stdout.decode('utf-8', errors='replace')
    except Exception:
        pass
    # 3. try as docx
    try:
        return _docx(path)
    except Exception:
        pass
    raise RuntimeError(
        'Не удалось открыть .doc.\n'
        'Установите LibreOffice (sudo apt install libreoffice) или antiword.'
    )


def _txt(path):
    for enc in ('utf-8', 'cp1251', 'latin-1'):
        try:
            return Path(path).read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return Path(path).read_bytes().decode('utf-8', errors='replace')


def _pdf(path):
    try:
        import pdfplumber
        texts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
        return '\n'.join(texts)
    except ImportError:
        pass
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        return '\n'.join(p.extract_text() or '' for p in r.pages)
    except ImportError:
        pass
    raise RuntimeError('Установите pdfplumber: pip install pdfplumber')


def _rtf(path):
    try:
        from striprtf.striprtf import rtf_to_text
        raw = Path(path).read_text(encoding='utf-8', errors='replace')
        return rtf_to_text(raw)
    except ImportError:
        pass
    raw = Path(path).read_bytes().decode('cp1251', errors='replace')
    text = re.sub(r'\{[^{}]*\}', '', raw)
    text = re.sub(r'\\[a-z]+\d*\s?', ' ', text)
    text = re.sub(r'[{}\\]', '', text)
    return re.sub(r' {2,}', ' ', text).strip()


def _html(path):
    raw = Path(path).read_text(encoding='utf-8', errors='replace')
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(raw, 'html.parser').get_text(separator='\n')
    except ImportError:
        text = re.sub(r'<[^>]+>', ' ', raw)
        return re.sub(r' {2,}', ' ', text).strip()
