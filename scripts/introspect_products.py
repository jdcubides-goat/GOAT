from __future__ import annotations

import argparse
from pathlib import Path

from stepxml.product_introspect import write_introspection_json


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Introspect inner structure of Product nodes in STEP XML.")
    p.add_argument("--xml", required=True, help="Path to STEP XML file")
    p.add_argument("--out", required=True, help="Output JSON path")
    p.add_argument("--max-products", type=int, default=5, help="How many products to introspect")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    n = write_introspection_json(Path(args.xml), Path(args.out), max_products=args.max_products)
    print(f"Introspected {n} products -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
