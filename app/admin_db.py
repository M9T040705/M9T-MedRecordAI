"""管理后台数据持久化：抽取模板、ICD编码库、术语词典。

表：
- extraction_templates：抽取模板（不同类型病案的字段配置）
- icd_codes：ICD编码库（疾病编码与名称）
- term_dictionary：术语词典（同义词、缩写映射）
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional

from .config import settings

_lock = threading.Lock()

# ---------------- 建表 SQL ----------------

_MYSQL_SQL = """
CREATE TABLE IF NOT EXISTS extraction_templates (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    doc_type VARCHAR(64) NOT NULL,
    description TEXT,
    fields_json JSON NOT NULL,
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name (name),
    INDEX idx_doc_type (doc_type),
    INDEX idx_is_active (is_active)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS icd_codes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(256) NOT NULL,
    category VARCHAR(64),
    description TEXT,
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_code (code),
    INDEX idx_name (name),
    INDEX idx_category (category)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS term_dictionary (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    term VARCHAR(128) NOT NULL,
    standard_term VARCHAR(128) NOT NULL,
    term_type VARCHAR(32) DEFAULT 'synonym',
    description TEXT,
    is_active TINYINT DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_term (term),
    INDEX idx_standard_term (standard_term),
    INDEX idx_term_type (term_type)
) DEFAULT CHARSET=utf8mb4;
"""

_SQLITE_SQL = """
CREATE TABLE IF NOT EXISTS extraction_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    description TEXT,
    fields_json TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(name)
);
CREATE INDEX IF NOT EXISTS idx_templates_doc_type ON extraction_templates(doc_type);
CREATE INDEX IF NOT EXISTS idx_templates_active ON extraction_templates(is_active);

CREATE TABLE IF NOT EXISTS icd_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(code)
);
CREATE INDEX IF NOT EXISTS idx_icd_name ON icd_codes(name);
CREATE INDEX IF NOT EXISTS idx_icd_category ON icd_codes(category);

