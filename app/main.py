"""医疗病案智能编码系统 —— FastAPI 服务入口。

完整业务闭环：
- 认证：JWT 登录 + 科室级权限隔离
- 文档解析：7种格式（PDF/DOCX/PPTX/XLSX/TXT/图片/HTML）+ OCR + 语义分片
- 智能抽取：LLM+规则双引擎融合，15字段抽取 + ICD-10 三层校验
- 工作流：待抽取→已抽取→复核中→已确认→已归档
- 人工复核：修改字段、提交复核、确认、驳回、归档
- 审计日志：所有关键操作留痕
- 统计仪表盘：抽取量、状态分布、ICD分布、每日趋势
- 批量处理：多文件上传、异步处理
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .auth import USERS, authenticate, can_view, get_current_user, require_departments
from .chunker import chunk_document
from .config import settings
from .db import (STATUS_ARCHIVED, STATUS_CONFIRMED, STATUS_EXTRACTED,
                 STATUS_REVIEWING, STATUS_TRANSITIONS, VALID_STATUSES,
                 add_audit_log, count_records, get_backend, get_record,
                 get_stats, init_db, list_audit_logs, list_records,
                 save_record, update_record)
from .extractor.pipeline import extract_fields
from .llm_client import get_llm_client
from .parser.base import ParseError, parse_document
from .schemas import (AuditLogItem, AuditLogListResponse, BatchItemResult,
                      BatchResponse, ExtractRequest, ExtractResponse,
                      FieldOut, HealthResponse, IcdOut, LoginRequest,
                      ParseResponse, ProcessResponse, RecordDetail,
                      RecordItem, RecordListResponse, ReviewRequest,
                      ReviewResponse, StatsResponse, TokenResponse)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .admin_db import init_admin_db
    init_admin_db()
    settings.outputs_dir.mkdir(exist_ok=True)
    yield


app = FastAPI(title="医疗病案智能编码系统", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 注册管理后台路由
from .admin_api import router as admin_router
app.include_router(admin_router)

EXTRACT_ALLOWED = require_departments("病案科", "医务部", "医保办")
ADMIN_ONLY = require_departments("医务部")


def _client_ip(request: Request) -> str:
    """获取客户端IP。"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _log_action(user: dict, action: str, target_type: str = "",
                target_id: str = "", detail: Optional[dict] = None,
                ip: str = ""):
    """记录审计日志（失败不阻断主流程）。"""
    try:
        add_audit_log(
            username=user.get("sub", ""),
            department=user.get("department", ""),
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=detail or {},
            ip_address=ip,
        )
    except Exception:
        pass


def _fields_out(result) -> list[FieldOut]:
    return [FieldOut(key=f.key, label=f.label, value=f.value,
                     confidence=f.confidence, source=f.source) for f in result.fields]


def _icd_out(icd_check: dict) -> IcdOut:
    return IcdOut(
        code=icd_check.get("code", ""),
        valid_format=icd_check.get("valid_format", False),
        in_dictionary=icd_check.get("in_dictionary", False),
        name=icd_check.get("name", ""),
        suggestion=icd_check.get("suggestion", ""),
        matched=icd_check.get("matched", False),
    )


def _record_to_item(r: dict) -> RecordItem:
    return RecordItem(
        id=r["id"], doc_name=r["doc_name"], department=r["department"],
        mode=r["mode"], confidence=r["confidence"], status=r["status"],
        created_at=str(r.get("created_at", "")),
        updated_at=str(r.get("updated_at", "") or ""),
        reviewer=r.get("reviewer", "") or "",
        confirmed_by=r.get("confirmed_by", "") or "",
        fields_json=r.get("fields_json") or {},
        icd_json=r.get("icd_json") or {},
    )


def _record_to_detail(r: dict) -> RecordDetail:
    item = _record_to_item(r)
    return RecordDetail(
        **item.model_dump(),
        original_text=r.get("original_text", "") or "",
        reviewed_at=str(r.get("reviewed_at", "") or None),
        confirmed_at=str(r.get("confirmed_at", "") or None),
    )


