"""数据持久化：抽取结果落库（MySQL 优先，SQLite 自动降级）。

表：
- extraction_records：一次「解析+抽取」产生一条记录，带工作流状态、复核信息
- audit_logs：操作审计日志，记录谁在什么时候做了什么
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import settings

_lock = threading.Lock()
_conn = None
_backend = "sqlite"

# 工作流状态枚举
STATUS_PENDING = "pending"        # 待抽取
STATUS_EXTRACTED = "extracted"    # 已抽取（待复核）
STATUS_REVIEWING = "reviewing"    # 复核中
STATUS_CONFIRMED = "confirmed"    # 已确认
STATUS_ARCHIVED = "archived"      # 已归档

VALID_STATUSES = [STATUS_PENDING, STATUS_EXTRACTED, STATUS_REVIEWING,
                  STATUS_CONFIRMED, STATUS_ARCHIVED]

# 状态流转规则：当前状态 -> 允许的下一状态
STATUS_TRANSITIONS = {
    STATUS_PENDING: [STATUS_EXTRACTED],
    STATUS_EXTRACTED: [STATUS_REVIEWING, STATUS_CONFIRMED],
    STATUS_REVIEWING: [STATUS_CONFIRMED, STATUS_EXTRACTED],  # 确认或驳回重抽
    STATUS_CONFIRMED: [STATUS_ARCHIVED],
    STATUS_ARCHIVED: [],
}

_MYSQL_SQL = """
CREATE TABLE IF NOT EXISTS extraction_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    doc_name VARCHAR(255),
    department VARCHAR(64),
    fields_json JSON,
    icd_json JSON,
    original_text TEXT,
    mode VARCHAR(32),
    confidence FLOAT,
    status VARCHAR(16) DEFAULT 'extracted',
    reviewer VARCHAR(64) DEFAULT '',
    reviewed_at DATETIME NULL,
    confirmed_by VARCHAR(64) DEFAULT '',
    confirmed_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_department (department),
    INDEX idx_created_at (created_at)
) DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64),
    department VARCHAR(64),
    action VARCHAR(32),
    target_type VARCHAR(32),
    target_id VARCHAR(64),
    detail JSON,
    ip_address VARCHAR(64) DEFAULT '',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at)
) DEFAULT CHARSET=utf8mb4;
"""

_SQLITE_SQL = """
CREATE TABLE IF NOT EXISTS extraction_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_name TEXT,
    department TEXT,
    fields_json TEXT,
    icd_json TEXT,
    original_text TEXT,
    mode TEXT,
    confidence REAL,
    status TEXT DEFAULT 'extracted',
    reviewer TEXT DEFAULT '',
    reviewed_at TEXT,
    confirmed_by TEXT DEFAULT '',
    confirmed_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    department TEXT,
    action TEXT,
    target_type TEXT,
    target_id TEXT,
    detail TEXT,
    ip_address TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_status ON extraction_records(status);
