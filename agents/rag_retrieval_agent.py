"""RAG 检索 Agent - 根据分析结果从知识库检索优秀简历片段"""
from typing import List, Dict
from rag.retriever import retriever


class RAGRetrievalAgent:
    """RAG 检索智能体"""

    def retrieve_by_analysis(self, analysis: Dict, k: int = 5) -> List[Dict]:
        """根据简历分析结果检索相关优秀简历片段"""
        structured = analysis.get("structured", {})
        title = structured.get("title", "")
        skills = []
        for s in structured.get("skills", []):
            skills.extend(s.get("items", []))

        # 根据求职意向和技能检索
        query_parts = [f"求职意向: {title}"] if title else []
        if skills:
            query_parts.append(f"技能: {', '.join(skills)}")

        # 同时检索薄弱环节的相关内容
        weaknesses = analysis.get("weaknesses", [])
        for w in weaknesses[:2]:
            query_parts.append(w.get("aspect", ""))

        query = " | ".join(query_parts)
        return retriever.search_similar(query, k=k)

    def retrieve_by_query(self, query: str, k: int = 5) -> List[Dict]:
        """直接通过查询检索"""
        return retriever.search_similar(query, k=k)

    def format_results(self, results: List[Dict]) -> str:
        """将检索结果格式化为文本"""
        if not results:
            return "未检索到相关优秀简历参考。"

        formatted = ["以下是与您背景相关的优秀简历片段参考：\n"]
        for i, doc in enumerate(results, 1):
            formatted.append(f"--- 参考 {i} ---")
            formatted.append(doc["text"])
            formatted.append("")

        return "\n".join(formatted)
