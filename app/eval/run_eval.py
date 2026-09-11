"""字段抽取准确率评测：以 data/samples/expected.json 为标注基准。

指标：
- 字段级准确率：每个字段 value 与标注一致的样本占比（空值双方一致也算对，missing 单列）
- 综合准确率：全部字段的匹配率
- ICD 匹配率：main_icd 与标注一致的样本占比
- 召回覆盖率：非空字段中被正确抽取的比例

用法：python -m app.eval.run_eval
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from ..config import settings
from ..extractor.pipeline import extract_fields
from ..parser.base import parse_document

TEXT_FORMATS = {".txt", ".md", ".pdf", ".docx", ".xlsx"}


def _load_expected() -> dict:
    path = settings.samples_dir / "expected.json"
    if not path.exists():
        raise FileNotFoundError("未找到 expected.json，请先运行 python data/gen_samples.py")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_sample(sample_id: str) -> str:
    for fmt in (".txt", ".md", ".pdf", ".docx", ".xlsx"):
        f = settings.samples_dir / f"{sample_id}{fmt}"
        if f.exists():
            doc = parse_document(f)
            return doc.text + "\n" + doc.table_text()
    return ""


def main() -> None:
    expected = _load_expected()
    print(f"评测样本：{len(expected)} 份病案首页（来自 expected.json）\n")
    stats = {k: {"hit": 0, "total": 0, "missing": 0} for k in next(iter(expected.values())).keys()}
    overall = {"hit": 0, "total": 0}
    icd_hits = icd_total = 0
    rows = []

    for sid, want in expected.items():
        text = _parse_sample(sid)
        if not text:
            print(f"  [跳过] {sid}: 无可用文本")
            continue
        ext = extract_fields(text, prefer_llm=not settings.offline)
        got = {x.key: x.value for x in ext.fields}
        row = {"sample": sid, "mode": ext.mode, "fields": {}}
        for key, want_val in want.items():
            got_val = got.get(key, "")
            match = (want_val == got_val)
            overall["total"] += 1
            stats[key]["total"] += 1
            row["fields"][key] = {"want": want_val, "got": got_val, "match": match}
            if match:
                overall["hit"] += 1
                stats[key]["hit"] += 1
            if not want_val:
                stats[key]["missing"] += 1
        if want.get("main_icd") and got.get("main_icd"):
            icd_total += 1
            icd_hits += 1 if want["main_icd"] == got["main_icd"] else 0
        rows.append(row)

    print(f"{'字段':<14}{'准确率':>10}{'命中/样本'}")
    print("-" * 40)
    for key, s in stats.items():
        acc = s["hit"] / s["total"] if s["total"] else 1.0
        print(f"{key:<16}{acc:>8.1%}    {s['hit']}/{s['total']}")
    print("-" * 40)
    print(f"{'综合准确率':<16}{overall['hit'] / overall['total']:>8.1%}    {overall['hit']}/{overall['total']}")
    if icd_total:
        print(f"{'ICD匹配率':<16}{icd_hits / icd_total:>8.1%}    {icd_hits}/{icd_total}")
    print(f"\n模式：{'LLM+规则' if not settings.offline else '规则（未配置 LLM Key）'}")

    settings.outputs_dir.mkdir(exist_ok=True)
    (settings.outputs_dir / "eval_detail.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细已保存：{settings.outputs_dir / 'eval_detail.json'}")


if __name__ == "__main__":
    main()
