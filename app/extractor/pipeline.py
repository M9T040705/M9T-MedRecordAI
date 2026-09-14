"""抽取融合管道：LLM 优先、规则补位，输出带置信度的结构化结果 + ICD 校验。

流程：术语归一化 → 解析文本 → LLM 抽取（在线）→ 规则抽取 → 逐字段融合
（LLM 值非空优先，规则值补空缺）→ ICD-10 校验 → 汇总。

支持抽取模板：传入 template_id 或 template_name 时，使用模板中配置的字段列表，
替代默认的 15 个病案首页字段。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .fields import FIELD_KEYS
from .llm_extractor import extract_by_llm
from .rule_extractor import extract_by_rules
from ..icd.icd_validator import validate_icd


def _normalize_terms(text: str) -> str:
    """术语归一化：用术语词典中的标准术语替换非标准表述（同义词/缩写/别名/口语化）。"""
    try:
        from ..admin_db import get_all_term_mappings
        mappings = get_all_term_mappings()
        if not mappings:
            return text
        result = text
        for term, standard in mappings.items():
            if term and term in result:
                result = result.replace(term, standard)
        return result
    except Exception:
        return text


def _get_template_fields(template_id: Optional[int] = None, template_name: Optional[str] = None) -> Optional[List[str]]:
    """从数据库获取抽取模板的字段列表。"""
    try:
        from ..admin_db import get_template, get_template_by_name
        tpl = None
        if template_id:
            tpl = get_template(template_id)
        elif template_name:
            tpl = get_template_by_name(template_name)
        if tpl and tpl.get("fields_json"):
            return [f.get("name") for f in tpl["fields_json"] if f.get("name")]
    except Exception:
        pass
    return None


@dataclass
class FieldResult:
    key: str
    label: str
    value: str
    confidence: float
    source: str


@dataclass
class ExtractionResult:
    fields: List[FieldResult]
    icd_check: dict
    mode: str            # rule / llm+rule
    missing: List[str]

    def to_dict(self) -> dict:
        return {
            "fields": [f.__dict__ for f in self.fields],
            "icd_check": self.icd_check,
            "mode": self.mode,
            "missing": self.missing,
        }


def _merge(llm_fields: Dict[str, str], rule_fields: Dict[str, dict]) -> Dict[str, FieldResult]:
    merged = {}
    for key in FIELD_KEYS:
        label = _label(key)
        llm_v = (llm_fields or {}).get(key, "")
        rule_v = (rule_fields or {}).get(key, {})
        rule_val = rule_v.get("value") or ""
        rule_conf = rule_v.get("confidence", 0.0)
        rule_src = rule_v.get("source", "none")
        if llm_v:
            merged[key] = FieldResult(key, label, llm_v, 0.9, "llm")
        elif rule_val:
            merged[key] = FieldResult(key, label, rule_val, rule_conf, rule_src)
        else:
            merged[key] = FieldResult(key, label, "", 0.0, "none")
    return merged


def _label(key: str) -> str:
    from .fields import FIELD_LABELS
    return FIELD_LABELS.get(key, key)


def extract_fields(text: str, prefer_llm: bool = True,
                    template_id: Optional[int] = None,
                    template_name: Optional[str] = None) -> ExtractionResult:
    # 1. 术语归一化（同义词/缩写/别名 → 标准术语）
    normalized_text = _normalize_terms(text)

    # 2. 确定抽取字段列表（模板优先，否则用默认 15 字段）
    field_keys = _get_template_fields(template_id=template_id, template_name=template_name) or FIELD_KEYS

    # 3. 规则抽取 + LLM 抽取
    rule_fields = extract_by_rules(normalized_text)
    if prefer_llm:
        llm_fields = extract_by_llm(normalized_text)
        mode = "llm+rule" if any(llm_fields.values()) else "rule"
    else:
        llm_fields = {}
        mode = "rule"

    # 4. 逐字段融合
    merged = {}
    for key in field_keys:
        label = _label(key)
        llm_v = (llm_fields or {}).get(key, "")
        rule_v = (rule_fields or {}).get(key, {})
        rule_val = rule_v.get("value") or ""
        rule_conf = rule_v.get("confidence", 0.0)
        rule_src = rule_v.get("source", "none")
        if llm_v:
            merged[key] = FieldResult(key, label, llm_v, 0.9, "llm")
        elif rule_val:
            merged[key] = FieldResult(key, label, rule_val, rule_conf, rule_src)
        else:
            merged[key] = FieldResult(key, label, "", 0.0, "none")
    missing = [k for k, f in merged.items() if not f.value]

    # 5. ICD 校验
    icd_value = merged.get("main_icd", FieldResult("main_icd", "主要诊断ICD编码", "", 0, "none")).value
    icd_check = validate_icd(icd_value) if icd_value else {
        "code": "", "valid_format": False, "in_dictionary": False,
        "name": "", "suggestion": "未抽取到 ICD 编码", "matched": False,
    }
    return ExtractionResult(
        fields=[merged[k] for k in field_keys],
        icd_check=icd_check,
        mode=mode,
        missing=missing,
    )
