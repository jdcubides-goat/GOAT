from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple
import json
import xml.etree.ElementTree as ET
from collections import Counter


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


@dataclass
class ProductIntrospection:
    id: str
    user_type_id: Optional[str]
    parent_id: Optional[str]
    name: Optional[str]
    top_inner_tags: List[Tuple[str, int]]
    sample_inner_nodes: List[Dict[str, object]]  # tag, attrib_keys, path


def _iter_descendants(elem: ET.Element) -> Iterator[Tuple[str, ET.Element]]:
    for child in elem.iter():
        yield _strip_ns(child.tag), child


def introspect_products(
    xml_path: str | Path,
    *,
    max_products: int = 10,
    top_n_tags: int = 25,
    sample_nodes: int = 40,
) -> List[ProductIntrospection]:
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    out: List[ProductIntrospection] = []
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        if _strip_ns(elem.tag) != "Product":
            continue

        attrib = dict(elem.attrib)
        pid = attrib.get("ID", "")
        user_type_id = attrib.get("UserTypeID")
        parent_id = attrib.get("ParentID")

        name = None
        name_elem = elem.find(".//Name")
        if name_elem is not None and name_elem.text:
            name = name_elem.text.strip()

        # conteo de tags internos
        c = Counter()
        samples: List[Dict[str, object]] = []

        # hacemos un recorrido por descendientes (incluye el mismo Product; lo excluimos)
        for tag, node in _iter_descendants(elem):
            if tag == "Product":
                continue
            c[tag] += 1

            # toma muestra de nodos “representativos”
            if len(samples) < sample_nodes:
                samples.append(
                    {
                        "tag": tag,
                        "attrib_keys": sorted(list(node.attrib.keys())),
                        "attrib_preview": {k: node.attrib.get(k) for k in list(node.attrib.keys())[:5]},
                        "text_preview": (node.text or "").strip()[:120],
                    }
                )

        rec = ProductIntrospection(
            id=pid,
            user_type_id=user_type_id,
            parent_id=parent_id,
            name=name,
            top_inner_tags=c.most_common(top_n_tags),
            sample_inner_nodes=samples,
        )
        out.append(rec)

        elem.clear()

        if len(out) >= max_products:
            break

    return out


def write_introspection_json(
    xml_path: str | Path,
    out_path: str | Path,
    *,
    max_products: int = 10,
) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    records = introspect_products(xml_path, max_products=max_products)
    payload = [asdict(r) for r in records]
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(records)
