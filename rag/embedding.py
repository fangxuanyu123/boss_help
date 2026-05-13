"""文本嵌入工具"""
from typing import List
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings
from config import EMBEDDING_MODEL_PATH, EMBEDDING_MODEL_TYPE


class EmbeddingProvider:
    """嵌入模型提供者"""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = self._init_model()
        return self._model

    def _init_model(self):
        if EMBEDDING_MODEL_TYPE == "openai":
            return OpenAIEmbeddings(
                model="text-embedding-ada-002",
            )
        else:
            return HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL_PATH,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文本"""
        return self.model.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """嵌入查询文本"""
        return self.model.embed_query(text)


# 全局单例
embedding_provider = EmbeddingProvider()
