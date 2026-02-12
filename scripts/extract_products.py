from __future__ import annotations

import argparse
from pathlib import Path

from stepxml.product_extractor import write_products_jsonl


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Extract Product headers from STEP XML into JSONL.")
    p.add_argument("--xml", required=True, help="Path to STEP XML file")
    p.add_argument("--out", required=True, help="Output JSONL path")
    p.add_argument("--max-products", type=int, default=200, help="Max products to extract (default: 200)")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    xml_path = Path(args.xml)
    out_path = Path(args.out)

    n = write_products_jsonl(xml_path, out_path, max_products=args.max_products)
    print(f"Extracted {n} products -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
