#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# Cargar variables del .env (OPENAI_API_KEY, etc.)
load_dotenv()


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


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_category_path(labels: Dict[str, Any]) -> str:
    parts = []
    for k in ("web_department", "web_category", "web_subcategory"):
        v = (labels.get(k) or "").strip()
        if v:
            parts.append(v)
    return " > > > ".join(parts)


def build_prompt(category: Dict[str, Any]) -> str:
    labels = category.get("labels", {}) or {}
    signals = category.get("signals", {}) or {}

    web_department = labels.get("web_department") or ""
    web_category = labels.get("web_category") or ""
    web_subcategory = labels.get("web_subcategory") or ""
    products_count = int(category.get("products_count") or 0)

    keywords = (category.get("keywords") or [])[:20]
    recommended_focus = (category.get("recommended_focus") or [])[:8]

    evidence = category.get("evidence", {}) or {}
    sample_web_names = evidence.get("sample_web_names") or category.get("sample_web_names") or []
    sample_web_names = sample_web_names[:10]

    signal_summary = {
        "has_dimensions": bool(signals.get("has_dimensions")),
        "has_material": bool(signals.get("has_material")),
        "has_color": bool(signals.get("has_color")),
        "has_model": bool(signals.get("has_model")),
        "is_tech_like": bool(signals.get("is_tech_like")),
        "is_home_like": bool(signals.get("is_home_like")),
    }

    return f"""
Eres un redactor de catálogo eCommerce. Tu tarea es escribir UNA descripción breve de categoría, en español neutro, para ayudar a compradores a entender qué incluye la categoría.

REGLAS:
- No inventes especificaciones, marcas, números ni claims técnicos no soportados.
- No menciones precios, promociones, garantías, envíos ni disponibilidad.
- No hagas listas con viñetas; solo 1 párrafo.
- Longitud objetivo: 2 a 4 frases (máx. ~70-90 palabras).
- Mantén coherencia con el contexto de la categoría. Si el contexto es pobre o genérico, responde exactamente: "SKIP".

CONTEXTO:
- Departamento: {web_department}
- Categoría: {web_category}
- Subcategoría: {web_subcategory}
- #Productos analizados: {products_count}
- Palabras frecuentes: {", ".join(keywords) if keywords else "N/A"}
- Enfoques recomendados: {", ".join(recommended_focus) if recommended_focus else "N/A"}
- Señales: {json.dumps(signal_summary, ensure_ascii=False)}
- Ejemplos de nombres (muestra): {" | ".join(sample_web_names) if sample_web_names else "N/A"}

ENTREGA:
- Devuelve SOLO el texto final (o "SKIP").
""".strip()


@dataclass
class LLMConfig:
    model: str
    temperature: float = 0.2
    max_tokens: int = 220
    timeout_s: int = 60


def extract_response_text(resp: Any) -> str:
    out_text: List[str] = []
    for item in getattr(resp, "output", []) or []:
        if getattr(item, "type", None) == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", None) == "output_text":
                    out_text.append(getattr(c, "text", "") or "")
    return normalize_ws(" ".join(out_text))


def call_llm(prompt: str, cfg: LLMConfig) -> str:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Install it with: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    client = OpenAI(api_key=api_key)

    payload = dict(
        model=cfg.model,
        input=[
            {"role": "system", "content": "Responde con precisión y sin inventar información."},
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=cfg.max_tokens,
        timeout=cfg.timeout_s,
    )

    # Algunos modelos (p.ej. gpt-5-*) rechazan temperature.
    # Estrategia: intentar con temperature, y si da 400 por ese param, reintentar sin él.
    try:
        resp = client.responses.create(**payload, temperature=cfg.temperature)
        return extract_response_text(resp)
    except Exception as e:
        msg = str(e)
        if "Unsupported parameter" in msg and "temperature" in msg:
            resp = client.responses.create(**payload)
            return extract_response_text(resp)
        raise


def should_generate(category: Dict[str, Any]) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    if not category.get("generate_category_description", False):
        reasons.append("flag_generate_category_description_false")

    labels = category.get("labels", {}) or {}
    if not (labels.get("web_subcategory") or labels.get("web_category") or labels.get("web_department")):
        reasons.append("missing_labels")

    products_count = int(category.get("products_count") or 0)
    if products_count < 30:
        reasons.append("too_few_products")

    keywords = category.get("keywords") or []
    if len(keywords) < 5:
        reasons.append("too_few_keywords")

    recommended_focus = category.get("recommended_focus") or []
    if len(recommended_focus) == 0:
        reasons.append("missing_recommended_focus")

    return (len(reasons) == 0, reasons)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="in_path", required=True, help="Input category_insights.jsonl")
    p.add_argument("--out", dest="out_path", required=True, help="Output category_descriptions.jsonl")
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"), help="LLM model name")
    p.add_argument("--dry-run", action="store_true", help="Do not call LLM; just print what would run")
    p.add_argument("--limit", type=int, default=0, help="Limit categories processed (0 = no limit)")
    p.add_argument("--sleep", type=float, default=0.15, help="Sleep seconds between calls")
    args = p.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    cfg = LLMConfig(model=args.model)

    rows_out: List[Dict[str, Any]] = []
    processed = 0

    for cat in read_jsonl(in_path):
        if args.limit and processed >= args.limit:
            break

        labels = cat.get("labels", {}) or {}
        category_key = cat.get("category_key") or labels.get("parent_id")
        category_path = build_category_path(labels)

        ok, reasons = should_generate(cat)

        # SALIDA LIMPIA (JSON)
        record: Dict[str, Any] = {
            "category_key": category_key,
            "category_path": category_path,
        }

        if not ok:
            record["description"] = None
            record["skip_reasons"] = reasons
            rows_out.append(record)
            processed += 1
            continue

        prompt = build_prompt(cat)

        if args.dry_run:
            record["description"] = None
            record["skip_reasons"] = ["dry_run"]
            rows_out.append(record)
            processed += 1
            continue

        text = call_llm(prompt, cfg)

        if text.strip().upper() == "SKIP" or len(text.strip()) < 20:
            record["description"] = None
            record["skip_reasons"] = ["llm_returned_skip_or_too_short"]
        else:
            record["description"] = text

        rows_out.append(record)
        processed += 1
        time.sleep(args.sleep)

    write_jsonl(out_path, rows_out)
    print(f"OK: wrote {len(rows_out)} rows to {out_path}")


if __name__ == "__main__":
    main()
