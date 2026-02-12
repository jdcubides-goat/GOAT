from __future__ import annotations

import argparse
import json
from pathlib import Path


WEB_ORDER = ["THD.HR.WebDepartment", "THD.HR.WebCategory", "THD.HR.WebSubcategory"]
ERP_ORDER = ["THD.HR.Department", "THD.HR.Class", "THD.HR.SubClass"]


def build_path(hierarchy: dict, order: list[str]) -> list[str]:
    out = []
    for key in order:
        node = hierarchy.get(key)
        if node and node.get("name"):
            out.append(node["name"])
    return out


def build_description(product: dict, web_path: list[str]) -> str:
    name = product.get("product_name") or ""
    desc_attrs = product.get("desc_attrs", {})

    short_desc = desc_attrs.get("THD.PR.WebShortDescription", {}).get("name")
    label = desc_attrs.get("THD.PR.Label", {}).get("name")
    model = desc_attrs.get("THD.PR.Model", {}).get("name")

    parts = [name]

    if short_desc:
        parts.append(short_desc)

    if model:
        parts.append(f"Modelo: {model}")

    if web_path:
        parts.append(f"Categoría: {' > '.join(web_path)}")

    return ". ".join(parts)


def parse_args():
    p = argparse.ArgumentParser(description="Build RAG-ready documents from compact product dataset.")
    p.add_argument("--compact", required=True)
    p.add_argument("--out", required=True)
    return p.parse_args()


def main():
    args = parse_args()
    in_path = Path(args.compact)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with in_path.open("r", encoding="utf-8") as f, \
         out_path.open("w", encoding="utf-8") as out:

        for line in f:
            product = json.loads(line)

            web_path = build_path(product.get("web_hierarchy", {}), WEB_ORDER)
            erp_path = build_path(product.get("erp_hierarchy", {}), ERP_ORDER)

            description = build_description(product, web_path)

            rag_doc = {
                "id": product["product_id"],
                "text": description,
                "metadata": {
                    "product_id": product["product_id"],
                    "name": product.get("product_name"),
                    "web_path": web_path,
                    "erp_path": erp_path,
                    "parent_id": product.get("parent_id"),
                    "user_type_id": product.get("user_type_id"),
                }
            }

            out.write(json.dumps(rag_doc, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} RAG documents -> {out_path}")


if __name__ == "__main__":
    main()
