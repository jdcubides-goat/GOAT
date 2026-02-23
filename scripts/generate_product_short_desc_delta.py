#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from xml.sax.saxutils import escape
from time import perf_counter

from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

load_dotenv()


# ==============================================================================
# IO JSONL
# ==============================================================================
def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSONL at {path}:{line_no}: {e}") from e


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ==============================================================================
# Text helpers
# ==============================================================================
def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def to_single_paragraph(text: str) -> str:
    text = re.sub(r"[\r\n]+", " ", (text or ""))
    return normalize_ws(text)


def clamp_chars(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rstrip()
    m = re.search(r"[.!?]\s+[^.!?]*$", cut)
    if m:
        cut = cut[: m.start()].rstrip()
    return cut.rstrip(" ,;:-") + "."


def pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        s = str(v[0]).strip()
        return s or None
    s = str(v).strip()
    return s or None


# ==============================================================================
# Category context
# ==============================================================================
def load_category_context(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Espera JSONL tipo:
    {
      "category_key": "INT.L4-S1219",
      "labels": {"parent_id": "INT.L4-S1219", "web_department": "...", "web_category": "...", "web_subcategory": "..."},
      "keywords": [...],
      "recommended_focus": [...],
      ...
    }
    Retorna dict indexado por category_key (y/o parent_id equivalente).
    """
    ctx: Dict[str, Dict[str, Any]] = {}
    if not path or not path.exists():
        return ctx

    for row in read_jsonl(path):
        key = (row.get("category_key") or "").strip()
        labels = row.get("labels", {}) or {}
        parent_id = (labels.get("parent_id") or "").strip()

        if key:
            ctx[key] = row
        if parent_id and parent_id not in ctx:
            # index extra por parent_id para match directo con productos
            ctx[parent_id] = row

    return ctx


def build_category_path_str_from_labels(labels: Dict[str, Any]) -> str:
    web_department = (labels.get("web_department") or "").strip()
    web_category = (labels.get("web_category") or "").strip()
    web_subcategory = (labels.get("web_subcategory") or "").strip()

    parts = [p for p in [web_department, web_category, web_subcategory] if p]
    return " > ".join(parts) if parts else ""


# ==============================================================================
# OpenAI
# ==============================================================================
def model_supports_temperature(model: str) -> bool:
    m = (model or "").lower()
    if m.startswith("gpt-5"):
        return False
    return True


@dataclass
class LLMConfig:
    model: str
    max_output_tokens: int = 160
    timeout_s: int = 60
    sleep_s: float = 0.15
    temperature: Optional[float] = None


def call_llm(prompt: str, cfg: LLMConfig) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment (.env).")

    client = OpenAI(api_key=api_key)

    kwargs: Dict[str, Any] = {
        "model": cfg.model,
        "input": [
            {"role": "system", "content": "Responde con precisión. No inventes datos."},
            {"role": "user", "content": prompt},
        ],
        "max_output_tokens": cfg.max_output_tokens,
        "timeout": cfg.timeout_s,
    }

    if cfg.temperature is not None and model_supports_temperature(cfg.model):
        kwargs["temperature"] = cfg.temperature

    resp = client.responses.create(**kwargs)

    out_text: List[str] = []
    for item in getattr(resp, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    out_text.append(getattr(c, "text", ""))

    return normalize_ws(" ".join(out_text))


# ==============================================================================
# Prompt SHORT
# ==============================================================================
def build_prompt_short(
    prod: Dict[str, Any],
    max_chars: int,
    include_attr_names: bool,
    mode: str,
    existing_short: Optional[str],
    category_labels: Dict[str, Any],
    category_keywords: List[str],
    category_focus: List[str],
) -> str:
    web_department = category_labels.get("web_department") or (prod.get("labels", {}) or {}).get("web_department") or ""
    web_category = category_labels.get("web_category") or (prod.get("labels", {}) or {}).get("web_category") or ""
    web_subcategory = category_labels.get("web_subcategory") or (prod.get("labels", {}) or {}).get("web_subcategory") or ""
    category_last_level = prod.get("category_last_level") or web_subcategory or web_category or web_department or "Producto"

    web_name = prod.get("web_name") or ""
    tipo_marca = prod.get("tipo_marca") or ""
    model = prod.get("model") or ""
    brand = prod.get("brand") or prod.get("marca") or ""

    attrs = prod.get("attributes", {}) or {}

    candidate_keys = [
        "THD.CT.COLOR",
        "THD.CT.MATERIAL",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.ALTO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
    ]

    picked: List[tuple[str, str]] = []
    for k in candidate_keys:
        v = pick_first(attrs.get(k))
        if v:
            picked.append((k, v))
        if len(picked) >= 2:
            break

    if include_attr_names:
        attrs_str = ", ".join([f"{k.split('.')[-1].lower()} {v}" for k, v in picked]) if picked else "N/A"
    else:
        attrs_str = ", ".join([v for _, v in picked]) if picked else "N/A"

    existing_block = ""
    if existing_short and existing_short.strip():
        existing_block = f'\nSHORT EXISTENTE:\n"{normalize_ws(existing_short)}"\n'

    kw_str = ", ".join(category_keywords[:12]) if category_keywords else "N/A"
    focus_str = ", ".join(category_focus[:10]) if category_focus else "N/A"

    return f"""
Eres redactor eCommerce. Genera UNA descripción corta (short description) para PDP/search/preview en español neutro.

MODO:
- mode={mode}
  - create: crear desde cero
  - improve: mejorar la short existente sin inventar datos

REGLAS OBLIGATORIAS:
- 1 solo párrafo.
- Máximo {max_chars} caracteres (contando espacios).
- 1 a 2 frases.
- Debe ser entendible sin contexto adicional.
- No inventes especificaciones, compatibilidades ni claims.
- No menciones precio, promos, envíos, disponibilidad, ni garantía.
- Evita repetir el nombre del producto (0 o 1 vez máximo).
- Debe incluir: tipo/categoría + (marca si existe) + 1–2 atributos clave.

CONTEXTO DE CATEGORÍA:
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- Tipo/Categoría (último nivel): {category_last_level}
- Keywords (señales): {kw_str}
- Enfoque recomendado: {focus_str}

DATOS DEL PRODUCTO:
- WebName: {web_name}
- Brand (si existe): {brand if brand else "N/A"}
- Modelo: {model if model else "N/A"}
- TipoMarca (contexto): {tipo_marca if tipo_marca else "N/A"}

ATRIBUTOS DISPONIBLES (selección 1–2):
- {attrs_str}

{existing_block}
ENTREGA:
- Devuelve SOLO la short final (sin comillas).
""".strip()


# ==============================================================================
# XML builders
# ==============================================================================
def build_delta_xml(rows: List[Dict[str, Any]], attr_id: str) -> str:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<STEP-ProductInformation>")
    parts.append("  <Products>")
    for r in rows:
        if r.get("decision") != "generate":
            continue
        pid = r.get("product_id")
        desc = r.get("web_short_description")
        if not pid or not desc:
            continue
        parts.append(f'    <Product ID="{escape(str(pid))}">')
        parts.append("      <Values>")
        parts.append(f'        <Value AttributeID="{escape(attr_id)}">{escape(str(desc))}</Value>')
        parts.append("      </Values>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</STEP-ProductInformation>")
    return "\n".join(parts) + "\n"


def build_preview_context_xml(context_rows: List[Dict[str, Any]]) -> str:
    """
    Formato tipo:
    <GOAT-Preview>
      <Products>
        <Product id="...">
          <WebName>...</WebName>
          <ParentID>...</ParentID>
          <CategoryPath>Dept &gt; Cat &gt; Subcat</CategoryPath>
        </Product>
      </Products>
    </GOAT-Preview>
    """
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<GOAT-Preview>")
    parts.append("  <Products>")
    for r in context_rows:
        pid = r.get("product_id")
        if not pid:
            continue
        web_name = r.get("web_name") or ""
        parent_id = r.get("parent_id") or ""
        category_path_str = r.get("category_path_str") or ""
        parts.append(f'    <Product id="{escape(str(pid))}">')
        parts.append(f"      <WebName>{escape(str(web_name))}</WebName>")
        parts.append(f"      <ParentID>{escape(str(parent_id))}</ParentID>")
        parts.append(f"      <CategoryPath>{escape(str(category_path_str))}</CategoryPath>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</GOAT-Preview>")
    return "\n".join(parts) + "\n"


# ==============================================================================
# main
# ==============================================================================
def main() -> None:
    p = argparse.ArgumentParser()

    p.add_argument("--in", dest="in_path", required=True, help="Input products JSONL (features per product)")
    p.add_argument("--out-jsonl", dest="out_jsonl", required=True, help="Output results JSONL")
    p.add_argument("--out-xml", dest="out_xml", required=True, help="Output STEPXML delta file")

    # Contexto categoría (igual que LONG)
    p.add_argument("--category-context", dest="category_context", required=False, default="", help="Category context JSONL")
    p.add_argument("--out-preview-jsonl", dest="out_preview_jsonl", required=False, default="", help="Output preview context JSONL")
    p.add_argument("--out-preview-xml", dest="out_preview_xml", required=False, default="", help="Output preview context XML")

    p.add_argument("--model", default="gpt-4.1-mini", help="Model name")
    p.add_argument("--limit", type=int, default=0, help="Limit products (0 = no limit)")
    p.add_argument("--max-chars", type=int, default=120, help="Max chars per short description")
    p.add_argument("--attr-id", default="THD.PR.WebShortDescription", help="STEP AttributeID to write back")

    p.add_argument("--temperature", type=float, default=-1.0, help="Temperature (ignored for models that don't support it)")
    p.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between calls")
    p.add_argument("--dry-run", action="store_true", help="Do not call LLM; only output prompts preview")

    p.add_argument("--mode", choices=["create", "improve"], default="create", help="Create from scratch or improve existing")
    p.add_argument("--existing-field", default="web_short_description", help="Field name in input JSON for existing short")
    p.add_argument("--include-attr-names", action="store_true", help="Include attribute labels (e.g., 'color negro')")

    # logging
    p.add_argument("--log-every", type=int, default=0, help="Log every N products (0 = no periodic log)")

    args = p.parse_args()

    cfg = LLMConfig(
        model=args.model,
        sleep_s=args.sleep,
        temperature=None if args.temperature < 0 else float(args.temperature),
    )

    in_path = Path(args.in_path)
    out_jsonl = Path(args.out_jsonl)
    out_xml = Path(args.out_xml)

    category_ctx_path = Path(args.category_context) if args.category_context else None
    category_ctx = load_category_context(category_ctx_path) if category_ctx_path else {}

    out_preview_jsonl = Path(args.out_preview_jsonl) if args.out_preview_jsonl else None
    out_preview_xml = Path(args.out_preview_xml) if args.out_preview_xml else None

    rows_out: List[Dict[str, Any]] = []
    generated_rows_for_xml: List[Dict[str, Any]] = []

    preview_rows: List[Dict[str, Any]] = []

    t0 = perf_counter()
    processed = 0
    generated = 0
    skipped = 0

    for prod in read_jsonl(in_path):
        if args.limit and processed >= args.limit:
            break

        pid = prod.get("product_id")
        parent_id = prod.get("parent_id") or (prod.get("labels", {}) or {}).get("parent_id") or ""
        web_name = prod.get("web_name") or ""

        existing_short = pick_first(prod.get(args.existing_field)) if args.existing_field else None
        mode = args.mode
        if mode == "improve" and not (existing_short and existing_short.strip()):
            mode = "create"

        record: Dict[str, Any] = {
            "product_id": pid,
            "parent_id": parent_id,
            "web_name": web_name,
            "model": cfg.model,
            "decision": "generate",
            "skip_reasons": [],
        }

        if not pid:
            record["decision"] = "skip"
            record["skip_reasons"].append("missing_product_id")
            rows_out.append(record)
            processed += 1
            skipped += 1
            continue

        # Category context lookup por parent_id
        cat_row = category_ctx.get(parent_id, {}) if parent_id else {}
        cat_labels = (cat_row.get("labels", {}) or {})
        cat_keywords = cat_row.get("keywords", []) or []
        cat_focus = cat_row.get("recommended_focus", []) or []

        category_path_str = build_category_path_str_from_labels(cat_labels) if cat_labels else ""
        if not category_path_str:
            # fallback desde labels del producto si existen
            category_path_str = build_category_path_str_from_labels(prod.get("labels", {}) or {})

        # Always build preview context row (así la app siempre tiene la tabla)
        preview_rows.append(
            {
                "product_id": pid,
                "web_name": web_name,
                "parent_id": parent_id,
                "category_path": [p for p in category_path_str.split(" > ") if p] if category_path_str else [],
                "category_path_str": category_path_str,
            }
        )

        prompt = build_prompt_short(
            prod=prod,
            max_chars=args.max_chars,
            include_attr_names=bool(args.include_attr_names),
            mode=mode,
            existing_short=existing_short,
            category_labels=cat_labels if cat_labels else (prod.get("labels", {}) or {}),
            category_keywords=cat_keywords,
            category_focus=cat_focus,
        )

        if args.dry_run:
            record["decision"] = "skip"
            record["skip_reasons"].append("dry_run")
            record["prompt_preview"] = prompt[:900]
            rows_out.append(record)
            processed += 1
            skipped += 1
            continue

        per_start = perf_counter()
        text = call_llm(prompt, cfg)
        text = to_single_paragraph(text)
        text = clamp_chars(text, args.max_chars)

        if len(text) < 25:
            record["decision"] = "skip"
            record["skip_reasons"].append("too_short_after_generation")
            record["web_short_description"] = None
            skipped += 1
        else:
            record["web_short_description"] = text
            generated_rows_for_xml.append(record)
            generated += 1

        per_end = perf_counter()
        record["latency_s"] = round(per_end - per_start, 3)

        rows_out.append(record)
        processed += 1

        if args.log_every and processed % args.log_every == 0:
            ok = (record["decision"] == "generate")
            chars = len(record.get("web_short_description") or "")
            print(f"[{processed}] id={pid} | gen={ok} | chars={chars} | time={record['latency_s']}s")

        time.sleep(cfg.sleep_s)

    # Outputs
    write_jsonl(out_jsonl, rows_out)

    delta_xml = build_delta_xml(generated_rows_for_xml, attr_id=args.attr_id)
    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text(delta_xml, encoding="utf-8")

    # Preview outputs (context map)
    if out_preview_jsonl:
        write_jsonl(out_preview_jsonl, preview_rows)
    if out_preview_xml:
        out_preview_xml.parent.mkdir(parents=True, exist_ok=True)
        out_preview_xml.write_text(build_preview_context_xml(preview_rows), encoding="utf-8")

    t1 = perf_counter()
    total_s = t1 - t0
    avg_s = (total_s / processed) if processed else 0.0

    print(f"OK: wrote JSONL -> {out_jsonl} ({len(rows_out)} rows)")
    print(f"OK: wrote STEPXML delta -> {out_xml} ({generated} products)")
    if out_preview_jsonl:
        print(f"OK: wrote Preview JSONL -> {out_preview_jsonl} ({len(preview_rows)} rows)")
    if out_preview_xml:
        print(f"OK: wrote Preview XML -> {out_preview_xml} ({len(preview_rows)} products)")
    print(f"STATS: processed={processed} generated={generated} skipped={skipped} total_time={total_s:.2f}s avg_per_product={avg_s:.3f}s")


if __name__ == "__main__":
    main()
