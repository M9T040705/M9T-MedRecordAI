"""病案首页 15 类核心字段定义（对应简历"开发病案 15 类字段抽取模块"）。"""
from __future__ import annotations

from typing import List

FIELD_DEFS: List[dict] = [
    {"key": "record_no",        "label": "病案号",          "type": "str"},
    {"key": "name",             "label": "姓名",            "type": "str"},
    {"key": "gender",           "label": "性别",            "type": "enum", "enum": ["男", "女"]},
    {"key": "birth_date",       "label": "出生日期",        "type": "date"},
    {"key": "admission_date",   "label": "入院日期",        "type": "date"},
    {"key": "discharge_date",   "label": "出院日期",        "type": "date"},
    {"key": "admission_dept",   "label": "入院科室",        "type": "str"},
    {"key": "discharge_dept",   "label": "出院科室",        "type": "str"},
    {"key": "main_diagnosis",   "label": "主要诊断",        "type": "str"},
    {"key": "main_icd",         "label": "主要诊断ICD编码", "type": "icd"},
    {"key": "secondary_diagnosis", "label": "次要诊断",     "type": "str"},
    {"key": "surgery",          "label": "手术操作",        "type": "str"},
    {"key": "attending_doctor", "label": "主治医师",        "type": "str"},
    {"key": "hospital_days",    "label": "住院天数",        "type": "int"},
    {"key": "payment_type",     "label": "费用类别",        "type": "enum", "enum": ["医保", "自费", "公费", "商保"]},
]

FIELD_LABELS: dict = {f["key"]: f["label"] for f in FIELD_DEFS}
FIELD_KEYS: List[str] = [f["key"] for f in FIELD_DEFS]


def field_label(key: str) -> str:
    return FIELD_LABELS.get(key, key)
