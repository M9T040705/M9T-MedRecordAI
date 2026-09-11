"""API 请求/响应模型。"""
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


# ---------------- 认证 ----------------
class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    username: str
    department: str
    role: str


class UserInfo(BaseModel):
    username: str
    department: str
    role: str


# ---------------- 文档解析 ----------------
class ParseResponse(BaseModel):
    doc_name: str
    format: str
    text_preview: str
    text_length: int
    tables_count: int
    scanned: bool
    chunk_count: int


# ---------------- 字段抽取 ----------------
class ExtractRequest(BaseModel):
    text: str = Field(..., description="待抽取文本")


class FieldOut(BaseModel):
    key: str
    label: str
    value: str
    confidence: float
    source: str


class IcdOut(BaseModel):
    code: str
    valid_format: bool
    in_dictionary: bool
    name: str
    suggestion: str
    matched: bool


class ExtractResponse(BaseModel):
    fields: List[FieldOut]
    icd_check: IcdOut
    mode: str
    missing: List[str]
    field_count: int
    confidence_avg: float


class ProcessResponse(BaseModel):
    record_id: int
    doc_name: str
    parse: ParseResponse
    extract: ExtractResponse


# ---------------- 记录管理 ----------------
class RecordItem(BaseModel):
    id: int
    doc_name: str
    department: str
    mode: str
    confidence: float
    status: str
    created_at: str
    updated_at: Optional[str] = None
    reviewer: Optional[str] = ""
    confirmed_by: Optional[str] = ""
    fields_json: dict
    icd_json: dict


class RecordDetail(RecordItem):
    original_text: Optional[str] = ""
    reviewed_at: Optional[str] = None
    confirmed_at: Optional[str] = None


class RecordListResponse(BaseModel):
    total: int
    items: List[RecordItem]


# ---------------- 人工复核 ----------------
class ReviewFieldUpdate(BaseModel):
    """单个字段的修改。"""
    key: str
    value: str


class ReviewRequest(BaseModel):
    """人工复核请求：修改字段 + 提交复核状态。"""
    fields: Optional[List[ReviewFieldUpdate]] = Field(None, description="修改的字段列表")
    action: str = Field(..., description="操作：submit_review（提交复核）/ confirm（确认）/ reject（驳回重抽）/ archive（归档）")
    comment: Optional[str] = Field("", description="复核意见")


class ReviewResponse(BaseModel):
    record_id: int
    status: str
    message: str


# ---------------- 审计日志 ----------------
class AuditLogItem(BaseModel):
    id: int
    username: str
    department: str
    action: str
    target_type: str
    target_id: str
    detail: dict
    ip_address: str
    created_at: str


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogItem]


# ---------------- 统计仪表盘 ----------------
class StatusCount(BaseModel):
    pending: int = 0
    extracted: int = 0
    reviewing: int = 0
    confirmed: int = 0
    archived: int = 0


class IcdDistributionItem(BaseModel):
    label: str
    count: int


class DailyTrendItem(BaseModel):
    date: str
    count: int


class StatsResponse(BaseModel):
    total: int
    status_counts: Dict[str, int]
    avg_confidence: float
    icd_distribution: List[IcdDistributionItem]
    daily_trend: List[DailyTrendItem]


# ---------------- 批量处理 ----------------
class BatchItemResult(BaseModel):
    filename: str
    success: bool
    record_id: Optional[int] = None
    error: Optional[str] = None
    field_count: Optional[int] = None
    confidence: Optional[float] = None


class BatchResponse(BaseModel):
    task_id: str
    total: int
    success: int
    failed: int
    results: List[BatchItemResult]
    elapsed_ms: int


# ---------------- 健康检查 ----------------
class HealthResponse(BaseModel):
    status: str
    llm_online: bool
    ocr_mode: str
    db_store: str
    parser_count: int
