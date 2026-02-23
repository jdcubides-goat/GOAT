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


# -------------------------
# IO helpers
# -------------------------
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


# -------------------------
# Text helpers
# -------------------------
def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def to_single_paragraph(text: str) -> str:
    text = re.sub(r"[\r\n]+", " ", text)
    return normalize_ws(text)


def clamp_chars(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars].rstrip()
    # intenta recortar al final de una frase si existe
    m = re.search(r"[.!?]\s+[^.!?]*$", cut)
    if m:
        cut = cut[: m.start()].rstrip()
    return cut.rstrip(" ,;:-") + "."


def pick_first(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, list) and v:
        return str(v[0]).strip() or None
    s = str(v).strip()
    return s or None


# -------------------------
# Category context (breadcrumb) resolver
# -------------------------
def load_category_context_map(category_context_path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Espera JSONL con una fila por categoría.
    Debe tener al menos:
      - category_key o labels.parent_id (ej: INT.L4-S1212)
      - labels con web_department/web_category/web_subcategory
      - opcional: category_path (lista) o breadcrumb (str)
    """
    m: Dict[str, Dict[str, Any]] = {}
    for row in read_jsonl(category_context_path):
        key = row.get("category_key") or (row.get("labels", {}) or {}).get("parent_id")
        if not key:
            continue
        m[str(key)] = row
    return m


def resolve_category_path_for_product(prod: Dict[str, Any], ctx_map: Optional[Dict[str, Dict[str, Any]]]) -> List[str]:
    """
    Prioridad:
      1) prod.category_path si ya viene
      2) category_context_dir: row.category_path o row.breadcrumb
      3) labels: [web_department, web_category, web_subcategory]
    """
    # 1) directo en producto
    cp = prod.get("category_path")
    if isinstance(cp, list) and cp:
        return [str(x).strip() for x in cp if str(x).strip()]

    parent_id = str(prod.get("parent_id") or "")
    if ctx_map and parent_id and parent_id in ctx_map:
        row = ctx_map[parent_id]
        cp2 = row.get("category_path")
        if isinstance(cp2, list) and cp2:
            return [str(x).strip() for x in cp2 if str(x).strip()]
        bc = row.get("breadcrumb")
        if isinstance(bc, str) and bc.strip():
            # acepta "A > > > B > > > C"
            parts = [p.strip() for p in re.split(r">\s*>\s*>|>", bc) if p.strip()]
            return parts

        labels = row.get("labels", {}) or {}
        fallback = [
            labels.get("web_department") or "",
            labels.get("web_category") or "",
            labels.get("web_subcategory") or "",
        ]
        fallback = [x.strip() for x in fallback if x and x.strip()]
        if fallback:
            return fallback

    # 3) labels del producto
    labels = prod.get("labels", {}) or {}
    fallback = [
        labels.get("web_department") or "",
        labels.get("web_category") or "",
        labels.get("web_subcategory") or "",
    ]
    return [x.strip() for x in fallback if x and x.strip()]


# -------------------------
# Prompt (LONG)
# -------------------------
def build_prompt(prod: Dict[str, Any], max_chars: int, category_path: List[str]) -> str:
    labels = prod.get("labels", {}) or {}
    web_department = labels.get("web_department") or ""
    web_category = labels.get("web_category") or ""
    web_subcategory = labels.get("web_subcategory") or ""

    category_last_level = (
        prod.get("category_last_level")
        or (category_path[-1] if category_path else "")
        or web_subcategory
        or web_category
        or web_department
    )

    web_name = prod.get("web_name") or ""
    tipo_marca = prod.get("tipo_marca") or ""
    model = prod.get("model") or ""

    attrs = prod.get("attributes", {}) or {}

    candidate_keys = [
        "THD.PR.Model",
        "THD.PR.TipoMarca",
        "THD.CT.MATERIAL",
        "THD.CT.COLOR",
        "THD.CT.ALTO",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.PESO",
        "THD.CT.PROFUNDIDAD",
        "THD.CT.CAPACIDAD",
        "THD.CT.POTENCIA",
        "THD.CT.VELOCIDAD",
        "THD.CT.TIPODELUZ",
        "THD.CT.LUZ",
    ]

    selected: List[str] = []
    for k in candidate_keys:
        val = pick_first(attrs.get(k))
        if val:
            selected.append(f"{k}={val}")
        if len(selected) >= 10:
            break

    selected_block = "\n".join(selected) if selected else "N/A"
    category_path_str = " > ".join(category_path) if category_path else "N/A"

    return f"""
