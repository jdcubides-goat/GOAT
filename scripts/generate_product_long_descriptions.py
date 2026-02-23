#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from lxml import etree

try:
    from openai import OpenAI
    from openai import BadRequestError
except Exception:
    OpenAI = None
    BadRequestError = Exception


# ----------------------------
# Helpers JSONL
# ----------------------------
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


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


# ----------------------------
# STEPXML parsing (ProductSampleData)
# ----------------------------
def iter_product_files(xml_dir: Path) -> List[Path]:
    files = sorted([p for p in xml_dir.glob("*.xml") if p.is_file()])
    # Prefer ProductSampleData first, but keep all.
    return files


def iter_products_from_productsample(xml_path: Path) -> Iterable[Dict[str, Any]]:
    """
    Yields dict:
      {
        "product_id": "...",
        "parent_id": "...",
        "name": "...",
        "values": { AttributeID: [values...] }
      }
    """
    # stream parse to support 60MB+ files
    context = etree.iterparse(str(xml_path), events=("end",), tag="Product")
    for _, elem in context:
        try:
            user_type = elem.get("UserTypeID") or ""
            if user_type != "PMDM.PRD.GoldenRecord":
                elem.clear()
                continue

            product_id = elem.get("ID") or ""
            parent_id = elem.get("ParentID") or ""

            # <Name> optional
            name_node = elem.find("Name")
            name = (name_node.text or "").strip() if name_node is not None else ""

            values_node = elem.find("Values")
            values: Dict[str, List[str]] = {}

            if values_node is not None:
                for v in values_node.findall("Value"):
                    aid = v.get("AttributeID") or ""
                    txt = (v.text or "").strip()
                    if not aid or not txt:
                        continue
                    values.setdefault(aid, []).append(txt)

                # MultiValue -> Value inside
                for mv in values_node.findall("MultiValue"):
                    aid = mv.get("AttributeID") or ""
                    if not aid:
                        continue
                    for subv in mv.findall("Value"):
                        txt = (subv.text or "").strip()
                        if txt:
                            values.setdefault(aid, []).append(txt)

            yield {
                "product_id": product_id,
                "parent_id": parent_id,
                "name": name,
                "values": values,
                "source_file": xml_path.name,
            }
        finally:
            # important for memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]


