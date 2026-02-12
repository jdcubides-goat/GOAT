from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Optional, List, Iterator
import json
import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


WEB_HR_ORDER = ["THD.HR.WebDepartment", "THD.HR.WebCategory", "THD.HR.WebSubcategory"]
ERP_HR_ORDER = ["THD.HR.Department", "THD.HR.Class", "THD.HR.SubClass"]


# atributos que suelen servir para descripción fallback (ajusta si quieres)
DEFAULT_DESC_ATTRS = [
    "THD.PR.WebShortDescription",
    "THD.PR.Label",
    "THD.PR.BrandName",
    "THD.PR.Model",
    "THD.PR.Color",
    "THD.PR.Material",
]


@dataclass
class ProductCompact:
    product_id: str
    product_name: Optional[str]
    user_type_id: Optional[str]
    parent_id: Optional[str]

    web_hierarchy: Dict[str, Dict[str, Optional[str]]]   # attr -> {id,name}
    erp_hierarchy: Dict[str, Dict[str, Optional[str]]]   # attr -> {id,name}

    classifications: List[Dict[str, Optional[str]]]
    cross_references: List[Dict[str, Optional[str]]]

    desc_attrs: Dict[str, Dict[str, Optional[str]]]      # attr -> {id,name,unit}


def iter_product_compact(
    xml_path: str | Path,
    *,
    max_products: Optional[int] = None,
    desc_attrs: Optional[List[str]] = None,
) -> Iterator[ProductCompact]:
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    desc_attrs = desc_attrs or DEFAULT_DESC_ATTRS
    desc_set = set(desc_attrs)

    count = 0
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        if _strip_ns(elem.tag) != "Product":
            continue

        p_attrib = dict(elem.attrib)
        pid = p_attrib.get("ID", "")
        user_type_id = p_attrib.get("UserTypeID")
        parent_id = p_attrib.get("ParentID")

        name = None
        name_elem = elem.find(".//Name")
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()

        classifications: List[Dict[str, Optional[str]]] = []
        for c in elem.findall(".//ClassificationReference"):
            a = dict(c.attrib)
            classifications.append({"classification_id": a.get("ClassificationID"), "type": a.get("Type")})

        cross_refs: List[Dict[str, Optional[str]]] = []
        for r in elem.findall(".//ProductCrossReference"):
            a = dict(r.attrib)
            cross_refs.append({"product_id": a.get("ProductID"), "type": a.get("Type")})

        web_h: Dict[str, Dict[str, Optional[str]]] = {}
        erp_h: Dict[str, Dict[str, Optional[str]]] = {}
        desc: Dict[str, Dict[str, Optional[str]]] = {}

        # recorrer solo Values/Value
        for v in elem.findall(".//Value"):
            a = dict(v.attrib)
            attr_id = a.get("AttributeID")
            if not attr_id:
                continue

            v_id = a.get("ID")
            unit_id = a.get("UnitID")
            v_text = (v.text or "").strip() if v.text else None

            if attr_id.startswith("THD.HR.Web"):
                web_h[attr_id] = {"id": v_id, "name": v_text}
            elif attr_id.startswith("THD.HR.") and attr_id in ERP_HR_ORDER:
                erp_h[attr_id] = {"id": v_id, "name": v_text}
            elif attr_id in desc_set:
                desc[attr_id] = {"id": v_id, "name": v_text, "unit": unit_id}

        yield ProductCompact(
            product_id=pid,
            product_name=name,
            user_type_id=user_type_id,
            parent_id=parent_id,
            web_hierarchy=web_h,
            erp_hierarchy=erp_h,
            classifications=classifications,
            cross_references=cross_refs,
            desc_attrs=desc,
        )

        elem.clear()
        count += 1
        if max_products is not None and count >= max_products:
            return


def write_compact_jsonl(
    xml_path: str | Path,
    out_path: str | Path,
    *,
    max_products: Optional[int] = None,
    desc_attrs: Optional[List[str]] = None,
) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in iter_product_compact(xml_path, max_products=max_products, desc_attrs=desc_attrs):
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
            n += 1
    return n
