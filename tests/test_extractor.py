"""规则抽取器单测（覆盖病案首页 15 字段）。"""
from app.extractor.rule_extractor import RuleExtractor

SAMPLE = """病案号: 20260001
姓名: 张伟
性别: 男
出生日期: 1985-03-12
入院日期: 2026-05-10
出院日期: 2026-05-18
入院科室: 心血管内科
出院科室: 心血管内科
主要诊断: 原发性高血压
主要诊断ICD编码: I10
次要诊断: 2型糖尿病
手术操作: 冠状动脉造影术
主治医师: 李梅
住院天数: 9
费用类别: 医保
"""


def test_extract_all_fields():
    r = RuleExtractor().extract(SAMPLE)
    assert r["record_no"]["value"] == "20260001"
    assert r["name"]["value"] == "张伟"
    assert r["gender"]["value"] == "男"
    assert r["birth_date"]["value"] == "1985-03-12"
    assert r["admission_date"]["value"] == "2026-05-10"
    assert r["discharge_date"]["value"] == "2026-05-18"
    assert r["admission_dept"]["value"] == "心血管内科"
    assert r["discharge_dept"]["value"] == "心血管内科"
    assert r["main_diagnosis"]["value"] == "原发性高血压"
    assert r["main_icd"]["value"] == "I10"
    assert r["secondary_diagnosis"]["value"] == "2型糖尿病"
    assert r["surgery"]["value"] == "冠状动脉造影术"
    assert r["attending_doctor"]["value"] == "李梅"
    assert r["hospital_days"]["value"] == "9"
    assert r["payment_type"]["value"] == "医保"
    # 全字段都有置信度
    assert all(v["confidence"] > 0 for v in r.values())


def test_hospital_days_inferred_from_dates():
    text = SAMPLE.replace("住院天数: 9", "住院天数: ")
    r = RuleExtractor().extract(text)
    assert r["hospital_days"]["value"] == "9"
    assert r["hospital_days"]["source"] == "infer"


def test_date_normalization():
    text = SAMPLE.replace("1985-03-12", "1985年3月12日")
    r = RuleExtractor().extract(text)
    assert r["birth_date"]["value"] == "1985-03-12"


def test_colon_variant():
    text = SAMPLE.replace(": ", "：")
    r = RuleExtractor().extract(text)
    assert r["name"]["value"] == "张伟"


def test_dept_wordlist_fallback():
    text = "病案号: X1\n姓名: 王芳\n性别: 女\n心血管内科\n主要诊断: 肺炎\n主要诊断ICD编码: J18.9\n费用类别: 医保"
    r = RuleExtractor().extract(text)
    assert r["admission_dept"]["value"] == "心血管内科"
    assert r["admission_dept"]["source"] == "infer"