CREATE TABLE IF NOT EXISTS term_dictionary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    standard_term TEXT NOT NULL,
    term_type TEXT DEFAULT 'synonym',
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')),
    UNIQUE(term)
);
CREATE INDEX IF NOT EXISTS idx_term_standard ON term_dictionary(standard_term);
CREATE INDEX IF NOT EXISTS idx_term_type ON term_dictionary(term_type);
"""


def init_admin_db() -> None:
    """初始化管理后台数据表。"""
    from .db import _backend, _get_mysql, _get_sqlite
    with _lock:
        if _backend == "mysql":
            try:
                c = _get_mysql()
                for stmt in _MYSQL_SQL.split(";"):
                    if stmt.strip():
                        with c.cursor() as cur:
                            cur.execute(stmt)
                c.commit()
                c.close()
                return
            except Exception:
                pass
        conn = _get_sqlite()
        conn.executescript(_SQLITE_SQL)
        conn.commit()


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_conn():
    from .db import _backend, _get_mysql, _get_sqlite
    if _backend == "mysql":
        try:
            return _get_mysql(), "mysql"
        except Exception:
            pass
    return _get_sqlite(), "sqlite"


def _row_to_dict(row) -> dict:
    d = dict(row)
    if isinstance(d.get("fields_json"), str):
        try:
            d["fields_json"] = json.loads(d["fields_json"])
        except Exception:
            pass
    return d


# ==================== 抽取模板 ====================

def list_templates(doc_type: Optional[str] = None, is_active: Optional[int] = None,
                   keyword: str = "", limit: int = 50, offset: int = 0) -> list:
    """查询抽取模板列表。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if doc_type:
            conditions.append(f"doc_type={ph}")
            params.append(doc_type)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(name LIKE {ph} OR description LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM extraction_templates{where} ORDER BY id DESC LIMIT {ph} OFFSET {ph}"
        rows = conn.execute(sql, params).fetchall() if backend == "sqlite" else _mysql_fetchall(conn, sql, params)
        return [_row_to_dict(r) for r in rows]


def count_templates(doc_type: Optional[str] = None, is_active: Optional[int] = None, keyword: str = "") -> int:
    """统计抽取模板数量。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if doc_type:
            conditions.append(f"doc_type={ph}")
            params.append(doc_type)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(name LIKE {ph} OR description LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT COUNT(*) as cnt FROM extraction_templates{where}"
        row = conn.execute(sql, params).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, params)
        return row["cnt"] if row else 0


def get_template(template_id: int) -> Optional[dict]:
    """获取单个抽取模板。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM extraction_templates WHERE id={ph}"
        row = conn.execute(sql, (template_id,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (template_id,))
        return _row_to_dict(row) if row else None


def get_template_by_name(name: str) -> Optional[dict]:
    """按名称获取抽取模板。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM extraction_templates WHERE name={ph} AND is_active=1"
        row = conn.execute(sql, (name,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (name,))
        return _row_to_dict(row) if row else None


def create_template(data: dict) -> int:
    """创建抽取模板。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        fields_json = json.dumps(data.get("fields", []), ensure_ascii=False)
        sql = (f"INSERT INTO extraction_templates (name,doc_type,description,fields_json,is_active) "
               f"VALUES ({ph},{ph},{ph},{ph},{ph})")
        params = (data["name"], data.get("doc_type", ""), data.get("description", ""),
                  fields_json, data.get("is_active", 1))
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                tid = cur.lastrowid
            conn.commit()
            conn.close()
            return tid


def update_template(template_id: int, data: dict) -> bool:
    """更新抽取模板。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sets = []
        params = []
        if "name" in data:
            sets.append(f"name={ph}")
            params.append(data["name"])
        if "doc_type" in data:
            sets.append(f"doc_type={ph}")
            params.append(data["doc_type"])
        if "description" in data:
            sets.append(f"description={ph}")
            params.append(data["description"])
        if "fields" in data:
            sets.append(f"fields_json={ph}")
            params.append(json.dumps(data["fields"], ensure_ascii=False))
        if "is_active" in data:
            sets.append(f"is_active={ph}")
            params.append(data["is_active"])
        if not sets:
            return False
        sets.append(f"updated_at={ph}")
        params.append(_now_str())
        params.append(template_id)
        sql = f"UPDATE extraction_templates SET {', '.join(sets)} WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


def delete_template(template_id: int) -> bool:
    """删除抽取模板。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"DELETE FROM extraction_templates WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, (template_id,))
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, (template_id,))
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


# ==================== ICD 编码库 ====================

def list_icd_codes(category: Optional[str] = None, is_active: Optional[int] = None,
                   keyword: str = "", limit: int = 50, offset: int = 0) -> list:
    """查询ICD编码列表。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if category:
            conditions.append(f"category={ph}")
            params.append(category)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(code LIKE {ph} OR name LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM icd_codes{where} ORDER BY code ASC LIMIT {ph} OFFSET {ph}"
        rows = conn.execute(sql, params).fetchall() if backend == "sqlite" else _mysql_fetchall(conn, sql, params)
        return [dict(r) for r in rows]


def count_icd_codes(category: Optional[str] = None, is_active: Optional[int] = None, keyword: str = "") -> int:
    """统计ICD编码数量。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if category:
            conditions.append(f"category={ph}")
            params.append(category)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(code LIKE {ph} OR name LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT COUNT(*) as cnt FROM icd_codes{where}"
        row = conn.execute(sql, params).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, params)
        return row["cnt"] if row else 0


def get_icd_code(icd_id: int) -> Optional[dict]:
    """获取单个ICD编码。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM icd_codes WHERE id={ph}"
        row = conn.execute(sql, (icd_id,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (icd_id,))
        return dict(row) if row else None


def get_icd_by_code(code: str) -> Optional[dict]:
    """按编码获取ICD。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM icd_codes WHERE code={ph} AND is_active=1"
        row = conn.execute(sql, (code,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (code,))
        return dict(row) if row else None


def search_icd(keyword: str, limit: int = 10) -> list:
    """搜索ICD编码（按编码或名称模糊匹配）。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM icd_codes WHERE is_active=1 AND (code LIKE {ph} OR name LIKE {ph}) ORDER BY code ASC LIMIT {ph}"
        params = (f"%{keyword}%", f"%{keyword}%", limit)
        rows = conn.execute(sql, params).fetchall() if backend == "sqlite" else _mysql_fetchall(conn, sql, params)
        return [dict(r) for r in rows]


def create_icd_code(data: dict) -> int:
    """创建ICD编码。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = (f"INSERT INTO icd_codes (code,name,category,description,is_active) "
               f"VALUES ({ph},{ph},{ph},{ph},{ph})")
        params = (data["code"], data["name"], data.get("category", ""),
                  data.get("description", ""), data.get("is_active", 1))
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                iid = cur.lastrowid
            conn.commit()
            conn.close()
            return iid


def update_icd_code(icd_id: int, data: dict) -> bool:
    """更新ICD编码。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sets = []
        params = []
        for key in ("code", "name", "category", "description", "is_active"):
            if key in data:
                sets.append(f"{key}={ph}")
                params.append(data[key])
        if not sets:
            return False
        sets.append(f"updated_at={ph}")
        params.append(_now_str())
        params.append(icd_id)
        sql = f"UPDATE icd_codes SET {', '.join(sets)} WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


def delete_icd_code(icd_id: int) -> bool:
    """删除ICD编码。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"DELETE FROM icd_codes WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, (icd_id,))
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, (icd_id,))
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


# ==================== 术语词典 ====================

def list_terms(term_type: Optional[str] = None, is_active: Optional[int] = None,
               keyword: str = "", limit: int = 50, offset: int = 0) -> list:
    """查询术语列表。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if term_type:
            conditions.append(f"term_type={ph}")
            params.append(term_type)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(term LIKE {ph} OR standard_term LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        sql = f"SELECT * FROM term_dictionary{where} ORDER BY id DESC LIMIT {ph} OFFSET {ph}"
        rows = conn.execute(sql, params).fetchall() if backend == "sqlite" else _mysql_fetchall(conn, sql, params)
        return [dict(r) for r in rows]


def count_terms(term_type: Optional[str] = None, is_active: Optional[int] = None, keyword: str = "") -> int:
    """统计术语数量。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        conditions = []
        params = []
        if term_type:
            conditions.append(f"term_type={ph}")
            params.append(term_type)
        if is_active is not None:
            conditions.append(f"is_active={ph}")
            params.append(is_active)
        if keyword:
            conditions.append(f"(term LIKE {ph} OR standard_term LIKE {ph})")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT COUNT(*) as cnt FROM term_dictionary{where}"
        row = conn.execute(sql, params).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, params)
        return row["cnt"] if row else 0