# ----------------------------
# PPH parsing (optional)
# ----------------------------
def load_pph_tree(pph_path: Path) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Returns node_map:
      node_id -> {"name": str|None, "parent_id": str|None, "user_type": str|None}
    This supports PPH exports that come as Product nodes (as in your sample).
    """
    node_map: Dict[str, Dict[str, Optional[str]]] = {}
    context = etree.iterparse(str(pph_path), events=("end",), tag=("Entity", "Product"))
    for _, elem in context:
        node_id = elem.get("ID")
        if not node_id:
            elem.clear()
            continue

        user_type = elem.get("UserTypeID")
        # Parent reference sometimes appears as attribute, sometimes as child
        parent_id = elem.get("ParentID")
        if not parent_id:
            pid_node = elem.find("ParentID")
            parent_id = (pid_node.text or "").strip() if pid_node is not None else None
        if parent_id == "":
            parent_id = None

        name_node = elem.find("Name")
        name = (name_node.text or "").strip() if name_node is not None else None
        if name == "":
            name = None

        node_map[node_id] = {"name": name, "parent_id": parent_id, "user_type": user_type}
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]
    return node_map


def build_breadcrumb(parent_id: str, node_map: Dict[str, Dict[str, Optional[str]]], max_hops: int = 10) -> List[str]:
    """
    Walk up from INT.L4-... to parent nodes if present.
    Returns list of names from top->bottom (best-effort).
    """
    if not parent_id or parent_id not in node_map:
        return []

    names: List[str] = []
    cur = parent_id
    hops = 0
    while cur and hops < max_hops and cur in node_map:
        n = node_map[cur].get("name")
        if n:
            names.append(n)
        cur = node_map[cur].get("parent_id") or ""
        hops += 1

    names.reverse()
    return names


# ----------------------------
# LLM prompt (Caso 1)
# ----------------------------
def pick_product_context(values: Dict[str, List[str]]) -> Dict[str, Any]:
    """
    Minimal, high-signal fields for long description.
    We DO NOT dump 400 attrs; we pick key ones + top tech signals.
    """
    def first(aid: str) -> str:
        return values.get(aid, [""])[0]

    web_name = first("THD.PR.WebName")
    web_short = first("THD.PR.WebShortDescription")
    web_long_existing = first("THD.PR.WebLongDescription")

    dept = first("THD.HR.WebDepartment") or first("THD.HR.Department")
    cat = first("THD.HR.WebCategory")
    subcat = first("THD.HR.WebSubcategory")

    # Common identity / commercial
    brand = first("THD.PR.TipoMarca") or first("THD.PR.BrandID")
    model = first("THD.PR.Model") or first("THD.CT.MODELO")
    gtin = first("PMDM.AT.GTIN")

    # Common tech/logistic attributes (optional, only if present)
    tech_candidates = [
        "THD.CT.COLOR",
        "THD.CT.MATERIAL",
        "THD.CT.ALTO",
        "THD.CT.ANCHO",
        "THD.CT.LARGO",
        "THD.CT.PESO",
        "THD.PR.EachPeso",
    ]
    tech: Dict[str, str] = {}
    for aid in tech_candidates:
        v = first(aid)
        if v:
            tech[aid] = v

    return {
        "web_name": web_name,
        "web_short": web_short,
        "web_long_existing": web_long_existing,
        "web_department": dept,
        "web_category": cat,
        "web_subcategory": subcat,
        "brand": brand,
        "model": model,
        "gtin": gtin,
        "tech": tech,
    }


def build_prompt_case1(product: Dict[str, Any], breadcrumb: List[str]) -> str:
    values: Dict[str, List[str]] = product["values"]
    ctx = pick_product_context(values)

    # If context is too thin, we skip (no inventar)
    # Still allow generation if we have WebName + (short OR some tech OR category labels)
    has_min = bool(ctx["web_name"]) and (
        bool(ctx["web_short"]) or bool(ctx["tech"]) or bool(ctx["web_subcategory"]) or bool(breadcrumb)
    )
    if not has_min:
        return "SKIP"

    breadcrumb_str = " > ".join(breadcrumb) if breadcrumb else ""
    labels_str = " > ".join([x for x in [ctx["web_department"], ctx["web_category"], ctx["web_subcategory"]] if x])

    # Provide only a compact attribute payload
    tech_lines = []
    for k, v in ctx["tech"].items():
        tech_lines.append(f"- {k}: {v}")
    tech_block = "\n".join(tech_lines) if tech_lines else "N/A"

    return f"""
Eres un redactor eCommerce senior. Genera UNA descripción larga en español neutro para un producto, basada SOLO en la información disponible.

REGLAS (obligatorio):
- No inventes especificaciones, compatibilidades, certificaciones ni beneficios no sustentados.
- No menciones precios, promociones, garantía, envío, stock, devoluciones.
- No uses viñetas. Solo 2 a 4 párrafos.
- Longitud objetivo: 120 a 220 palabras.
- Evita repetir el nombre del producto más de una vez.
- Si la información es insuficiente para una descripción útil, responde exactamente: "SKIP".

CONTEXTO DEL PRODUCTO:
- Product ID: {product.get("product_id","")}
- Nombre web (si existe): {ctx["web_name"] or product.get("name","")}
- Descripción corta (si existe): {ctx["web_short"] or "N/A"}
- Jerarquía (labels en producto): {labels_str or "N/A"}
- Breadcrumb (PPH si existe): {breadcrumb_str or "N/A"}
- Marca: {ctx["brand"] or "N/A"}
- Modelo: {ctx["model"] or "N/A"}
- GTIN: {ctx["gtin"] or "N/A"}
- Atributos técnicos disponibles:
{tech_block}

NOTA:
- Si ya existe una descripción larga y es buena, puedes mejorar redacción y orden sin cambiar el sentido.
- Descripción larga existente (si existe): {ctx["web_long_existing"] or "N/A"}

