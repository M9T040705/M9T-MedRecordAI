"""ICD-10 校验器单测。"""
from app.icd.icd_validator import validate_icd


def test_valid_dictionary_hit():
    r = validate_icd("I10")
    assert r["valid_format"] is True
    assert r["in_dictionary"] is True
    assert r["name"] == "原发性高血压"
    assert r["matched"] is True


def test_valid_with_decimal():
    r = validate_icd("e11.9")   # 小写应归一化
    assert r["valid_format"] is True
    assert r["code"] == "E11.9"
    assert r["in_dictionary"] is True


def test_invalid_format():
    for bad in ("I", "I1", "I100", "11.2", "AB12", "I1.234"):
        r = validate_icd(bad)
        assert r["valid_format"] is False, f"{bad} 应为非法格式"


def test_not_in_dictionary_gets_suggestion():
    r = validate_icd("I12.9")   # 不在字典，但有近邻
    assert r["valid_format"] is True
    assert r["in_dictionary"] is False
    assert r["suggestion"] != ""


def test_empty_code():
    r = validate_icd("")
    assert r["valid_format"] is False
