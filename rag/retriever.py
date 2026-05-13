"""检索器 - 提供高层检索接口"""
from typing import List, Dict
from rag.vector_store import vector_store
from rag.document_processor import DocumentProcessor
from pathlib import Path


class ResumeRetriever:
    """简历知识库检索器"""

    def __init__(self):
        self.vector_store = vector_store
        self.processor = DocumentProcessor()

    def search_similar(self, query: str, k: int = 5) -> List[Dict]:
        """根据查询检索相似简历片段"""
        return self.vector_store.similarity_search(query, k=k)

    def search_by_job_intent(self, job_title: str, skills: List[str], k: int = 5) -> List[Dict]:
        """根据求职意向检索优秀简历"""
        query = f"求职意向: {job_title}，技能: {', '.join(skills)}"
        return self.search_similar(query, k=k)

    def add_resume_to_kb(self, filepath: Path, metadata: Dict = None) -> int:
        """将简历文件添加到知识库"""
        documents = self.processor.process_file(filepath, metadata)
        return self.vector_store.add_documents(documents)

    def batch_add_to_kb(self, directory: Path) -> int:
        """批量添加目录下所有简历到知识库"""
        total = 0
        for ext in ["*.pdf", "*.docx", "*.txt"]:
            for filepath in directory.glob(ext):
                try:
                    added = self.add_resume_to_kb(filepath)
                    total += added
                except Exception as e:
                    print(f"处理文件 {filepath.name} 失败: {e}")
        return total

    def get_knowledge_base_stats(self) -> Dict:
        """获取知识库统计"""
        return {
            "total_chunks": self.vector_store.count(),
        }


# 全局单例
retriever = ResumeRetriever()