CREATE INDEX IF NOT EXISTS idx_records_department ON extraction_records(department);
CREATE INDEX IF NOT EXISTS idx_audit_username ON audit_logs(username);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
"""


def _get_sqlite() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = settings.project_dir / "data" / "platform.db"
        path.parent.mkdir(exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def _get_mysql():
    import pymysql
    return pymysql.connect(
        host=settings.mysql_host, port=settings.mysql_port,
        user=settings.mysql_user, password=settings.mysql_password,
        database=settings.mysql_db, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def init_db() -> None:
    global _backend
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
                # 尝试为旧表添加新列（兼容升级）
                _migrate_mysql_columns()
                return
            except Exception:
                _backend = "sqlite"
        conn = _get_sqlite()
        conn.executescript(_SQLITE_SQL)
        conn.commit()
        _migrate_sqlite_columns()


def _migrate_mysql_columns():
    """为旧版本表添加新列（MySQL）。"""
    try:
        c = _get_mysql()
        with c.cursor() as cur:
            # 检查列是否存在，不存在则添加
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'original_text'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN original_text TEXT AFTER icd_json")
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'reviewer'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN reviewer VARCHAR(64) DEFAULT '' AFTER status")
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'reviewed_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN reviewed_at DATETIME NULL AFTER reviewer")
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'confirmed_by'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN confirmed_by VARCHAR(64) DEFAULT '' AFTER reviewed_at")
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'confirmed_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN confirmed_at DATETIME NULL AFTER confirmed_by")
            cur.execute("SHOW COLUMNS FROM extraction_records LIKE 'updated_at'")
            if not cur.fetchone():
                cur.execute("ALTER TABLE extraction_records ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER created_at")
        c.commit()
        c.close()
    except Exception:
        pass


def _migrate_sqlite_columns():
    """为旧版本表添加新列（SQLite）。"""
    conn = _get_sqlite()
    try:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(extraction_records)").fetchall()]
        if "original_text" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN original_text TEXT")
        if "reviewer" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN reviewer TEXT DEFAULT ''")
        if "reviewed_at" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN reviewed_at TEXT")
        if "confirmed_by" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN confirmed_by TEXT DEFAULT ''")
        if "confirmed_at" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN confirmed_at TEXT")
        if "updated_at" not in columns:
            conn.execute("ALTER TABLE extraction_records ADD COLUMN updated_at TEXT DEFAULT (datetime('now','localtime'))")
        conn.commit()
    except Exception:
        pass


def get_backend() -> str:
    return _backend


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_record(record: dict) -> int:
    """保存抽取记录，返回记录ID。"""
    with _lock:
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(
                        "INSERT INTO extraction_records "
                        "(doc_name,department,fields_json,icd_json,original_text,mode,confidence,status) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (record["doc_name"], record["department"],
                         json.dumps(record["fields"], ensure_ascii=False),
                         json.dumps(record["icd"], ensure_ascii=False),
                         record.get("original_text", ""),
                         record["mode"], record["confidence"],
                         record.get("status", STATUS_EXTRACTED)),
                    )
                    rid = cur.lastrowid
                c.commit()
                c.close()
                return rid
            except Exception:
                pass
        conn = _get_sqlite()
        cur = conn.execute(
            "INSERT INTO extraction_records "
            "(doc_name,department,fields_json,icd_json,original_text,mode,confidence,status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (record["doc_name"], record["department"],
             json.dumps(record["fields"], ensure_ascii=False),
             json.dumps(record["icd"], ensure_ascii=False),
             record.get("original_text", ""),
             record["mode"], record["confidence"],
             record.get("status", STATUS_EXTRACTED)),
        )
        conn.commit()
        return cur.lastrowid


def get_record(record_id: int) -> Optional[dict]:
    """获取单条记录详情。"""
    with _lock:
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute("SELECT * FROM extraction_records WHERE id=%s", (record_id,))
                    row = cur.fetchone()
                c.close()
                return _row_to_dict(row) if row else None
            except Exception:
                pass
        conn = _get_sqlite()
        row = conn.execute("SELECT * FROM extraction_records WHERE id=?", (record_id,)).fetchone()
        return _row_to_dict(row) if row else None


def update_record(record_id: int, updates: dict) -> bool:
    """更新记录字段（fields_json、status、reviewer等）。"""
    if not updates:
        return False
    with _lock:
        sets = []
        params = []
        for key, val in updates.items():
            if key in ("fields_json", "icd_json") and isinstance(val, (dict, list)):
                val = json.dumps(val, ensure_ascii=False)
            sets.append(f"{key}=%s" if _backend == "mysql" else f"{key}=?")
            params.append(val)
        sets.append("updated_at=%s" if _backend == "mysql" else "updated_at=?")
        params.append(_now_str())
        params.append(record_id)
        sql = f"UPDATE extraction_records SET {', '.join(sets)} WHERE id={'%s' if _backend == 'mysql' else '?'}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    affected = cur.rowcount
                c.commit()
                c.close()
                return affected > 0
            except Exception:
                return False
        conn = _get_sqlite()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount > 0


def list_records(department: Optional[str] = None, status: Optional[str] = None,
                 limit: int = 50, offset: int = 0) -> list:
    """查询记录列表，支持按科室、状态筛选。"""
    with _lock:
        conditions = []
        params = []
        if department:
            conditions.append("department=%s" if _backend == "mysql" else "department=?")
            params.append(department)
        if status:
            conditions.append("status=%s" if _backend == "mysql" else "status=?")
            params.append(status)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        placeholder = "%s" if _backend == "mysql" else "?"
        params.extend([limit, offset])
        sql = f"SELECT * FROM extraction_records{where} ORDER BY id DESC LIMIT {placeholder} OFFSET {placeholder}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                c.close()
                return [_row_to_dict(r) for r in rows]
            except Exception:
                pass
        conn = _get_sqlite()
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def count_records(department: Optional[str] = None, status: Optional[str] = None) -> int:
    """统计记录数量。"""
    with _lock:
        conditions = []
        params = []
        if department:
            conditions.append("department=%s" if _backend == "mysql" else "department=?")
            params.append(department)
        if status:
            conditions.append("status=%s" if _backend == "mysql" else "status=?")
            params.append(status)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"SELECT COUNT(*) as cnt FROM extraction_records{where}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                c.close()
                return row["cnt"] if row else 0
            except Exception:
                pass
        conn = _get_sqlite()
        row = conn.execute(sql, params).fetchone()
        return row["cnt"] if row else 0


def add_audit_log(username: str, department: str, action: str,
                  target_type: str = "", target_id: str = "",
                  detail: Optional[dict] = None, ip_address: str = "") -> int:
    """添加审计日志。"""
    with _lock:
        detail_json = json.dumps(detail or {}, ensure_ascii=False)
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(
                        "INSERT INTO audit_logs (username,department,action,target_type,target_id,detail,ip_address) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (username, department, action, target_type, target_id, detail_json, ip_address),
                    )
                    lid = cur.lastrowid
                c.commit()
                c.close()
                return lid
            except Exception:
                pass
        conn = _get_sqlite()
        cur = conn.execute(
            "INSERT INTO audit_logs (username,department,action,target_type,target_id,detail,ip_address) "
            "VALUES (?,?,?,?,?,?,?)",
            (username, department, action, target_type, target_id, detail_json, ip_address),
        )
        conn.commit()
        return cur.lastrowid


def list_audit_logs(username: Optional[str] = None, action: Optional[str] = None,
                    limit: int = 100, offset: int = 0) -> list:
    """查询审计日志。"""
    with _lock:
        conditions = []
        params = []
        if username:
            conditions.append("username=%s" if _backend == "mysql" else "username=?")
            params.append(username)
        if action:
            conditions.append("action=%s" if _backend == "mysql" else "action=?")
            params.append(action)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        placeholder = "%s" if _backend == "mysql" else "?"
        params.extend([limit, offset])
        sql = f"SELECT * FROM audit_logs{where} ORDER BY id DESC LIMIT {placeholder} OFFSET {placeholder}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                c.close()
                return [_audit_row_to_dict(r) for r in rows]
            except Exception:
                pass
        conn = _get_sqlite()
        rows = conn.execute(sql, params).fetchall()
        return [_audit_row_to_dict(r) for r in rows]


def get_stats(department: Optional[str] = None) -> dict:
    """获取统计仪表盘数据。"""
    with _lock:
        where = ""
        params = []
        if department:
            where = " WHERE department=%s" if _backend == "mysql" else " WHERE department=?"
            params.append(department)
        placeholder = "%s" if _backend == "mysql" else "?"

        # 各状态数量
        status_counts = {}
        for st in VALID_STATUSES:
            sql = f"SELECT COUNT(*) as cnt FROM extraction_records{where}{' AND' if where else ''} status={placeholder}"
            p = params + [st]
            if _backend == "mysql":
                try:
                    c = _get_mysql()
                    with c.cursor() as cur:
                        cur.execute(sql, p)
                        row = cur.fetchone()
                    c.close()
                    status_counts[st] = row["cnt"] if row else 0
                except Exception:
                    status_counts[st] = 0
            else:
                conn = _get_sqlite()
                row = conn.execute(sql, p).fetchone()
                status_counts[st] = row["cnt"] if row else 0

        # 总数
        total = sum(status_counts.values())

        # 平均置信度
        avg_conf = 0.0
        sql = f"SELECT AVG(confidence) as avg_conf FROM extraction_records{where}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                c.close()
                avg_conf = float(row["avg_conf"] or 0)
            except Exception:
                pass
        else:
            conn = _get_sqlite()
            row = conn.execute(sql, params).fetchone()
            avg_conf = float(row["avg_conf"] or 0)

        # ICD 分布（前10）
        icd_dist = []
        sql = f"""
            SELECT icd_json FROM extraction_records
            {where} AND icd_json IS NOT NULL AND icd_json != ''
            LIMIT 500
        """
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                c.close()
                icd_dist = _count_icd(rows)
            except Exception:
                pass
        else:
            conn = _get_sqlite()
            rows = conn.execute(sql, params).fetchall()
            icd_dist = _count_icd(rows)

        # 近7天趋势
        daily_trend = _get_daily_trend(department)

        return {
            "total": total,
            "status_counts": status_counts,
            "avg_confidence": round(avg_conf, 2),
            "icd_distribution": icd_dist[:10],
            "daily_trend": daily_trend,
        }


def _count_icd(rows) -> list:
    """从记录中统计 ICD 分布。"""
    from collections import Counter
    counter = Counter()
    for row in rows:
        try:
            icd_json = row["icd_json"] if isinstance(row, dict) else row["icd_json"]
            if isinstance(icd_json, str):
                icd_json = json.loads(icd_json)
            code = icd_json.get("code", "")
            name = icd_json.get("name", "")
            if code and code not in ("", "null"):
                counter[f"{code} {name}".strip()] += 1
        except Exception:
            continue
    return [{"label": k, "count": v} for k, v in counter.most_common(10)]


def _get_daily_trend(department: Optional[str] = None) -> list:
    """获取近7天每日抽取量趋势。"""
    from datetime import timedelta
    today = datetime.now().date()
    result = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        where = " WHERE DATE(created_at)=%s" if _backend == "mysql" else " WHERE date(created_at)=?"
        params = [day_str]
        if department:
            where += " AND department=%s" if _backend == "mysql" else " AND department=?"
            params.append(department)
        sql = f"SELECT COUNT(*) as cnt FROM extraction_records{where}"
        if _backend == "mysql":
            try:
                c = _get_mysql()
                with c.cursor() as cur:
                    cur.execute(sql, params)
                    row = cur.fetchone()
                c.close()
                cnt = row["cnt"] if row else 0
            except Exception:
                cnt = 0
        else:
            conn = _get_sqlite()
            row = conn.execute(sql, params).fetchone()
            cnt = row["cnt"] if row else 0
        result.append({"date": day_str, "count": cnt})
    return result


def _row_to_dict(row) -> dict:
    d = dict(row)
    for k in ("fields_json", "icd_json"):
        if isinstance(d.get(k), str):
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


def _audit_row_to_dict(row) -> dict:
    d = dict(row)
    if isinstance(d.get("detail"), str):
        try:
            d["detail"] = json.loads(d["detail"])
        except Exception:
            pass
    return d
