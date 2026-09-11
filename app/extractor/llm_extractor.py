"""LLM 抽取器：大模型从病案首页文本中抽取 15 类字段（结构化 JSON）。

- 无 LLM Key 时返回空结果（由融合管道降级到规则抽取）；
- 输出字段校验：非法枚举、日期格式由 postprocess 清洗。
"""
from __future__ import annotations

import re
from typing import Dict

from ..config import settings
from ..llm_client import get_llm_client
from .fields import FIELD_KEYS, field_label

_EXTRACT_PROMPT = """你是病案信息抽取引擎。从下列病案首页文本中抽取字段，只输出 JSON 对象，键名必须严格使用以下 15 个：
{keys}

规则：
- 日期统一为 YYYY-MM-DD 格式；
- gender 只能是 男/女；payment_type 只能是 医保/自费/公费/商保；
- main_icd 是 ICD-10 编码，格式如 I10、E11.9；
- 无法确定的字段值为空字符串 ""；
- 不要编造文本中不存在的信息。

病案文本：
{text}
"""


def _postprocess(fields: dict) -> dict:
    out = {}
    for key in FIELD_KEYS:
        v = fields.get(key)
        if v is None:
            v = ""
        v = str(v).strip()
        if key == "gender" and v not in ("男", "女"):
            v = ""
        if key == "payment_type" and v and v not in ("医保", "自费", "公费", "商保"):
            v = ""
        if key in ("admission_date", "discharge_date", "birth_date"):
            m = re.search(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})", v)
            if m:
                v = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            else:
                v = ""
        if key == "main_icd":
            v = v.upper()
        out[key] = v
    return out


def extract_by_llm(text: str) -> Dict[str, str]:
    """返回 {field_key: value}；无 Key 或解析失败返回全空。"""
    client = get_llm_client()
    if client is None:
        return {k: "" for k in FIELD_KEYS}
    keys_desc = ", ".join(f"{k}({field_label(k)})" for k in FIELD_KEYS)
    try:
        obj = client.extract_json([
            {"role": "system", "content": "你是严谨的病案结构化抽取引擎，只输出 JSON。"},
            {"role": "user", "content": _EXTRACT_PROMPT.format(keys=keys_desc, text=text[:6000])},
        ])
    except Exception:
        return {k: "" for k in FIELD_KEYS}
    if not isinstance(obj, dict):
        return {k: "" for k in FIELD_KEYS}
    return _postprocess(obj)
