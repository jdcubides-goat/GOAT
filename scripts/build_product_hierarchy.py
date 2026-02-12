from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


PARENT_RE = re.compile(r"INT\.L(?P<level>\d+)-(?P<code>.+)")


def parse_args():
    p = argparse.ArgumentParser(description="Build per-product hierarchy snapshot from flattened values.")
    p.add_argument("--values", required=True, help="outputs/product_values_v1.jsonl")
    p.add_argument("--out", required=True, help="outputs/product_hierarchy_v1.jsonl")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.values)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # per-product aggregation
    agg = defaultdict(lambda: {
        "product_id": None,
        "product_name": None,
        "user_type_id": None,
        "parent_id": None,
        "parent_level": None,
        "parent_code": None,
        "hr_attributes": {},   # THD.HR.* => {id, name}
    })

    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            pid = r["product_id"]
            a = r.get("attribute_id")

            rec = agg[pid]
            rec["product_id"] = pid
            rec["product_name"] = r.get("product_name")
            rec["user_type_id"] = r.get("user_type_id")
            rec["parent_id"] = r.get("parent_id")

            # parse parent_id once
            if rec["parent_id"] and rec["parent_level"] is None:
                m = PARENT_RE.match(rec["parent_id"])
                if m:
                    rec["parent_level"] = int(m.group("level"))
                    rec["parent_code"] = m.group("code")

            # capture hierarchy attributes
            if a and a.startswith("THD.HR."):
                rec["hr_attributes"][a] = {
                    "id": r.get("value_id"),
                    "name": r.get("value_text"),
                }

    # write jsonl
    n = 0
    with out_path.open("w", encoding="utf-8") as out:
        for pid, rec in agg.items():
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} products -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
