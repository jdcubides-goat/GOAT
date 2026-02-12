from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WEB_ORDER = ["THD.HR.WebDepartment", "THD.HR.WebCategory", "THD.HR.WebSubcategory"]

STOP = {
    "de","la","el","y","a","en","con","para","por","sin","del","las","los",
    "cm","mm","mt","mts","kg","g","lt","l","x","un","una","unos","unas"
}

def norm_text(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"[^a-z0-9áéíóúñü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokens(s: str) -> list[str]:
    s = norm_text(s)
    out: list[str] = []
    for t in s.split():
        if t in STOP:
            continue
        if len(t) <= 2:
            continue
        out.append(t)
    return out

def web_path(product: dict) -> list[str]:
    h = product.get("web_hierarchy", {}) or {}
    out: list[str] = []
    for k in WEB_ORDER:
        node = h.get(k) or {}
        if node.get("name"):
            out.append(node["name"])
    return out

def parse_args():
    p = argparse.ArgumentParser(description="Build per-web-category context from compact product dataset.")
    p.add_argument("--compact", required=True, help="outputs/product_compact_v1.jsonl")
    p.add_argument("--out", required=True, help="outputs/category_context_v1.jsonl")
    p.add_argument("--examples-per-cat", type=int, default=10)
    p.add_argument("--top-terms", type=int, default=40)
    return p.parse_args()

def main() -> int:
    args = parse_args()
    in_path = Path(args.compact)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cats = defaultdict(lambda: {
        "count": 0,
        "examples": [],
        "term_counter": Counter(),
        "web_department": None,
        "web_category": None,
        "web_subcategory": None,
    })

    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)

            path = web_path(p)
            if len(path) == 3:
                web_department, web_category, web_subcategory = path
                key = " > ".join(path)
            else:
                web_department = path[0] if len(path) > 0 else None
                web_category = path[1] if len(path) > 1 else None
                web_subcategory = path[2] if len(path) > 2 else None
                key = " > ".join(path) if path else "UNMAPPED"

            name = p.get("product_name") or ""
            desc_attrs = p.get("desc_attrs", {}) or {}
            short_desc = (desc_attrs.get("THD.PR.WebShortDescription") or {}).get("name") or ""
            label = (desc_attrs.get("THD.PR.Label") or {}).get("name") or ""
            model = (desc_attrs.get("THD.PR.Model") or {}).get("name") or ""

            c = cats[key]
            c["count"] += 1
            c["web_department"] = c["web_department"] or web_department
            c["web_category"] = c["web_category"] or web_category
            c["web_subcategory"] = c["web_subcategory"] or web_subcategory

            # términos desde nombre/label/short (para “vocabulario de categoría”)
            c["term_counter"].update(tokens(name))
            c["term_counter"].update(tokens(label))
            c["term_counter"].update(tokens(short_desc))

            # ejemplos representativos
            if len(c["examples"]) < args.examples_per_cat:
                c["examples"].append({
                    "product_id": p.get("product_id"),
                    "product_name": name,
                    "model": model or None,
                    "short_desc": short_desc or None,
                    "erp_subclass": ((p.get("erp_hierarchy", {}) or {}).get("THD.HR.SubClass") or {}).get("name"),
                })

    n = 0
    with out_path.open("w", encoding="utf-8") as out:
        for key, info in cats.items():
            top_terms = [t for t, _ in info["term_counter"].most_common(args.top_terms)]
            row = {
                "category_key": key,  # "Depto > Cat > Subcat"
                "web_department": info["web_department"],
                "web_category": info["web_category"],
                "web_subcategory": info["web_subcategory"],
                "product_count": info["count"],
                "top_terms": top_terms,
                "examples": info["examples"],
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} categories -> {out_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
