import os
import json
import time
from typing import Dict, Any, Iterable, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError("Falta OPENAI_API_KEY en .env")

client = OpenAI(api_key=API_KEY)

SYSTEM_PROMPT = """Eres un redactor técnico de e-commerce para un sistema MDM (Stibo STEP).
Tu tarea es generar una descripción breve de categoría basada SOLO en señales y ejemplos entregados.
No inventes medidas, materiales, garantías, certificaciones ni compatibilidades.
No uses adjetivos subjetivos (ej. “resistente”, “práctico”, “funcional”, “premium”).
Usa español de México (es-MX). Tono profesional y claro.
Salida ESTRICTAMENTE en JSON con las llaves: category_key, title, description.
"""

USER_PROMPT_TEMPLATE = """Genera un JSON para una categoría.

Reglas:
- title: 4 a 8 palabras, sin MAYÚSCULAS sostenidas, sin claims.
- description: un párrafo (250–450 caracteres aprox). Debe explicar “qué se encuentra aquí” y “para qué sirve” de forma neutral.
- No menciones “según la data” ni “según el catálogo”.
- No agregues keywords, FAQs, guías de compra, bullets.

Datos de entrada:
{payload}
"""

def call_llm(payload: Dict[str, Any], max_retries: int = 3) -> Dict[str, Any]:
    user_prompt = USER_PROMPT_TEMPLATE.format(payload=json.dumps(payload, ensure_ascii=False))

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
            )
            text = resp.choices[0].message.content.strip()

            # El modelo debe devolver JSON puro, pero por robustez:
            if text.startswith("```"):
                text = text.strip("`")
                # intenta encontrar el primer { ... }
                start = text.find("{")
                end = text.rfind("}")
                text = text[start:end+1].strip()

            obj = json.loads(text)

            # Validaciones mínimas
            for k in ("category_key", "title", "description"):
                if k not in obj:
                    raise ValueError(f"Falta llave requerida: {k}")

            # fuerza category_key al del job para evitar drift
            obj["category_key"] = payload.get("category_key", obj["category_key"])

            return obj

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))

    raise RuntimeError("No se pudo generar respuesta")

def iter_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def main(in_jobs: str, out_path: str, limit: Optional[int] = None):
    results = []
    count = 0

    with open(out_path, "w", encoding="utf-8") as out:
        for job in iter_jsonl(in_jobs):
            if job.get("job_type") != "category_enrichment":
                continue

            payload = job.copy()

            # (Opcional) recorta top_terms por si viene muy grande
            inputs = payload.get("inputs", {})
            if isinstance(inputs.get("top_terms"), list):
                inputs["top_terms"] = inputs["top_terms"][:35]
            if isinstance(inputs.get("examples"), list):
                inputs["examples"] = inputs["examples"][:8]
            payload["inputs"] = inputs

            obj = call_llm(payload)

            out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1
            print(f"[OK] {count}: {obj['category_key']}")

            if limit and count >= limit:
                break

    print(f"Listo. Generadas: {count}. Output: {out_path}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-jobs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    main(args.in_jobs, args.out, args.limit)
