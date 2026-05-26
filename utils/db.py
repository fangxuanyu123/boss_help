"""SQLite 持久化 —— 存储优化历史记录"""
import sqlite3
import json
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "output" / "history.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            resume_name TEXT NOT NULL,
            job_title TEXT NOT NULL,
            match_score REAL,
            num_changes INTEGER,
            num_rounds INTEGER,
            coherence_score REAL,
            pdf_style TEXT,
            resume_raw_text TEXT,
            optimized_resume_json TEXT,
            diff_result_json TEXT,
            match_result_json TEXT,
            interview_prep_json TEXT,
            reflection_logs_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_optimization(
    resume_name: str,
    job_title: str,
    match_score: Optional[float],
    num_changes: Optional[int],
    num_rounds: Optional[int],
    coherence_score: Optional[float],
    pdf_style: Optional[str],
    resume_raw_text: str,
    optimized_resume_json: str,
    diff_result_json: str,
    match_result_json: str,
    interview_prep_json: str,
    reflection_logs_json: str,
) -> int:
    """保存一次优化记录，返回记录ID"""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO optimizations (
            resume_name, job_title, match_score, num_changes, num_rounds,
            coherence_score, pdf_style, resume_raw_text, optimized_resume_json,
            diff_result_json, match_result_json, interview_prep_json, reflection_logs_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            resume_name, job_title, match_score, num_changes, num_rounds,
            coherence_score, pdf_style, resume_raw_text, optimized_resume_json,
            diff_result_json, match_result_json, interview_prep_json, reflection_logs_json,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    logger.info("优化记录已保存: id=%d, title=%s, score=%.1f", row_id, job_title, match_score or 0)
    return row_id


def list_history(limit: int = 20) -> list[dict]:
    """列出最近的优化记录（不含大数据字段）"""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT id, created_at, resume_name, job_title, match_score,
                  num_changes, num_rounds, coherence_score, pdf_style
           FROM optimizations ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_optimization(record_id: int) -> Optional[dict]:
    """获取单条完整记录"""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM optimizations WHERE id=?", (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_optimization(record_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM optimizations WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    logger.info("优化记录已删除: id=%d", record_id)
