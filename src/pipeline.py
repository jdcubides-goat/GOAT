from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from collections import Counter

from stepxml_extract import iter_products_from_file


def discover_xml_files(xml_dir: Path) -> List[Path]:
    files = sorted(xml_dir.rglob("*.xml")) + sorted(xml_dir.rglob("*.XML"))
    return files


def guess_file_type(file_name: str) -> str:
    n = file_name.lower()
    if "pph" in n:
        return "PPH"
    if "product" in n:
        return "PRODUCT_SAMPLE"
    return "UNKNOWN"


def summarize_file(xml_path: Path, product_limit_for_sample: int = 10) -> Dict[str, Any]:
    product_count = 0
    sample = []
    attr_counter = Counter()

    for prod in iter_products_from_file(xml_path):
        product_count += 1

        # sample
        if len(sample) < product_limit_for_sample:
            sample.append({
                "product_id": prod["product_id"],
                "name": prod["name"],
                "user_type": prod["user_type"],
                "parent_id": prod["parent_id"],
            })

        # AttributeID frequency
        for aid, vals in prod["values"].items():
            attr_counter[aid] += len(vals)
            
    top_attr_ids = attr_counter.most_common(25)

    summary = {
        "file": xml_path.name,
        "path": str(xml_path),
        "size_bytes": xml_path.stat().st_size,
        "file_type_guess": guess_file_type(xml_path.name),
        "products_total": product_count,
        "products_sample": sample,
        "attribute_ids_top": top_attr_ids,
    }
    return summary


def run(xml_dir: str, out_dir: str = "outputs") -> None:
    xml_root = Path(xml_dir)
    if not xml_root.exists():
        raise FileNotFoundError(f"No existe: {xml_dir}")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = discover_xml_files(xml_root)
    if not files:
        print("No se encontraron XML en:", xml_dir)
        return

    all_results = []
    for f in files:
        print("Procesando:", f.name)
        summary = summarize_file(f)

        result = {
            "summary": summary,
        }
        all_results.append(result)

        (out / f"{f.stem}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    (out / "run.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("Listo. Salidas en:", out_dir)
