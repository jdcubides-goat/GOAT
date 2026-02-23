import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="outputs/category_context_dir.json")
    ap.add_argument("--out", dest="out_path", default="outputs/category_packs.jsonl")
    ap.add_argument("--only-generate", action="store_true")
    args = ap.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(in_path.read_text(encoding="utf-8"))

    cats = data["global"]["categories"]

    lines = 0
    kept = 0
    with out_path.open("w", encoding="utf-8") as f:
        for c in cats:
            lines += 1
            if args.only_generate and not c.get("generate_category_description", False):
                continue

            pack = {
                "category_key": c["category_key"],
                "labels": c.get("labels", {}),
                "products_count": c.get("products_count", 0),
                "strong_attributes": c.get("strong_attributes", [])[:30],
                "top_attributes_by_presence": c.get("top_attributes_by_presence", [])[:25],
                "sample_web_names": c.get("sample_web_names", [])[:12],
                "generate_category_description": c.get("generate_category_description", False),
                "skip_reasons": c.get("skip_reasons", []),
            }
            f.write(json.dumps(pack, ensure_ascii=False) + "\n")
            kept += 1

    print("OK ->", out_path)
    print("Total categories:", lines)
    print("Exported:", kept)


if __name__ == "__main__":
    main()