ENTREGA:
- Devuelve SOLO el texto final (o "SKIP").
""".strip()


# ----------------------------
# OpenAI calling
# ----------------------------
@dataclass
class LLMConfig:
    model: str
    temperature: Optional[float] = 0.2
    max_tokens: int = 380
    timeout_s: int = 60


def call_llm(prompt: str, cfg: LLMConfig, client: Any) -> str:
    if prompt.strip().upper() == "SKIP":
        return "SKIP"

    # First attempt: with temperature (some models reject it)
    def _request(with_temp: bool):
        kwargs = dict(
            model=cfg.model,
            input=[
                {"role": "system", "content": "Responde con precisión y sin inventar información."},
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=cfg.max_tokens,
            timeout=cfg.timeout_s,
        )
        if with_temp and cfg.temperature is not None:
            kwargs["temperature"] = cfg.temperature
        return client.responses.create(**kwargs)

    try:
        resp = _request(with_temp=True)
    except BadRequestError as e:
        msg = str(e)
        # Auto-retry if temperature is unsupported
        if "temperature" in msg and "not supported" in msg:
            resp = _request(with_temp=False)
        else:
            raise

    out_text: List[str] = []
    for item in getattr(resp, "output", []) or []:
        if getattr(item, "type", "") == "message":
            for c in getattr(item, "content", []) or []:
                if getattr(c, "type", "") == "output_text":
                    out_text.append(getattr(c, "text", ""))

    return normalize_ws(" ".join(out_text))


# ----------------------------
# Main
# ----------------------------
def main() -> None:
    load_dotenv()

    p = argparse.ArgumentParser()
    p.add_argument("--xml-dir", required=True, help="Directory with STEPXML files (data/real)")
    p.add_argument("--out", required=True, help="Output JSONL file (append if exists)")
    p.add_argument("--model", default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    p.add_argument("--pph", default="", help="Optional PPH xml path for breadcrumbs")
    p.add_argument("--limit", type=int, default=0, help="Limit products processed (0 = no limit)")
    p.add_argument("--sleep", type=float, default=0.10, help="Sleep seconds between calls")
    p.add_argument("--dry-run", action="store_true", help="Do not call LLM")
    args = p.parse_args()

    if OpenAI is None:
        raise RuntimeError("Missing dependency: openai. Install with: pip install openai")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment (.env)")

    client = OpenAI(api_key=api_key)
    cfg = LLMConfig(model=args.model)

    xml_dir = Path(args.xml_dir)
    out_path = Path(args.out)

    node_map: Dict[str, Dict[str, Optional[str]]] = {}
    if args.pph:
        pph_path = Path(args.pph)
        if pph_path.exists():
            node_map = load_pph_tree(pph_path)

    files = iter_product_files(xml_dir)
    product_files = [f for f in files if "ProductSampleData" in f.name]
    if not product_files:
        raise RuntimeError(f"No ProductSampleData xml found in: {xml_dir}")

    processed = 0

    for fpath in product_files:
        for prod in iter_products_from_productsample(fpath):
            if args.limit and processed >= args.limit:
                print(f"STOP: limit reached ({args.limit})")
                print(f"OK: wrote results to {out_path}")
                return

            breadcrumb = build_breadcrumb(prod.get("parent_id", ""), node_map) if node_map else []
            prompt = build_prompt_case1(prod, breadcrumb)

            record: Dict[str, Any] = {
                "product_id": prod.get("product_id"),
                "parent_id": prod.get("parent_id"),
                "source_file": prod.get("source_file"),
                "model": cfg.model,
                "decision": "generate",
                "skip_reasons": [],
                "breadcrumb": breadcrumb,
            }

            if prompt.strip().upper() == "SKIP":
                record["decision"] = "skip"
                record["skip_reasons"] = ["insufficient_context"]
                record["web_long_description"] = None
                append_jsonl(out_path, record)
                processed += 1
                continue

            if args.dry_run:
                record["web_long_description"] = None
                record["prompt_preview"] = prompt[:1200]
                append_jsonl(out_path, record)
                processed += 1
                continue

            text = call_llm(prompt, cfg, client)
            if text.strip().upper() == "SKIP" or len(text.strip()) < 60:
                record["decision"] = "skip"
                record["skip_reasons"] = ["llm_returned_skip_or_too_short"]
                record["web_long_description"] = None
            else:
                record["web_long_description"] = text

            append_jsonl(out_path, record)
            processed += 1
            time.sleep(args.sleep)

    print(f"OK: wrote {processed} rows to {out_path}")


if __name__ == "__main__":
    main()
