from __future__ import annotations

import argparse
import json
from pathlib import Path


TONE_RULES = {
    "language": "es-MX",
    "tone": "comercial, claro, profesional, sin exageraciones",
    "style": "informativo, orientado a e-commerce, evita claims no verificables",
}


def parse_args():
    p = argparse.ArgumentParser(description="Build AI jobs (one per category) for category description enrichment.")
    p.add_argument("--category-context", required=True, help="outputs/category_context_v1.jsonl")
    p.add_argument("--out", required=True, help="outputs/ai_jobs_categories_v1.jsonl")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    in_path = Path(args.category_context)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with in_path.open("r", encoding="utf-8") as f, out_path.open("w", encoding="utf-8") as out:
        for line in f:
            cat = json.loads(line)

            job = {
                "job_type": "category_enrichment",
                "category_key": cat["category_key"],
                "inputs": {
                    "web_department": cat.get("web_department"),
                    "web_category": cat.get("web_category"),
                    "web_subcategory": cat.get("web_subcategory"),
                    "product_count": cat.get("product_count"),
                    "top_terms": cat.get("top_terms", []),
                    "examples": cat.get("examples", []),
                    "tone_rules": TONE_RULES,
                },
                "expected_output_schema": {
                    "category_key": "string",
                    "title": "string",
                    "short_description": "string (120-200 chars aprox)",
                    "long_description": "string (600-1200 chars aprox)",
                    "keywords": "array[string] (10-25)",
                    "do_not": "array[string] (reglas: no inventar specs, no afirmar garantías, etc.)",
                },
            }

            out.write(json.dumps(job, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} AI category jobs -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
