from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM_STEPMDM = (
    "Eres un asistente de enriquecimiento de contenido para un PIM/MDM (Stibo STEP) en eCommerce. "
    "Escribe en español (México) con tono comercial, claro y profesional. "
    "Reglas estrictas: "
    "1) No inventes especificaciones técnicas, materiales, dimensiones, compatibilidades, certificaciones, garantías ni claims. "
    "2) No utilices adjetivos subjetivos como funcional, práctico, resistente, duradero, premium o similares. "
    "3) Si una característica no aplica a todos los productos, usa expresiones como 'según el producto' o 'puedes encontrar opciones con'. "
    "4) El título debe ser corto, neutro y sin calificativos innecesarios. "
    "5) La descripción debe ser un solo párrafo breve (250–450 caracteres) orientado a navegación de categoría. "
    "6) Devuelve únicamente JSON válido. No agregues texto adicional."
)
USER_TEMPLATE_STEPMDM = """\
CONTEXTO STIBO STEP:
Este contenido se almacenará como descripción editorial de categoría para eCommerce.

DATOS DISPONIBLES (NO INVENTAR):
Jerarquía web: {web_department} > {web_category} > {web_subcategory}
category_key: {category_key}
Cantidad de productos: {product_count}

Términos frecuentes en productos:
{top_terms_json}

Ejemplos representativos:
{examples_json}

INSTRUCCIONES:
Genera una descripción clara para explicar al cliente qué encontrará en esta categoría.
No incluyas características que no estén sustentadas por los términos o ejemplos.
Usa lenguaje neutro y objetivo.

SALIDA JSON ESTRICTA:
{{
  "category_key": "{category_key}",
  "title": "Nombre de la categoría sin adjetivos",
  "description": "Un solo párrafo breve explicando qué productos incluye y su propósito general."
}}
"""



def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run AI enrichment for categories (minimal schema).")
    p.add_argument("--jobs", required=True, help="outputs/ai_jobs_categories_v1.jsonl")
    p.add_argument("--out", required=True, help="outputs/category_enriched_v1.jsonl")
    p.add_argument("--model", default=None, help="Override model (else uses OPENAI_MODEL or fallback)")
    p.add_argument("--max", type=int, default=None, help="Optional limit of jobs")
    return p.parse_args()


def sanitize_payload(payload: dict, fallback_category_key: str) -> dict:
    allowed_fields = {"category_key", "title", "description"}

    for k in list(payload.keys()):
        if k not in allowed_fields:
            payload.pop(k, None)

    payload["category_key"] = (payload.get("category_key") or fallback_category_key or "").strip()
    payload["title"] = (payload.get("title") or "").strip()[:80]

    description = (payload.get("description") or "").strip()
    description = " ".join(description.split())
    payload["description"] = description[:600]

    if not payload["category_key"]:
        raise ValueError("category_key vacío")
    if not payload["title"]:
        raise ValueError("title vacío")
    if not payload["description"]:
        raise ValueError("description vacío")

    return payload


def main() -> int:
    args = parse_args()

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY. Define it in .env or as env var.")

    model = args.model or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"

    client = OpenAI(api_key=api_key)

    in_path = Path(args.jobs)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue

            job = json.loads(line)
            inputs = job.get("inputs", {}) or {}

            category_key = job.get("category_key", "") or ""
            prompt = USER_TEMPLATE_STEPMDM.format(
                category_key=category_key,
                web_department=inputs.get("web_department"),
                web_category=inputs.get("web_category"),
                web_subcategory=inputs.get("web_subcategory"),
                product_count=inputs.get("product_count"),
                top_terms_json=json.dumps(inputs.get("top_terms", []), ensure_ascii=False),
                examples_json=json.dumps(inputs.get("examples", []), ensure_ascii=False),
            )

            try:
                resp = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": SYSTEM_STEPMDM},
                        {"role": "user", "content": prompt},
                    ],
                )

                text = (resp.output_text or "").strip()
                payload = json.loads(text)
                payload = sanitize_payload(payload, fallback_category_key=category_key)

                fout.write(json.dumps(payload, ensure_ascii=False) + "\n")
                print(f"OK -> {payload['category_key']}")

            except Exception as e:
                # Save a debug row but keep the batch running
                err_row = {
                    "category_key": category_key,
                    "error": str(e),
                }
                # Try to store model output if available
                try:
                    err_row["raw"] = text  # may not exist if fail before assignment
                except Exception:
                    pass

                fout.write(json.dumps(err_row, ensure_ascii=False) + "\n")
                print(f"ERR -> {category_key}: {e}")

            n += 1
            if args.max is not None and n >= args.max:
                break

    print(f"Done. Wrote {n} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
