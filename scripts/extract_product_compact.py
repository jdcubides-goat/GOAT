from __future__ import annotations

import argparse
from pathlib import Path

from stepxml.product_compact import write_compact_jsonl


def parse_args():
    p = argparse.ArgumentParser(description="Extract 1-row-per-product compact dataset (hierarchy + minimal attrs).")
    p.add_argument("--xml", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-products", type=int, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    n = write_compact_jsonl(Path(args.xml), Path(args.out), max_products=args.max_products)
    print(f"Wrote {n} products -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
