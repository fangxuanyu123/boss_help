"""简历文档处理 - 文本提取与分块"""
from pathlib import Path
from typing import List, Dict
import uuid
from langchain.text_splitter import RecursiveCharacterTextSplitter
from utils.resume_parser import parse_pdf, parse_docx


class DocumentProcessor:
    """文档处理器：提取文本、分块"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )

    def extract_text(self, filepath: Path) -> str:
        """提取文件文本"""
        suffix = filepath.suffix.lower()
        if suffix == ".pdf":
            return parse_pdf(filepath)
        elif suffix == ".docx":
            return parse_docx(filepath)
        elif suffix == ".txt":
            return filepath.read_text(encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def split_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """将文本分割为带元数据的块"""
        chunks = self.text_splitter.split_text(text)
        documents = []
        for chunk in chunks:
            doc = {
                "id": uuid.uuid4().hex,
                "text": chunk,
                "metadata": metadata or {},
            }
            documents.append(doc)
        return documents

    def process_file(self, filepath: Path, metadata: Dict = None) -> List[Dict]:
        """处理单个文件：提取→分块"""
        text = self.extract_text(filepath)
        if metadata is None:
            metadata = {"source": filepath.name, "type": "resume"}
        else:
            metadata["source"] = filepath.name
        return self.split_text(text, metadata)