Eres redactor eCommerce. Genera UNA descripción larga de producto para PDP en español neutro.

REGLAS OBLIGATORIAS:
- 1 solo párrafo (sin viñetas, sin títulos, sin saltos de línea).
- Máximo {max_chars} caracteres (contando espacios).
- No inventes especificaciones, materiales, medidas, compatibilidades, ni claims.
- No menciones precio, promos, envíos, disponibilidad, ni garantía.
- No repitas el nombre del producto de forma innecesaria (úsalo 1 vez o 0 veces si se entiende sin él).
- Debe diferenciarse de una short description: más detalle y contexto de uso, pero sin exagerar.

CONTEXTO DE CATEGORÍA:
- Ruta: {category_path_str}
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- Último nivel (display): {category_last_level}

DATOS DEL PRODUCTO:
- WebName: {web_name}
- TipoMarca: {tipo_marca}
- Modelo: {model}

ATRIBUTOS DISPONIBLES (key=value):
{selected_block}

ENTREGA:
- Devuelve SOLO el párrafo final (sin comillas).
""".strip()


# -------------------------
# LLM call
# -------------------------
@dataclass
class LLMConfig:
    model: str
    max_output_tokens: int = 450
    timeout_s: int = 60
    sleep_s: float = 0.15
    temperature: Optional[float] = None


def model_supports_temperature(model: str) -> bool:
    m = (model or "").lower()
    if m.startswith("gpt-5"):
        return False
    return True


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
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    out_text.append(c.text)

    return normalize_ws(" ".join(out_text))


# -------------------------
# XML outputs
# -------------------------
def build_delta_xml(rows: List[Dict[str, Any]], attr_id: str, value_field: str) -> str:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<STEP-ProductInformation>")
    parts.append("  <Products>")
    for r in rows:
        if r.get("decision") != "generate":
            continue
        pid = r.get("product_id")
        val = r.get(value_field)
        if not pid or not val:
            continue
        parts.append(f'    <Product ID="{escape(str(pid))}">')
        parts.append("      <Values>")
        parts.append(f'        <Value AttributeID="{escape(attr_id)}">{escape(str(val))}</Value>')
        parts.append("      </Values>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</STEP-ProductInformation>")
    return "\n".join(parts) + "\n"


def build_preview_context_xml(context_rows: List[Dict[str, Any]]) -> str:
    """
    XML SOLO PARA DEMO / VISUAL.
    No es delta STEP (no usa Values/AttributeID).
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
        category_path = r.get("category_path_str") or ""
        parts.append(f'    <Product id="{escape(str(pid))}">')
        parts.append(f"      <WebName>{escape(str(web_name))}</WebName>")
        parts.append(f"      <ParentID>{escape(str(parent_id))}</ParentID>")
        parts.append(f"      <CategoryPath>{escape(str(category_path))}</CategoryPath>")
        parts.append("    </Product>")
    parts.append("  </Products>")
    parts.append("</GOAT-Preview>")
    return "\n".join(parts) + "\n"


