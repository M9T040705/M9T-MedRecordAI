"""抽取融合管道：LLM 优先、规则补位，输出带置信度的结构化结果 + ICD 校验。

流程：解析文本 → LLM 抽取（在线）→ 规则抽取 → 逐字段融合
（LLM 值非空优先，规则值补空缺）→ ICD-10 校验 → 汇总。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .fields import FIELD_KEYS
from .llm_extractor import extract_by_llm
from .rule_extractor import extract_by_rules
from ..icd.icd_validator import validate_icd


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


def extract_fields(text: str, prefer_llm: bool = True) -> ExtractionResult:
    rule_fields = extract_by_rules(text)
    if prefer_llm:
        llm_fields = extract_by_llm(text)
        mode = "llm+rule" if any(llm_fields.values()) else "rule"
    else:
        llm_fields = {}
        mode = "rule"
    merged = _merge(llm_fields, rule_fields)
    missing = [k for k, f in merged.items() if not f.value]

    icd_value = merged["main_icd"].value
    icd_check = validate_icd(icd_value) if icd_value else {
        "code": "", "valid_format": False, "in_dictionary": False,
        "name": "", "suggestion": "未抽取到 ICD 编码", "matched": False,
    }
    return ExtractionResult(
        fields=[merged[k] for k in FIELD_KEYS],
        icd_check=icd_check,
        mode=mode,
        missing=missing,
    )
