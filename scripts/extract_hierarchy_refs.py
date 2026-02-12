from __future__ import annotations

import argparse
import json
from pathlib import Path

from stepxml.product_flatten import iter_product_meta


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract hierarchy references from Products (ParentID + ClassificationReferences).")
    p.add_argument("--xml", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-products", type=int, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for meta in iter_product_meta(args.xml, max_products=args.max_products):
            row = {
                "product_id": meta.product_id,
                "product_name": meta.product_name,
                "parent_id": meta.parent_id,
                "classification_refs": meta.classifications,
                "cross_references": meta.cross_references,
                "resolved_hierarchy": None,  # luego lo llenamos con el diccionario de clasificaciones
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} product hierarchy refs -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
