from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass
class ProductRecord:
    product_id: str
    parent_id: str
    web_name: str
    labels: Dict[str, str]
    attributes: Dict[str, Any]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def _tag_local(tag: str) -> str:
    # "{ns}Product" -> "Product"
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _find_text_any(node: ET.Element, tags: Tuple[str, ...]) -> Optional[str]:
    # Find first child text matching local tag in tags
    for child in list(node):
        if _tag_local(child.tag) in tags:
            if child.text and child.text.strip():
                return _clean(child.text)
    return None


def _collect_values(node: ET.Element) -> List[str]:
    vals: List[str] = []
    for child in list(node):
        if child.text and child.text.strip():
            vals.append(_clean(child.text))
    return vals


def iter_products_from_step_xml(product_xml: Path, limit: int = 200) -> Iterable[ProductRecord]:
    """
    Best-effort STEP Product XML parser.
    Works with common STEP exports:
      - Product nodes with ID attribute
      - Values/Value nodes with AttributeID
      - Some label fields found as text nodes
    """
    if not product_xml.exists():
        return

    # Iterparse for memory efficiency
    ctx = ET.iterparse(str(product_xml), events=("start", "end"))
    _, root = next(ctx)  # type: ignore

    count = 0
    for event, elem in ctx:
        if event != "end":
            continue

        if _tag_local(elem.tag) not in ("Product", "product", "Products.Product"):
            continue

        # Product ID
        pid = elem.attrib.get("ID") or elem.attrib.get("Id") or elem.attrib.get("id")
        if not pid:
            elem.clear()
            continue
        pid = str(pid)

        # Parent id (best effort)
        parent_id = (
            elem.attrib.get("ParentID")
            or elem.attrib.get("ParentId")
            or elem.attrib.get("parent_id")
            or ""
        )
        parent_id = str(parent_id) if parent_id else ""

        labels: Dict[str, str] = {}
        attributes: Dict[str, Any] = {}

        # Common nodes: Values/Value with AttributeID
        for child in elem.iter():
            if _tag_local(child.tag) == "Value":
                attr_id = child.attrib.get("AttributeID") or child.attrib.get("AttributeId")
                if not attr_id:
                    continue
                # Value could have text or subnodes
                if child.text and child.text.strip():
                    v = _clean(child.text)
                    attributes[str(attr_id)] = v
                else:
                    vals = _collect_values(child)
                    if vals:
                        attributes[str(attr_id)] = vals[0] if len(vals) == 1 else vals

        # Web name heuristics
        web_name = (
            attributes.get("THD.PR.WebName")
            or attributes.get("THD.PR.WebDisplayName")
            or attributes.get("WebName")
            or ""
        )
        web_name = str(web_name) if web_name else ""

        # Department/category/subcategory heuristics
        dep = attributes.get("THD.HR.WebDepartment") or attributes.get("WebDepartment") or ""
        cat = attributes.get("THD.HR.WebCategory") or attributes.get("WebCategory") or ""
        sub = attributes.get("THD.HR.WebSubcategory") or attributes.get("WebSubcategory") or ""

        if dep:
            labels["web_department"] = str(dep)
        if cat:
            labels["web_category"] = str(cat)
        if sub:
            labels["web_subcategory"] = str(sub)

        # If parent_id not present, try from attributes
        if not parent_id:
            maybe_parent = attributes.get("THD.HR.ParentID") or attributes.get("ParentID") or ""
            parent_id = str(maybe_parent) if maybe_parent else ""

        yield ProductRecord(
            product_id=pid,
            parent_id=parent_id,
            web_name=web_name,
            labels=labels,
            attributes=attributes,
        )

        count += 1
        elem.clear()
        root.clear()  # keep memory low

        if limit is not None and count >= int(limit):
            break