"""应用配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目路径
PROJECT_ROOT = Path(__file__).parent
KNOWLEDGE_BASE_PATH = Path(os.getenv("KNOWLEDGE_BASE_PATH", PROJECT_ROOT / "knowledge_base"))
CHROMA_DB_PATH = Path(os.getenv("CHROMA_DB_PATH", PROJECT_ROOT / "chroma_db"))
OUTPUT_PATH = PROJECT_ROOT / "output"

# 确保目录存在
KNOWLEDGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")

# 嵌入模型配置
EMBEDDING_MODEL_PATH = os.getenv("EMBEDDING_MODEL_PATH", "shibing624/text2vec-base-chinese")
EMBEDDING_MODEL_TYPE = os.getenv("EMBEDDING_MODEL_TYPE", "local")  # local or openai

# ChromaDB 集合名称
CHROMA_COLLECTION_NAME = "resume_knowledge_base"
