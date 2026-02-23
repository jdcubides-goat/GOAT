from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .llm.client import call_llm_text
from .utils import norm_ws, write_jsonl, ensure_dir, write_json
from .io.delta_writer import build_step_delta_xml


def _single_paragraph(s: str) -> str:
    s = re.sub(r"[\r\n]+", " ", s or "")
    return norm_ws(s)


def _clamp_chars(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars].rstrip()
    # try cut on last sentence boundary
    m = re.search(r"[.!?]\s+[^.!?]*$", cut)
    if m:
        cut = cut[: m.start()].rstrip()
    return cut.rstrip(" ,;:-") + "."


def build_category_prompt(row: Dict, max_chars: int, forbidden_terms: Optional[List[str]] = None, required_terms: Optional[List[str]] = None) -> str:
    forbidden_terms = forbidden_terms or []
    required_terms = required_terms or []

    cat_path = row.get("category_path") or ""
    cat_name = row.get("category_name") or ""
    top_attrs = row.get("top_attribute_ids") or []
    keywords = row.get("keywords") or []
    products_count = row.get("products_count") or 0

    # Keep prompt tight and deterministic
    return f"""
Genera UNA descripción de categoría para eCommerce en español neutro.

REGLAS:
- 1 solo párrafo (sin viñetas).
- Máximo {max_chars} caracteres (con espacios).
- No inventes datos técnicos, marcas específicas, certificaciones o compatibilidades.
- No menciones precio, promociones, envío, disponibilidad, garantía.
- Enfoque: explicar qué incluye la categoría, usos típicos y cómo elegir (criterios generales).
- Evita redundancias.

CATEGORÍA:
- Path: {cat_path}
- Nombre: {cat_name}
- Productos de referencia (conteo): {products_count}

SEÑALES (solo referencia; no inventar specs):
- Keywords frecuentes: {", ".join(keywords[:15]) if keywords else "N/A"}
- Atributos frecuentes (IDs): {", ".join(top_attrs[:20]) if top_attrs else "N/A"}

COMPLIANCE:
- Términos requeridos (si aplica): {", ".join(required_terms) if required_terms else "N/A"}
- Términos prohibidos (si aplica): {", ".join(forbidden_terms) if forbidden_terms else "N/A"}

ENTREGA:
- Devuelve SOLO el texto final (sin comillas).
""".strip()


def generate_category_descriptions(
    category_rows: List[Dict],
    outputs_dir: Path,
    attribute_id_for_delta: str,
    model: str = "gpt-4.1-mini",
    max_chars: int = 600,
    max_output_tokens: int = 280,
    forbidden_terms: Optional[List[str]] = None,
    required_terms: Optional[List[str]] = None,
) -> Tuple[Path, Path, Path]:
    """
    Generates descriptions for given category_rows and persists:
      - category_descriptions.jsonl
      - delta_category_descriptions.xml
      - category_generation_report.json
    """
    ensure_dir(outputs_dir)

    out_rows = []
    report_rows = []

    for row in category_rows:
        prompt = build_category_prompt(row, max_chars=max_chars, forbidden_terms=forbidden_terms, required_terms=required_terms)
        txt, dt = call_llm_text(prompt, model=model, max_output_tokens=max_output_tokens)
        txt = _clamp_chars(_single_paragraph(txt), max_chars)

        out = {
            "category_key": row.get("category_key"),
            "category_path": row.get("category_path", ""),
            "category_name": row.get("category_name", ""),
            "model": model,
            "latency_s": round(dt, 3),
            "category_description": txt,
        }
        out_rows.append(out)
        report_rows.append({
            "category_key": out["category_key"],
            "latency_s": out["latency_s"],
            "chars": len(txt),
        })

    jsonl_path = outputs_dir / "category_descriptions.jsonl"
    xml_path = outputs_dir / "delta_category_descriptions.xml"
    rep_path = outputs_dir / "category_generation_report.json"

    write_jsonl(jsonl_path, out_rows)

    # Build STEP delta XML (treat categories as Products with ID=category_key)
    xml = build_step_delta_xml(
        rows=out_rows,
        attribute_id=attribute_id_for_delta,
        text_field="category_description",
        product_id_field="category_key",
        root_tag="STEP-ProductInformation",
    )
    xml_path.write_text(xml, encoding="utf-8")

    write_json(rep_path, {"count": len(out_rows), "rows": report_rows, "attribute_id_for_delta": attribute_id_for_delta})

    return jsonl_path, xml_path, rep_path