def get_term(term_id: int) -> Optional[dict]:
    """获取单个术语。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT * FROM term_dictionary WHERE id={ph}"
        row = conn.execute(sql, (term_id,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (term_id,))
        return dict(row) if row else None


def get_standard_term(term: str) -> Optional[str]:
    """获取术语的标准名称（用于抽取时归一化）。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"SELECT standard_term FROM term_dictionary WHERE term={ph} AND is_active=1"
        row = conn.execute(sql, (term,)).fetchone() if backend == "sqlite" else _mysql_fetchone(conn, sql, (term,))
        return row["standard_term"] if row else None


def get_all_term_mappings() -> dict:
    """获取所有术语映射（term -> standard_term），用于抽取前预处理。"""
    with _lock:
        conn, backend = _get_conn()
        sql = "SELECT term, standard_term FROM term_dictionary WHERE is_active=1"
        rows = conn.execute(sql).fetchall() if backend == "sqlite" else _mysql_fetchall(conn, sql, [])
        return {r["term"]: r["standard_term"] for r in rows}


def create_term(data: dict) -> int:
    """创建术语。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = (f"INSERT INTO term_dictionary (term,standard_term,term_type,description,is_active) "
               f"VALUES ({ph},{ph},{ph},{ph},{ph})")
        params = (data["term"], data["standard_term"], data.get("term_type", "synonym"),
                  data.get("description", ""), data.get("is_active", 1))
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                tid = cur.lastrowid
            conn.commit()
            conn.close()
            return tid


def update_term(term_id: int, data: dict) -> bool:
    """更新术语。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sets = []
        params = []
        for key in ("term", "standard_term", "term_type", "description", "is_active"):
            if key in data:
                sets.append(f"{key}={ph}")
                params.append(data[key])
        if not sets:
            return False
        sets.append(f"updated_at={ph}")
        params.append(_now_str())
        params.append(term_id)
        sql = f"UPDATE term_dictionary SET {', '.join(sets)} WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


def delete_term(term_id: int) -> bool:
    """删除术语。"""
    with _lock:
        conn, backend = _get_conn()
        ph = "%s" if backend == "mysql" else "?"
        sql = f"DELETE FROM term_dictionary WHERE id={ph}"
        if backend == "sqlite":
            cur = conn.execute(sql, (term_id,))
            conn.commit()
            return cur.rowcount > 0
        else:
            with conn.cursor() as cur:
                cur.execute(sql, (term_id,))
                affected = cur.rowcount
            conn.commit()
            conn.close()
            return affected > 0


# ==================== MySQL 辅助函数 ====================

def _mysql_fetchone(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _mysql_fetchall(conn, sql, params):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()
