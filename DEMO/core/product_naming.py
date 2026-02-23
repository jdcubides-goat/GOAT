from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.llm.client import call_llm_text
from core.io.delta_writer import build_delta_xml_products


def _to_single_paragraph(text: str) -> str:
    t = (text or "").strip()
    t = " ".join(t.split())
    return t


def _clamp_chars(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if max_chars <= 0:
        return t
    if len(t) <= max_chars:
        return t
    return t[: max_chars].rstrip()


def _pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        s = str(v[0]).strip()
        return s or None
    s = str(v).strip()
    return s or None


def _is_meaningful(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    if t.lower() in {"n/a", "na", "none", "null", "0", "0.0"}:
        return False
    return True


def _product_type(prod: Dict[str, Any], category_ctx: Optional[Dict[str, Any]]) -> str:
    if category_ctx:
        for k in ["product_type", "category_name", "web_subcategory", "web_category"]:
            v = category_ctx.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    labels = prod.get("labels") or {}
    for k in ["web_subcategory", "web_category"]:
        v = labels.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "Producto"


def _apply_case(text: str, casing: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    c = (casing or "").strip().lower()
    if c == "upper":
        return t.upper()
    if c == "lower":
        return t.lower()

    def fix_word(w: str) -> str:
        if re.fullmatch(r"[A-Z0-9]{2,}", w):
            return w
        if len(w) >= 2 and w.isupper():
            return w
        return w[:1].upper() + w[1:].lower()

    return " ".join(fix_word(w) for w in t.split())


def build_prompt_naming(
    prod: Dict[str, Any],
    category_ctx: Optional[Dict[str, Any]],
    max_chars: int,
    forbidden_terms: List[str],
    required_terms: List[str],
    language: str,
    casing: str,
) -> str:
    web_name = prod.get("web_name") or prod.get("name") or ""
    brand = prod.get("brand") or prod.get("marca") or ""
    model = prod.get("model") or prod.get("modelo") or ""
    attrs = prod.get("attributes") or {}

    ptype = _product_type(prod, category_ctx)

    candidate_keys = [
        "THD.CT.MATERIAL",
        "THD.CT.COLOR",
        "THD.CT.TAMANO",
        "THD.CT.MEDIDA",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.ALTO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
        "THD.CT.ACABADOS",
    ]

    picked: List[str] = []
    for k in candidate_keys:
        v = _pick_first(attrs.get(k))
        if v and _is_meaningful(v):
            picked.append(v)
        if len(picked) >= 6:
            break

    attrs_str = " | ".join(picked) if picked else "N/A"
    forbidden_str = "\n".join(forbidden_terms) if forbidden_terms else "N/A"
    required_str = "\n".join(required_terms) if required_terms else "N/A"

    return f"""
Generate ONE normalized eCommerce product name (title) for web publishing.

LANGUAGE: {language}
CASE: {casing}   (allowed: Proper / Upper / Lower)

HARD RULES:
- Max {max_chars} characters (including spaces)
- Do NOT invent attributes/specs
- If a field is missing/empty/0, omit it naturally
- Avoid repeating the same term twice (dedupe)
- No price, promo, shipping, availability, warranty terms
- Must be understandable without extra context

COMPLIANCE:
FORBIDDEN TERMS (must NOT appear):
{forbidden_str}

MANDATORY TERMS (use ONLY when they apply and fit naturally):
{required_str}

INPUTS:
- Product type/category: {ptype}
- Current web/product name (reference only): {web_name}
- Brand: {brand if brand else "N/A"}
- Model: {model if model else "N/A"}
- Attribute values available (use only if helpful): {attrs_str}

OUTPUT FORMAT GUIDANCE:
- Prefer: [Product type] + [Brand] + [Model] + [Key attributes (2-4)].
- Keep it clean, like large eCommerce titles.

Return ONLY the final product name/title (no quotes).
""".strip()


def generate_product_names(
    products: List[Dict[str, Any]],
    category_context_map: Dict[str, Dict[str, Any]],
    outputs_dir: Path,
    attribute_id_for_delta: str,
    max_chars: int,
    model: str,
    forbidden_terms: List[str],
    required_terms: List[str],
    language: str = "es-ES",
    casing: str = "Proper",
) -> Tuple[Path, Path, Path]:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    out_jsonl = outputs_dir / "product_names.jsonl"
    out_xml = outputs_dir / "delta_product_names.xml"
    out_report = outputs_dir / "product_naming_report.json"

    rows: List[Dict[str, Any]] = []
    timings: List[Dict[str, Any]] = []
    t0 = time.perf_counter()

    for prod in products:
        pid = str(prod.get("product_id") or prod.get("id") or "").strip()
        if not pid:
            continue

        parent_id = (prod.get("parent_id") or (prod.get("labels") or {}).get("parent_id") or "").strip()
        cc = category_context_map.get(str(parent_id)) if parent_id else None

        prompt = build_prompt_naming(
            prod=prod,
            category_ctx=cc,
            max_chars=int(max_chars),
            forbidden_terms=forbidden_terms,
            required_terms=required_terms,
            language=language,
            casing=casing,
        )

        t1 = time.perf_counter()
        txt, _ = call_llm_text(prompt, model=model, max_output_tokens=180)
        t2 = time.perf_counter()

        txt = _clamp_chars(_to_single_paragraph(txt), int(max_chars))
        txt = _apply_case(txt, casing)

        latency = float(t2 - t1)

        row = {
            "product_id": pid,
            "parent_id": parent_id,
            "decision": "generate",
            "model": model,
            "latency_s": round(latency, 3),
            "web_name_generated": txt,
        }
        rows.append(row)
        timings.append({"product_id": pid, "latency_s": round(latency, 3)})

    out_jsonl.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    out_xml.write_text(
        build_delta_xml_products(rows, attribute_id_for_delta, "web_name_generated"),
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
        "casing": casing,
        "forbidden_terms_count": len(forbidden_terms),
        "required_terms_count": len(required_terms),
        "timings": timings[:200],
    }
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return out_jsonl, out_xml, out_report
