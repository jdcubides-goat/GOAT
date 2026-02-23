# core/io/delta_writer.py
from __future__ import annotations

from typing import Any, Dict, List
from xml.sax.saxutils import escape as xml_escape


def build_delta_xml_products(rows: List[Dict[str, Any]], attribute_id: str, text_field: str) -> str:
    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append("<STEP-ProductInformation>")
    parts.append("  <Products>")
    for r in rows:
        pid = r.get("product_id")
        val = r.get(text_field)
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


def build_step_delta_xml(rows: List[Dict[str, Any]], attribute_id: str, text_field: str) -> str:
    # Alias “oficial” para lo que tu category_enricher ya espera
    return build_delta_xml_products(rows, attribute_id, text_field)


# Compat: algunos módulos antiguos importan este nombre
def build_step_delta_xml_products(rows: List[Dict[str, Any]], attribute_id: str, text_field: str) -> str:
    return build_delta_xml_products(rows, attribute_id, text_field)