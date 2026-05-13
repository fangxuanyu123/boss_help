"""文件处理工具"""
from pathlib import Path
from typing import Optional
import uuid
from config import OUTPUT_PATH


def save_uploaded_file(uploaded_file, target_dir: Path) -> Optional[Path]:
    """保存上传的文件到目标目录"""
    if uploaded_file is None:
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(uploaded_file.name).suffix
    filename = f"{uuid.uuid4().hex}{suffix}"
    filepath = target_dir / filename
    filepath.write_bytes(uploaded_file.getvalue())
    return filepath


def save_generated_resume(content: str, filename: str = "optimized_resume.md") -> Path:
    """保存生成的简历"""
    filepath = OUTPUT_PATH / filename
    filepath.write_text(content, encoding="utf-8")
    return filepath


def read_file_content(filepath: Path) -> str:
    """读取文件内容"""
    return filepath.read_text(encoding="utf-8")
