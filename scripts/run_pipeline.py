"""批量离线处理管道：解析 data/samples 全部样例 → 抽取 → ICD 校验 → outputs/result.json。

用法：python scripts/run_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings                       # noqa: E402
from app.extractor.pipeline import extract_fields       # noqa: E402
from app.parser.base import parse_document              # noqa: E402

TEXT_FORMATS = {".txt", ".md", ".pdf", ".docx", ".xlsx"}


def main() -> None:
    files = sorted(f for f in settings.samples_dir.iterdir() if f.suffix in TEXT_FORMATS)
    print(f"待处理样例：{len(files)} 份\n")
    results = []
    for f in files:
        try:
            doc = parse_document(f)
        except Exception as e:
            results.append({"file": f.name, "status": "parse_error", "error": str(e)})
            print(f"  [解析失败] {f.name}: {e}")
            continue
        text = doc.text + "\n" + doc.table_text()
        ext = extract_fields(text, prefer_llm=not settings.offline)
        fields = {x.key: x.value for x in ext.fields}
        results.append({
            "file": f.name, "format": doc.format, "status": "ok",
            "mode": ext.mode, "scanned": doc.scanned,
            "fields": fields,
            "missing": ext.missing,
            "icd_check": ext.icd_check,
            "confidence": round(sum(x.confidence for x in ext.fields if x.value) /
                                max(1, sum(1 for x in ext.fields if x.value)), 2),
        })
        miss = "、".join(ext.missing) if ext.missing else "无"
        print(f"  [OK] {f.name:<16} 模式={ext.mode:<8} 缺失=[{miss}]")

    settings.outputs_dir.mkdir(exist_ok=True)
    out = settings.outputs_dir / "result.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n完成：{ok}/{len(results)} 份成功 → {out}")


if __name__ == "__main__":
    main()
