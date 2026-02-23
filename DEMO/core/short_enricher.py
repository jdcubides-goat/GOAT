from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.llm.client import call_llm_text
from core.utils import clamp_chars, to_single_paragraph
from core.io.delta_writer import build_delta_xml_products


def build_prompt_short(
    prod: Dict[str, Any],
    category_ctx: Optional[Dict[str, Any]],
    max_chars: int,
    forbidden_terms: List[str],
    required_terms: List[str],
    language: str,
    tone: str,
) -> str:
    web_name = prod.get("web_name") or prod.get("name") or ""
    brand = prod.get("brand") or prod.get("marca") or ""
    attrs = prod.get("attributes") or {}

    picked_values = []
    for _k, v in attrs.items():
        if v:
            picked_values.append(str(v[0] if isinstance(v, list) else v))
        if len(picked_values) >= 2:
            break

    attr_str = ", ".join(picked_values) if picked_values else "N/A"
    forbidden_str = ", ".join(forbidden_terms) if forbidden_terms else "N/A"
    required_str = ", ".join(required_terms) if required_terms else "N/A"

    return f"""
Generate ONE short product description.

LANGUAGE: {language}
TONE: {tone}

RULES:
- Max {max_chars} characters
- 1 paragraph
- 1–2 sentences
- Must include: product type + brand (if exists) + 1–2 attributes
- Avoid repeating product name
- No pricing, shipping, promo, guarantee

FORBIDDEN TERMS:
{forbidden_str}

MANDATORY TERMS:
{required_str}

PRODUCT:
- Name: {web_name}
- Brand: {brand}
- Attributes: {attr_str}

Return ONLY the final short description.
""".strip()


def generate_product_short_descriptions(
    products: List[Dict[str, Any]],
    category_context_map: Dict[str, Dict[str, Any]],
    outputs_dir: Path,
    attribute_id_for_delta: str,
    max_chars: int,
    model: str,
    forbidden_terms: List[str],
    required_terms: List[str],
    language: str = "es-ES",
    tone: str = "neutral",
) -> Tuple[Path, Path, Path]:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    out_jsonl = outputs_dir / "product_short_descriptions.jsonl"
    out_xml = outputs_dir / "delta_product_short_descriptions.xml"
    out_report = outputs_dir / "product_short_generation_report.json"

    rows: List[Dict[str, Any]] = []
    timings: List[Dict[str, Any]] = []

    t0 = time.perf_counter()

    for prod in products:
        pid = str(prod.get("product_id") or prod.get("id") or "").strip()
        if not pid:
            continue

        parent_id = (prod.get("parent_id") or (prod.get("labels") or {}).get("parent_id") or "").strip()
        cc = category_context_map.get(str(parent_id)) if parent_id else None

        prompt = build_prompt_short(
            prod=prod,
            category_ctx=cc,
            max_chars=int(max_chars),
            forbidden_terms=forbidden_terms,
            required_terms=required_terms,
            language=language,
            tone=tone,
        )

        t1 = time.perf_counter()
        txt, _dt = call_llm_text(prompt, model=model, max_output_tokens=180)
        t2 = time.perf_counter()

        txt = clamp_chars(to_single_paragraph(txt), int(max_chars))

        latency = float(t2 - t1)
        row = {
            "product_id": pid,
            "parent_id": parent_id,
            "decision": "generate",
            "model": model,
            "latency_s": round(latency, 3),
            "short_description_generated": txt,
        }
        rows.append(row)
        timings.append({"product_id": pid, "latency_s": round(latency, 3)})

    out_jsonl.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    out_xml.write_text(
        build_delta_xml_products(rows, attribute_id_for_delta, "short_description_generated"),
        encoding="utf-8",
    )

    total_s = float(time.perf_counter() - t0)
    report = {
        "count": len(rows),
        "total_s": round(total_s, 3),
        "avg_s": round((total_s / len(rows)) if rows else 0.0, 3),
        "attribute_id_for_delta": attribute_id_for_delta,
        "max_chars": int(max_chars),
        "model": model,
        "language": language,
        "tone": tone,
        "forbidden_terms_count": len(forbidden_terms),
        "required_terms_count": len(required_terms),
        "timings": timings[:200],
    }
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return out_jsonl, out_xml, out_report