# -------------------------
# Main
# -------------------------
def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Input products JSONL (features per product)")
    p.add_argument("--out-jsonl", dest="out_jsonl", required=True, help="Output results JSONL")
    p.add_argument("--out-xml", dest="out_xml", required=True, help="Output STEPXML delta file")
    p.add_argument("--model", default="gpt-4.1-mini", help="Model name")
    p.add_argument("--limit", type=int, default=0, help="Limit products (0 = no limit)")
    p.add_argument("--max-chars", type=int, default=1200, help="Max chars per long description")
    p.add_argument("--attr-id", default="THD.PR.WebLongDescription", help="STEP AttributeID to write back")
    p.add_argument("--temperature", type=float, default=-1.0, help="Temperature (ignored for models that don't support it)")
    p.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between calls")
    p.add_argument("--dry-run", action="store_true", help="Do not call LLM; only output prompts preview")

    # NEW (context/preview)
    p.add_argument("--category-context", default="", help="Path to category_context_dir.jsonl to resolve category paths")
    p.add_argument("--out-preview-jsonl", default="", help="Output JSONL with product_id -> web_name + category_path")
    p.add_argument("--out-preview-xml", default="", help="Output preview XML (for demo) with web_name + category_path")

    # Logging
    p.add_argument("--log-every", type=int, default=1, help="Print progress every N products (default 1)")
    args = p.parse_args()

    cfg = LLMConfig(
        model=args.model,
        sleep_s=args.sleep,
        temperature=None if args.temperature < 0 else float(args.temperature),
    )

    in_path = Path(args.in_path)
    out_jsonl = Path(args.out_jsonl)
    out_xml = Path(args.out_xml)

    ctx_map: Optional[Dict[str, Dict[str, Any]]] = None
    if args.category_context.strip():
        ctx_path = Path(args.category_context)
        if not ctx_path.exists():
            raise RuntimeError(f"--category-context not found: {ctx_path}")
        ctx_map = load_category_context_map(ctx_path)

    preview_rows: List[Dict[str, Any]] = []
    rows_out: List[Dict[str, Any]] = []
    generated_rows_for_xml: List[Dict[str, Any]] = []

    t_batch0 = perf_counter()
    processed = 0
    generated = 0
    skipped = 0

    for prod in read_jsonl(in_path):
        if args.limit and processed >= args.limit:
            break

        t0 = perf_counter()

        pid = prod.get("product_id")
        web_name = prod.get("web_name")
        parent_id = prod.get("parent_id")

        category_path = resolve_category_path_for_product(prod, ctx_map)
        category_path_str = " > ".join(category_path) if category_path else ""

        record: Dict[str, Any] = {
            "product_id": pid,
            "parent_id": parent_id,
            "web_name": web_name,
            "category_last_level": (category_path[-1] if category_path else (prod.get("category_last_level") or "")),
            "category_path": category_path,
            "category_path_str": category_path_str,
            "source_file": prod.get("source_file"),
            "model": cfg.model,
            "decision": "generate",
            "skip_reasons": [],
        }

        # Preview mapping (siempre lo registramos si hay pid)
        if pid:
            preview_rows.append(
                {
                    "product_id": pid,
                    "web_name": web_name,
                    "parent_id": parent_id,
                    "category_path": category_path,
                    "category_path_str": category_path_str,
                }
            )

        if not pid:
            record["decision"] = "skip"
            record["skip_reasons"].append("missing_product_id")
            rows_out.append(record)
            processed += 1
            skipped += 1
            continue

        prompt = build_prompt(prod, max_chars=args.max_chars, category_path=category_path)

        if args.dry_run:
            record["decision"] = "skip"
            record["skip_reasons"].append("dry_run")
            record["prompt_preview"] = prompt[:900]
            rows_out.append(record)
            processed += 1
            skipped += 1
            continue

        text = call_llm(prompt, cfg)
        text = to_single_paragraph(text)
        text = clamp_chars(text, args.max_chars)

        if len(text) < 80:
            record["decision"] = "skip"
            record["skip_reasons"].append("too_short_after_generation")
            record["web_long_description"] = None
            skipped += 1
        else:
            record["web_long_description"] = text
            generated_rows_for_xml.append(record)
            generated += 1

        rows_out.append(record)
        processed += 1

        dt = perf_counter() - t0
        if args.log_every and (processed % args.log_every == 0):
            print(
                f"[{processed}] id={pid} | gen={record['decision']=='generate'} | "
                f"chars={(len(record.get('web_long_description') or '') if record.get('web_long_description') else 0)} | "
                f"time={dt:.2f}s"
            )

        time.sleep(cfg.sleep_s)

    # Outputs
    write_jsonl(out_jsonl, rows_out)

    delta_xml = build_delta_xml(
        generated_rows_for_xml,
        attr_id=args.attr_id,
        value_field="web_long_description",
    )
    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text(delta_xml, encoding="utf-8")

    # Preview outputs (optional)
    if args.out_preview_jsonl.strip():
        out_prev_jsonl = Path(args.out_preview_jsonl)
        write_jsonl(out_prev_jsonl, preview_rows)

    if args.out_preview_xml.strip():
        out_prev_xml = Path(args.out_preview_xml)
        out_prev_xml.parent.mkdir(parents=True, exist_ok=True)
        out_prev_xml.write_text(build_preview_context_xml(preview_rows), encoding="utf-8")

    t_batch = perf_counter() - t_batch0
    print(f"OK: wrote JSONL -> {out_jsonl} ({len(rows_out)} rows)")
    print(f"OK: wrote STEPXML delta -> {out_xml} ({len(generated_rows_for_xml)} products)")
    print(f"STATS: processed={processed} generated={generated} skipped={skipped} total_time={t_batch:.2f}s avg_per_product={(t_batch/processed if processed else 0):.2f}s")


if __name__ == "__main__":
    main()
