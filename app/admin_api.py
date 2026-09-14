"""管理后台 API：抽取模板、ICD编码库、术语词典的 REST 接口。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from . import admin_db

router = APIRouter(prefix="/api/admin", tags=["管理后台"])


# ==================== Schema ====================

class TemplateField(BaseModel):
    name: str
    label: str
    type: str = "string"
    required: bool = False
    description: str = ""


class TemplateCreate(BaseModel):
    name: str
    doc_type: str
    description: str = ""
    fields: List[TemplateField] = []
    is_active: int = 1


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    doc_type: Optional[str] = None
    description: Optional[str] = None
    fields: Optional[List[TemplateField]] = None
    is_active: Optional[int] = None


class IcdCreate(BaseModel):
    code: str
    name: str
    category: str = ""
    description: str = ""
    is_active: int = 1


class IcdUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class TermCreate(BaseModel):
    term: str
    standard_term: str
    term_type: str = "synonym"
    description: str = ""
    is_active: int = 1


class TermUpdate(BaseModel):
    term: Optional[str] = None
    standard_term: Optional[str] = None
    term_type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


# ==================== 抽取模板 ====================

@router.get("/templates")
def list_templates(
    page: int = 1,
    page_size: int = 20,
    doc_type: str = "",
    is_active: int = -1,
    keyword: str = "",
):
    """抽取模板列表。"""
    active_param = None if is_active < 0 else is_active
    offset = (page - 1) * page_size
    items = admin_db.list_templates(doc_type=doc_type or None, is_active=active_param,
                                     keyword=keyword, limit=page_size, offset=offset)
    total = admin_db.count_templates(doc_type=doc_type or None, is_active=active_param, keyword=keyword)
    return {"total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size, "items": items}


@router.get("/templates/{template_id}")
def get_template(template_id: int):
    """获取单个抽取模板。"""
    tpl = admin_db.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    return tpl


@router.post("/templates")
def create_template(req: TemplateCreate):
    """创建抽取模板。"""
    try:
        tid = admin_db.create_template(req.dict())
        return {"ok": True, "id": tid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败：{e}")


@router.put("/templates/{template_id}")
def update_template(template_id: int, req: TemplateUpdate):
    """更新抽取模板。"""
    data = {k: v for k, v in req.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    ok = admin_db.update_template(template_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在或更新失败")
    return {"ok": True}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int):
    """删除抽取模板。"""
    ok = admin_db.delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="模板不存在")
    return {"ok": True}


# ==================== ICD 编码库 ====================

@router.get("/icd-codes")
def list_icd_codes(
    page: int = 1,
    page_size: int = 20,
    category: str = "",
    is_active: int = -1,
    keyword: str = "",
):
    """ICD编码列表。"""
    active_param = None if is_active < 0 else is_active
    offset = (page - 1) * page_size
    items = admin_db.list_icd_codes(category=category or None, is_active=active_param,
                                     keyword=keyword, limit=page_size, offset=offset)
    total = admin_db.count_icd_codes(category=category or None, is_active=active_param, keyword=keyword)
    return {"total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size, "items": items}


@router.get("/icd-codes/search")
def search_icd_codes(q: str, limit: int = 10):
    """搜索ICD编码（按编码或名称模糊匹配）。"""
    if not q:
        return {"items": []}
    items = admin_db.search_icd(q, limit=limit)
    return {"items": items}


@router.get("/icd-codes/{icd_id}")
def get_icd_code(icd_id: int):
    """获取单个ICD编码。"""
    item = admin_db.get_icd_code(icd_id)
    if not item:
        raise HTTPException(status_code=404, detail="ICD编码不存在")
    return item


@router.post("/icd-codes")
def create_icd_code(req: IcdCreate):
    """创建ICD编码。"""
    try:
        iid = admin_db.create_icd_code(req.dict())
        return {"ok": True, "id": iid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败：{e}")


@router.put("/icd-codes/{icd_id}")
def update_icd_code(icd_id: int, req: IcdUpdate):
    """更新ICD编码。"""
    data = {k: v for k, v in req.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    ok = admin_db.update_icd_code(icd_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="ICD编码不存在或更新失败")
    return {"ok": True}


@router.delete("/icd-codes/{icd_id}")
def delete_icd_code(icd_id: int):
    """删除ICD编码。"""
    ok = admin_db.delete_icd_code(icd_id)
    if not ok:
        raise HTTPException(status_code=404, detail="ICD编码不存在")
    return {"ok": True}


# ==================== 术语词典 ====================

@router.get("/terms")
def list_terms(
    page: int = 1,
    page_size: int = 20,
    term_type: str = "",
    is_active: int = -1,
    keyword: str = "",
):
    """术语列表。"""
    active_param = None if is_active < 0 else is_active
    offset = (page - 1) * page_size
    items = admin_db.list_terms(term_type=term_type or None, is_active=active_param,
                                 keyword=keyword, limit=page_size, offset=offset)
    total = admin_db.count_terms(term_type=term_type or None, is_active=active_param, keyword=keyword)
    return {"total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size, "items": items}


@router.get("/terms/{term_id}")
def get_term(term_id: int):
    """获取单个术语。"""
    item = admin_db.get_term(term_id)
    if not item:
        raise HTTPException(status_code=404, detail="术语不存在")
    return item


@router.post("/terms")
def create_term(req: TermCreate):
    """创建术语。"""
    try:
        tid = admin_db.create_term(req.dict())
        return {"ok": True, "id": tid}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建失败：{e}")


@router.put("/terms/{term_id}")
def update_term(term_id: int, req: TermUpdate):
    """更新术语。"""
    data = {k: v for k, v in req.dict().items() if v is not None}
    if not data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    ok = admin_db.update_term(term_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="术语不存在或更新失败")
    return {"ok": True}


@router.delete("/terms/{term_id}")
def delete_term(term_id: int):
    """删除术语。"""
    ok = admin_db.delete_term(term_id)
    if not ok:
        raise HTTPException(status_code=404, detail="术语不存在")
    return {"ok": True}


# ==================== 统计 ====================

@router.get("/stats")
def admin_stats():
    """管理后台统计数据。"""
    return {
        "templates": admin_db.count_templates(),
        "icd_codes": admin_db.count_icd_codes(),
        "terms": admin_db.count_terms(),
        "active_templates": admin_db.count_templates(is_active=1),
        "active_icd_codes": admin_db.count_icd_codes(is_active=1),
        "active_terms": admin_db.count_terms(is_active=1),
    }