# ============================================================
# 认证接口
# ============================================================
@app.post("/api/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request):
    token = authenticate(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user = USERS[req.username]
    _log_action({"sub": req.username, "department": user["department"]},
                "login", ip=_client_ip(request))
    return TokenResponse(token=token, username=req.username,
                         department=user["department"], role=user["role"])


@app.get("/api/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    """获取当前用户信息。"""
    return {"username": user["sub"], "department": user["department"], "role": user["role"]}


# ============================================================
# 文档解析接口
# ============================================================
@app.post("/api/documents/parse", response_model=ParseResponse)
async def parse_doc(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    t0 = time.time()
    suffix = Path(file.filename).suffix
    tmp = settings.outputs_dir / f"upload_{int(t0)}{suffix}"
    tmp.write_bytes(await file.read())
    try:
        doc = parse_document(tmp)
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        tmp.unlink(missing_ok=True)
    doc.doc_name = file.filename
    chunks = chunk_document(doc)
    return ParseResponse(
        doc_name=doc.doc_name, format=doc.format,
        text_preview=doc.text[:200], text_length=len(doc.text),
        tables_count=len(doc.tables), scanned=doc.scanned,
        chunk_count=len(chunks),
    )


# ============================================================
# 病案字段抽取接口
# ============================================================
@app.post("/api/documents/extract", response_model=ExtractResponse)
def extract_doc(req: ExtractRequest, user: dict = Depends(EXTRACT_ALLOWED)):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text 不能为空")
    result = extract_fields(req.text, prefer_llm=not settings.offline)
    confs = [f.confidence for f in result.fields if f.value]
    return ExtractResponse(
        fields=_fields_out(result),
        icd_check=_icd_out(result.icd_check),
        mode=result.mode,
        missing=result.missing,
        field_count=sum(1 for f in result.fields if f.value),
        confidence_avg=round(sum(confs) / len(confs), 2) if confs else 0.0,
    )


# ============================================================
# 一站式处理（解析+抽取+落库）
# ============================================================
@app.post("/api/documents/process", response_model=ProcessResponse)
async def process_doc(file: UploadFile = File(...),
                      template_id: Optional[int] = Form(None),
                      template_name: Optional[str] = Form(None),
                      user: dict = Depends(EXTRACT_ALLOWED),
                      request: Request = None):
    t0 = time.time()
    suffix = Path(file.filename).suffix
    tmp = settings.outputs_dir / f"proc_{int(t0)}{suffix}"
    tmp.write_bytes(await file.read())
    try:
        doc = parse_document(tmp)
    except ParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        tmp.unlink(missing_ok=True)
    doc.doc_name = file.filename

    if doc.scanned and not doc.text:
        raise HTTPException(status_code=400, detail="扫描件 OCR 未产出文本，请检查 PaddleOCR 安装")

    chunks = chunk_document(doc)
    full_text = doc.text + "\n" + doc.table_text()
    extract = extract_fields(full_text, prefer_llm=not settings.offline,
                             template_id=template_id, template_name=template_name)
    confs = [f.confidence for f in extract.fields if f.value]

    record_id = save_record({
        "doc_name": doc.doc_name,
        "department": user["department"],
        "fields": [f.__dict__ for f in extract.fields],
        "icd": extract.icd_check,
        "original_text": full_text[:5000],
        "mode": extract.mode,
        "confidence": round(sum(confs) / len(confs), 2) if confs else 0.0,
        "status": STATUS_EXTRACTED,
    })

    _log_action(user, "create_record", "record", str(record_id),
                {"doc_name": doc.doc_name, "mode": extract.mode},
                _client_ip(request) if request else "")

    parse_resp = ParseResponse(
        doc_name=doc.doc_name, format=doc.format,
        text_preview=doc.text[:200], text_length=len(doc.text),
        tables_count=len(doc.tables), scanned=doc.scanned, chunk_count=len(chunks),
    )
    extract_resp = ExtractResponse(
        fields=_fields_out(extract), icd_check=_icd_out(extract.icd_check),
        mode=extract.mode, missing=extract.missing,
        field_count=sum(1 for f in extract.fields if f.value),
        confidence_avg=round(sum(confs) / len(confs), 2) if confs else 0.0,
    )
    return ProcessResponse(record_id=record_id, doc_name=doc.doc_name,
                           parse=parse_resp, extract=extract_resp)


# ============================================================
# 记录管理接口
# ============================================================
@app.get("/api/records", response_model=RecordListResponse)
def records(status: Optional[str] = None, limit: int = 50, offset: int = 0,
            user: dict = Depends(get_current_user)):
    """记录列表（科室级可见性，支持状态筛选）。"""
    if status and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态：{status}，可选：{VALID_STATUSES}")
    dept = None if user["role"] == "admin" else user["department"]
    total = count_records(department=dept, status=status)
    rows = list_records(department=dept, status=status, limit=min(limit, 200), offset=offset)
    return RecordListResponse(total=total, items=[_record_to_item(r) for r in rows])


@app.get("/api/records/{record_id}", response_model=RecordDetail)
def record_detail(record_id: int, user: dict = Depends(get_current_user)):
    """记录详情（含原始文本、复核信息）。"""
    r = get_record(record_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"记录 {record_id} 不存在")
    if not can_view(user, r["department"]):
        raise HTTPException(status_code=403, detail="无权限查看其他科室记录")
    return _record_to_detail(r)


# ============================================================
# 人工复核接口（工作流核心）
# ============================================================
@app.post("/api/records/{record_id}/review", response_model=ReviewResponse)
def review_record(record_id: int, req: ReviewRequest,
                  user: dict = Depends(EXTRACT_ALLOWED), request: Request = None):
    """
    人工复核：修改字段 + 状态流转。

    action 可选：
    - submit_review：提交复核（已抽取 → 复核中）
    - confirm：确认归档（复核中/已抽取 → 已确认）
    - reject：驳回重抽（复核中 → 已抽取）
    - archive：归档（已确认 → 已归档）
    """
    r = get_record(record_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"记录 {record_id} 不存在")
    if not can_view(user, r["department"]):
        raise HTTPException(status_code=403, detail="无权限操作其他科室记录")

    current_status = r["status"]
    action = req.action

    # 状态流转映射
    action_to_status = {
        "submit_review": STATUS_REVIEWING,
        "confirm": STATUS_CONFIRMED,
        "reject": STATUS_EXTRACTED,
        "archive": STATUS_ARCHIVED,
    }
    if action not in action_to_status:
        raise HTTPException(status_code=400,
                            detail=f"无效操作：{action}，可选：{list(action_to_status.keys())}")

    new_status = action_to_status[action]
    # 验证状态流转是否合法
    allowed = STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in allowed and new_status != current_status:
        raise HTTPException(
            status_code=400,
            detail=f"状态流转不合法：{current_status} → {new_status}，"
                   f"当前状态允许流转到：{allowed or '（终态，不可流转）'}"
        )

    # 构建更新字段
    updates = {"status": new_status}
    detail = {"action": action, "from_status": current_status, "to_status": new_status}

    # 修改字段（如果有）
    if req.fields:
        fields_list = r.get("fields_json") or []
        if isinstance(fields_list, dict):
            fields_list = fields_list.get("fields", [])
        field_map = {f.get("key"): f for f in fields_list if isinstance(f, dict)}
        changed = []
        for f_update in req.fields:
            if f_update.key in field_map:
                old_val = field_map[f_update.key].get("value", "")
                field_map[f_update.key]["value"] = f_update.value
                field_map[f_update.key]["source"] = "manual"
                field_map[f_update.key]["confidence"] = 1.0
                changed.append({"key": f_update.key, "old": old_val, "new": f_update.value})
        updates["fields_json"] = fields_list
        detail["changed_fields"] = changed

    # 复核人/确认人
    if action in ("submit_review", "reject"):
        updates["reviewer"] = user["sub"]
        updates["reviewed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    elif action == "confirm":
        updates["confirmed_by"] = user["sub"]
        updates["confirmed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if not updates.get("reviewer"):
            updates["reviewer"] = user["sub"]

    if req.comment:
        detail["comment"] = req.comment

    # 执行更新
    ok = update_record(record_id, updates)
    if not ok:
        raise HTTPException(status_code=500, detail="更新失败")

    # 记录审计日志
    _log_action(user, f"review_{action}", "record", str(record_id), detail,
                _client_ip(request) if request else "")

    action_msgs = {
        "submit_review": "已提交复核",
        "confirm": "已确认归档",
        "reject": "已驳回，等待重新抽取",
        "archive": "已归档",
    }
    return ReviewResponse(record_id=record_id, status=new_status,
                          message=action_msgs.get(action, "操作成功"))


# ============================================================
# 审计日志接口
# ============================================================
@app.get("/api/audit-logs", response_model=AuditLogListResponse)
def audit_logs(username: Optional[str] = None, action: Optional[str] = None,
               limit: int = 100, offset: int = 0,
               user: dict = Depends(get_current_user)):
    """审计日志查询（管理员可见全部，普通用户仅见自己）。"""
    if user["role"] != "admin":
        username = user["sub"]
    rows = list_audit_logs(username=username, action=action, limit=min(limit, 500), offset=offset)
    items = [AuditLogItem(
        id=r["id"], username=r["username"], department=r["department"],
        action=r["action"], target_type=r.get("target_type", ""),
        target_id=r.get("target_id", ""), detail=r.get("detail") or {},
        ip_address=r.get("ip_address", ""), created_at=str(r["created_at"]),
    ) for r in rows]
    return AuditLogListResponse(total=len(items), items=items)


# ============================================================
# 统计仪表盘接口
# ============================================================
@app.get("/api/stats/overview", response_model=StatsResponse)
def stats_overview(user: dict = Depends(get_current_user)):
    """统计概览：总量、状态分布、平均置信度、ICD分布、每日趋势。"""
    dept = None if user["role"] == "admin" else user["department"]
    return get_stats(department=dept)


# ============================================================
# 批量处理接口
# ============================================================
@app.post("/api/documents/batch", response_model=BatchResponse)
async def batch_process(files: list[UploadFile] = File(...),
                        user: dict = Depends(EXTRACT_ALLOWED),
                        request: Request = None):
    """
    批量上传处理：多文件依次解析+抽取+落库。
    （轻量版同步处理，生产环境建议改为异步队列）
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="单次最多上传20个文件")

    t0 = time.time()
    task_id = str(uuid.uuid4())[:8]
    results = []
    success = 0
    failed = 0

    for file in files:
        try:
            suffix = Path(file.filename).suffix
            tmp = settings.outputs_dir / f"batch_{task_id}_{int(time.time()*1000)}{suffix}"
            tmp.write_bytes(await file.read())
            try:
                doc = parse_document(tmp)
            except ParseError as e:
                results.append(BatchItemResult(filename=file.filename, success=False, error=str(e)))
                failed += 1
                continue
            finally:
                tmp.unlink(missing_ok=True)

            doc.doc_name = file.filename
            if doc.scanned and not doc.text:
                results.append(BatchItemResult(filename=file.filename, success=False,
                                                error="扫描件OCR未产出文本"))
                failed += 1
                continue

            full_text = doc.text + "\n" + doc.table_text()
            extract = extract_fields(full_text, prefer_llm=not settings.offline)
            confs = [f.confidence for f in extract.fields if f.value]
            avg_conf = round(sum(confs) / len(confs), 2) if confs else 0.0

            record_id = save_record({
                "doc_name": doc.doc_name, "department": user["department"],
                "fields": [f.__dict__ for f in extract.fields],
                "icd": extract.icd_check, "original_text": full_text[:5000],
                "mode": extract.mode, "confidence": avg_conf, "status": STATUS_EXTRACTED,
            })
            results.append(BatchItemResult(
                filename=file.filename, success=True, record_id=record_id,
                field_count=sum(1 for f in extract.fields if f.value),
                confidence=avg_conf,
            ))
            success += 1
        except Exception as e:
            results.append(BatchItemResult(filename=file.filename, success=False, error=str(e)))
            failed += 1

    elapsed_ms = int((time.time() - t0) * 1000)
    _log_action(user, "batch_process", "batch", task_id,
                {"total": len(files), "success": success, "failed": failed},
                _client_ip(request) if request else "")

    return BatchResponse(task_id=task_id, total=len(files), success=success,
                         failed=failed, results=results, elapsed_ms=elapsed_ms)


# ============================================================
# 健康检查
# ============================================================
@app.get("/healthz", response_model=HealthResponse)
def healthz():
    return HealthResponse(
        status="ok",
        llm_online=get_llm_client() is not None,
        ocr_mode=settings.ocr_mode,
        db_store=get_backend(),
        parser_count=7,
    )
