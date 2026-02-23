from __future__ import annotations

import os
import time
from typing import List

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def require_openai() -> None:
    if OpenAI is None:
        raise RuntimeError("Falta instalar openai. Ejecuta: pip install openai")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError("Falta OPENAI_API_KEY en tu .env / environment.")


def call_llm_text(prompt: str, model: str = "gpt-4.1-mini", max_output_tokens: int = 300) -> tuple[str, float]:
    require_openai()
    t0 = time.perf_counter()
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY").strip())

    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": "Responde con precisión. No inventes datos. Entrega solo el texto final solicitado."},
            {"role": "user", "content": prompt},
        ],
        max_output_tokens=max_output_tokens,
        timeout=120,
    )

    out: List[str] = []
    for item in resp.output:
        if item.type == "message":
            for c in item.content:
                if c.type == "output_text":
                    out.append(c.text)

    text = " ".join(out).strip()
    dt = time.perf_counter() - t0
    return text, dt
