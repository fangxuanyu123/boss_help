"""简历解析工具 - 支持 PDF 和 DOCX"""
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF
from docx import Document
from models.resume import Resume


def parse_pdf(filepath: Path) -> str:
    """解析 PDF 文件为纯文本"""
    doc = fitz.open(filepath)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def parse_docx(filepath: Path) -> str:
    """解析 DOCX 文件为纯文本"""
    doc = Document(str(filepath))
    text = "\n".join([p.text for p in doc.paragraphs])
    return text.strip()


def parse_resume(filepath: Path) -> Optional[Resume]:
    """解析简历文件为结构化 Resume 对象"""
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        raw_text = parse_pdf(filepath)
    elif suffix == ".docx":
        raw_text = parse_docx(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {suffix}，仅支持 PDF 和 DOCX")

    if not raw_text:
        return None

    # 返回包含原始文本的 Resume 对象，结构化由 LLM Agent 完成
    return Resume(raw_text=raw_text)
