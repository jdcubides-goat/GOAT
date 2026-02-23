from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

from core.llm.client import call_llm_text


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _to_single_paragraph(text: str) -> str:
    text = re.sub(r"[\r\n]+", " ", (text or ""))
    return _normalize_ws(text)


def _clamp_chars(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    m = re.search(r"[.!?]\s+[^.!?]*$", cut)
    if m:
        cut = cut[: m.start()].rstrip()
    return cut.rstrip(" ,;:-") + "."


def _pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        s = str(v[0]).strip()
        return s or None
    s = str(v).strip()
    return s or None


def build_delta_xml_products(
    rows: List[Dict[str, Any]],
    attribute_id: str,
    value_field: str,
) -> str:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<STEP-ProductInformation>")
    parts.append("  <Products>")
    for r in rows:
        pid = r.get("product_id")
        val = r.get(value_field)
        if not pid or not val:
            continue
        parts.append(f'    <Product ID="{xml_escape(str(pid))}">')
        parts.append("      <Values>")
        parts.append(f'        <Value AttributeID="{xml_escape(attribute_id)}">{xml_escape(str(val))}</Value>')
        parts.append("      </Values>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</STEP-ProductInformation>")
    return "\n".join(parts) + "\n"


def build_prompt_long(
    prod: Dict[str, Any],
    category_ctx: Optional[Dict[str, Any]],
    max_chars: int,
    forbidden_terms: List[str],
    required_terms: List[str],
) -> str:
    labels = prod.get("labels", {}) or {}
    web_department = labels.get("web_department") or ""
    web_category = labels.get("web_category") or ""
    web_subcategory = labels.get("web_subcategory") or ""

    web_name = prod.get("web_name") or prod.get("name") or ""
    model = prod.get("model") or ""
    brand = prod.get("brand") or prod.get("marca") or ""

    attrs = prod.get("attributes", {}) or {}
    candidate_keys = [
        "THD.CT.MATERIAL",
        "THD.CT.COLOR",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.ALTO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
        "THD.CT.ACABADOS",
        "THD.CT.MODELO",
    ]

    picked: List[str] = []
    for k in candidate_keys:
        v = _pick_first(attrs.get(k))
        if v:
            picked.append(f"{k.split('.')[-1]}: {v}")
        if len(picked) >= 8:
            break
    attrs_str = " | ".join(picked) if picked else "N/A"

    recommended_focus = (category_ctx.get("recommended_focus") or []) if category_ctx else []
    keywords = (category_ctx.get("keywords") or []) if category_ctx else []
    focus_str = ", ".join(recommended_focus) if recommended_focus else "N/A"
    kw_str = ", ".join(keywords[:15]) if keywords else "N/A"

    forbidden_str = "\n".join(forbidden_terms) if forbidden_terms else "N/A"
    required_str = "\n".join(required_terms) if required_terms else "N/A"

    return f"""
Genera UNA descripción larga (web long description) en español neutro para eCommerce.

REGLAS:
- 1 solo párrafo (sin viñetas).
- Máximo {max_chars} caracteres (con espacios).
- Explica beneficios de uso SIN inventar datos técnicos.
- No menciones precio, promos, envíos, disponibilidad, garantía.
- No afirmes certificaciones o compatibilidades no presentes en atributos.
- Usa solo información disponible + contexto de categoría.

COMPLIANCE:
- Palabras prohibidas (NO usar): 
{forbidden_str}

- Palabras obligatorias (SI usar cuando aplique y tenga sentido):
{required_str}

CONTEXTO DE CATEGORÍA:
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- Enfoque recomendado: {focus_str}
- Keywords (referencia): {kw_str}

DATOS PRODUCTO:
- WebName: {web_name}
- Brand: {brand if brand else "N/A"}
- Modelo: {model if model else "N/A"}
- Atributos disponibles (incorpora algunos de forma natural si aplica): {attrs_str}

ENTREGA:
- Devuelve SOLO la long final (sin comillas).
""".strip()


def generate_product_long_descriptions(
    products: List[Dict[str, Any]],
    category_context_map: Dict[str, Dict[str, Any]],
    outputs_dir: Path,
    attribute_id_for_delta: str,
    max_chars: int,
    model: str,
    forbidden_terms: List[str],
    required_terms: List[str],
) -> Tuple[Path, Path, Path]:
    outputs_dir.mkdir(parents=True, exist_ok=True)

    out_jsonl = outputs_dir / "product_long_desc.jsonl"
    out_xml = outputs_dir / "delta_web_long_desc.xml"
    out_report = outputs_dir / "product_long_generation_report.json"

    rows: List[Dict[str, Any]] = []
    timings: List[Dict[str, Any]] = []

    t0 = time.perf_counter()

    for prod in products:
        pid = str(prod.get("product_id") or "")
        if not pid:
            continue

        parent_id = prod.get("parent_id") or (prod.get("labels", {}) or {}).get("parent_id") or ""
        cc = category_context_map.get(str(parent_id)) if parent_id else None

        prompt = build_prompt_long(
            prod=prod,
            category_ctx=cc,
            max_chars=int(max_chars),
            forbidden_terms=forbidden_terms,
            required_terms=required_terms,
        )

        t1 = time.perf_counter()
        txt, _dt = call_llm_text(prompt, model=model, max_output_tokens=700)
        t2 = time.perf_counter()

        txt = _clamp_chars(_to_single_paragraph(txt), int(max_chars))
        latency = float(t2 - t1)

        row = {
            "product_id": pid,
            "parent_id": parent_id,
            "web_name": prod.get("web_name") or prod.get("name") or "",
            "decision": "generate",
            "model": model,
            "latency_s": round(latency, 3),
            "web_long_description": txt,
        }
        rows.append(row)
        timings.append({"product_id": pid, "latency_s": round(latency, 3)})

    out_jsonl.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8")
    out_xml.write_text(build_delta_xml_products(rows, attribute_id_for_delta, "web_long_description"), encoding="utf-8")

    total_s = float(time.perf_counter() - t0)
    report = {
        "count": len(rows),
        "total_s": round(total_s, 3),
        "avg_s": round((total_s / len(rows)) if rows else 0.0, 3),
        "attribute_id_for_delta": attribute_id_for_delta,
        "max_chars": int(max_chars),
        "model": model,
        "forbidden_terms_count": len(forbidden_terms),
        "required_terms_count": len(required_terms),
        "timings": timings[:200],
    }
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return out_jsonl, out_xml, out_report


def read_terms_from_upload(name: str, raw_bytes: bytes) -> List[str]:
    """
    Acepta txt/json/xml simple:
    - txt: una palabra por línea
    - json: {"terms":[...]} o lista [...]
    - xml: <terms><term>...</term></terms>
    """
    ext = (name.split(".")[-1] or "").lower()
    s = (raw_bytes or b"").decode("utf-8", errors="ignore").strip()
    if not s:
        return []

    # TXT
    if ext in {"txt", "csv"}:
        terms = [t.strip() for t in s.splitlines() if t.strip()]
        return terms

    # JSON
    if ext in {"json"}:
        try:
            obj = json.loads(s)
            if isinstance(obj, list):
                return [str(x).strip() for x in obj if str(x).strip()]
            if isinstance(obj, dict):
                arr = obj.get("terms") or obj.get("forbidden") or obj.get("required") or []
                if isinstance(arr, list):
                    return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            return []
        return []

    # XML (muy simple)
    if ext in {"xml"}:
        # extrae <term>...</term>
        terms = re.findall(r"<term>(.*?)</term>", s, flags=re.IGNORECASE | re.DOTALL)
        terms = [re.sub(r"\s+", " ", t).strip() for t in terms if t.strip()]
        return terms

    # fallback: intenta líneas
    return [t.strip() for t in s.splitlines() if t.strip()]
