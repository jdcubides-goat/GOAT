from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterator, Optional, List
import json
import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


@dataclass
class FlatValueRow:
    product_id: str
    product_name: Optional[str]
    user_type_id: Optional[str]
    parent_id: Optional[str]
    attribute_id: str
    value_text: Optional[str]
    value_id: Optional[str]
    unit_id: Optional[str]


@dataclass
class ProductMeta:
    product_id: str
    product_name: Optional[str]
    user_type_id: Optional[str]
    parent_id: Optional[str]
    classifications: List[Dict[str, Optional[str]]]
    cross_references: List[Dict[str, Optional[str]]]


def iter_product_flat_values(xml_path: str | Path, *, max_products: Optional[int] = None) -> Iterator[FlatValueRow]:
    """
    Streaming: para cada <Product>, produce filas por cada <Value AttributeID=...>.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    product_count = 0
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        if _strip_ns(elem.tag) != "Product":
            continue

        attrib = dict(elem.attrib)
        product_id = attrib.get("ID", "")
        user_type_id = attrib.get("UserTypeID")
        parent_id = attrib.get("ParentID")

        # name
        product_name = None
        name_elem = elem.find(".//Name")
        if name_elem is not None and name_elem.text:
            product_name = name_elem.text.strip()

        # values: Value nodes with AttributeID
        for v in elem.findall(".//Value"):
            v_attrib = dict(v.attrib)
            attribute_id = v_attrib.get("AttributeID")
            if not attribute_id:
                continue

            value_text = (v.text or "").strip() if v.text else None
            value_id = v_attrib.get("ID")
            unit_id = v_attrib.get("UnitID")

            yield FlatValueRow(
                product_id=product_id,
                product_name=product_name,
                user_type_id=user_type_id,
                parent_id=parent_id,
                attribute_id=attribute_id,
                value_text=value_text,
                value_id=value_id,
                unit_id=unit_id,
            )

        elem.clear()
        product_count += 1
        if max_products is not None and product_count >= max_products:
            return


def iter_product_meta(xml_path: str | Path, *, max_products: Optional[int] = None) -> Iterator[ProductMeta]:
    """
    Streaming: extrae meta de clasificaciones y cross references por producto.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    product_count = 0
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        if _strip_ns(elem.tag) != "Product":
            continue

        attrib = dict(elem.attrib)
        product_id = attrib.get("ID", "")
        user_type_id = attrib.get("UserTypeID")
        parent_id = attrib.get("ParentID")

        product_name = None
        name_elem = elem.find(".//Name")
        if name_elem is not None and name_elem.text:
            product_name = name_elem.text.strip()

        classifications: List[Dict[str, Optional[str]]] = []
        for c in elem.findall(".//ClassificationReference"):
            c_attrib = dict(c.attrib)
            classifications.append(
                {
                    "classification_id": c_attrib.get("ClassificationID"),
                    "type": c_attrib.get("Type"),
                }
            )

        cross_refs: List[Dict[str, Optional[str]]] = []
        for r in elem.findall(".//ProductCrossReference"):
            r_attrib = dict(r.attrib)
            cross_refs.append(
                {
                    "product_id": r_attrib.get("ProductID"),
                    "type": r_attrib.get("Type"),
                }
            )

        yield ProductMeta(
            product_id=product_id,
            product_name=product_name,
            user_type_id=user_type_id,
            parent_id=parent_id,
            classifications=classifications,
            cross_references=cross_refs,
        )

        elem.clear()
        product_count += 1
        if max_products is not None and product_count >= max_products:
            return


def write_jsonl(rows: Iterator[object], out_path: str | Path) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
            n += 1
    return n
