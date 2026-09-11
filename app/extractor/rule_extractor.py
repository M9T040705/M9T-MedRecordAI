"""规则抽取器：正则 + 词表抽取病案首页 15 类字段（离线可用，可解释、可审计）。

每个字段返回 {"value": ..., "confidence": 0~1, "source": "regex|infer|none"}。
日期类字段统一归一化为 YYYY-MM-DD；住院天数可由入出院日期推算。
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List

from .fields import FIELD_KEYS, field_label

DATE_PAT = re.compile(r"(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?")
DATE_LONG_PAT = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")

DEPT_WORDS = [
    "心血管内科", "神经内科", "呼吸内科", "消化内科", "内分泌科", "肾内科", "血液内科",
    "普外科", "骨科", "泌尿外科", "神经外科", "胸外科", "妇产科", "儿科", "眼科", "耳鼻喉科",
    "口腔科", "皮肤科", "急诊科", "重症医学科", "肿瘤科", "康复医学科", "感染科", "中医科",
]


def _norm_date(raw: str) -> str:
    m = DATE_PAT.search(raw)
    if not m:
        return raw.strip()
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _days_between(a: str, b: str) -> int | None:
    try:
        d1 = date.fromisoformat(a)
        d2 = date.fromisoformat(b)
        return (d2 - d1).days + 1
    except Exception:
        return None


class RuleExtractor:
    def __init__(self):
        self.patterns = self._build_patterns()

    def _build_patterns(self) -> Dict[str, re.Pattern]:
        def kv(*keys: str):
            # 注意：分隔符后只允许空格/制表符（[ \t]*），禁止 \s（会跨行吞内容）
            return re.compile(rf"(?:{'|'.join(keys)})[:：][ \t]*([^\n|，。;；]+)")

        return {
            "record_no": kv("病案号", "住院号", "病历号"),
            "name": kv("姓名"),
            "gender": kv("性别"),
            "birth_date": kv("出生日期", "出生年月", "生日"),
            "admission_date": kv("入院日期", "入院时间", "住院日期"),
            "discharge_date": kv("出院日期", "出院时间"),
            "admission_dept": kv("入院科室"),
            "discharge_dept": kv("出院科室"),
            "main_diagnosis": kv("主要诊断", "出院诊断", "入院诊断"),
            "main_icd": re.compile(r"(?:ICD[-－]?10|ICD|主要诊断.*?编码|疾病编码)[:：]?[ \t]*([A-Za-z]\d{2}(?:\.\d{1,2})?)"),
            "secondary_diagnosis": kv("次要诊断", "其他诊断", "合并诊断"),
            "surgery": kv("手术操作", "手术名称", "主要手术", "操作名称"),
            "attending_doctor": kv("主治医师", "经治医师", "主管医师", "主任医师"),
            "hospital_days": re.compile(r"住院天数[:：]?\s*(\d{1,3})"),
            "payment_type": kv("费用类别", "医疗付费方式", "费用类型"),
        }

    def extract(self, text: str) -> Dict[str, dict]:
        result = {k: {"value": None, "confidence": 0.0, "source": "none"} for k in FIELD_KEYS}
        # 1) 正则主抽取
        for key, pat in self.patterns.items():
            m = pat.search(text)
            if not m:
                continue
            value = m.group(1).strip()
            if key in ("admission_date", "discharge_date", "birth_date"):
                value = _norm_date(value)
            if key == "main_icd":
                value = value.upper()
            result[key] = {"value": value, "confidence": 0.95, "source": "regex"}

        # 2) 性别/费用类别枚举校验（正则可能抓错）
        if result["gender"]["value"] not in ("男", "女"):
            result["gender"] = {"value": None, "confidence": 0.0, "source": "none"}
        if result["payment_type"]["value"] and result["payment_type"]["value"] not in ("医保", "自费", "公费", "商保"):
            result["payment_type"]["confidence"] = 0.5

        # 3) 科室词表兜底（当字段缺失时）
        for key in ("admission_dept", "discharge_dept"):
            if result[key]["value"]:
                continue
            for word in DEPT_WORDS:
                if word in text:
                    result[key] = {"value": word, "confidence": 0.6, "source": "infer"}
                    break

        # 4) 住院天数推算
        if not result["hospital_days"]["value"]:
            a = result["admission_date"]["value"]
            b = result["discharge_date"]["value"]
            if a and b:
                days = _days_between(a, b)
                if days and days > 0:
                    result["hospital_days"] = {"value": str(days), "confidence": 0.8, "source": "infer"}
        else:
            result["hospital_days"]["value"] = str(int(result["hospital_days"]["value"]))

        return result


def extract_by_rules(text: str) -> Dict[str, dict]:
    return RuleExtractor().extract(text)
