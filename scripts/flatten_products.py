from __future__ import annotations

import argparse
from pathlib import Path

from stepxml.product_flatten import (
    iter_product_flat_values,
    iter_product_meta,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Flatten STEP Products into JSONL outputs.")
    p.add_argument("--xml", required=True, help="Path to STEP XML file")
    p.add_argument("--out-values", required=True, help="Output JSONL for product attribute values")
    p.add_argument("--out-meta", required=True, help="Output JSONL for product meta (classifications/crossrefs)")
    p.add_argument("--max-products", type=int, default=None, help="Optional max products to process")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    xml_path = Path(args.xml)

    n_values = write_jsonl(
        iter_product_flat_values(xml_path, max_products=args.max_products),
        Path(args.out_values),
    )
    n_meta = write_jsonl(
        iter_product_meta(xml_path, max_products=args.max_products),
        Path(args.out_meta),
    )

    print(f"Wrote values: {n_values} -> {args.out_values}")
    print(f"Wrote meta:   {n_meta} -> {args.out_meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
