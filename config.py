"""应用配置管理"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# 项目路径
PROJECT_ROOT = Path(__file__).parent
OUTPUT_PATH = PROJECT_ROOT / "output"

# 确保目录存在
OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

# LLM 配置
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME", "deepseek-chat")
