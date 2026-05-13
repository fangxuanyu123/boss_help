"""向量数据库管理 - ChromaDB"""
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from config import CHROMA_DB_PATH, CHROMA_COLLECTION_NAME
from rag.embedding import embedding_provider


class VectorStore:
    """ChromaDB 向量存储封装"""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DB_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self._get_or_create_collection()
        self.embedder = embedding_provider

    def _get_or_create_collection(self):
        """获取或创建集合"""
        try:
            return self.client.get_collection(CHROMA_COLLECTION_NAME)
        except ValueError:
            return self.client.create_collection(CHROMA_COLLECTION_NAME)

    def add_documents(self, documents: List[Dict]) -> int:
        """添加文档到向量库"""
        if not documents:
            return 0

        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        embeddings = self.embedder.embed_texts(texts)

        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(documents)

    def similarity_search(self, query: str, k: int = 5) -> List[Dict]:
        """语义搜索，返回最相似的 k 个文档"""
        query_embedding = self.embedder.embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
        )

        documents = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                documents.append({
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "score": results["distances"][0][i] if results["distances"] else 0,
                })
        return documents

    def count(self) -> int:
        """返回向量库中的文档数量"""
        return self.collection.count()

    def delete_all(self):
        """清空集合"""
        self.client.delete_collection(CHROMA_COLLECTION_NAME)
        self.collection = self._get_or_create_collection()

    def get_all_documents(self) -> List[Dict]:
        """获取所有文档"""
        results = self.collection.get()
        docs = []
        if results["ids"]:
            for i, doc_id in enumerate(results["ids"]):
                docs.append({
                    "id": doc_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
        return docs


# 全局单例
vector_store = VectorStore()
