from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterator, Optional, List
import json
import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


@dataclass
class ProductRecord:
    id: str
    user_type_id: Optional[str] = None
    parent_id: Optional[str] = None
    raw_attrib: Optional[Dict[str, str]] = None
    # opcional: info mínima interna (si existe)
    name: Optional[str] = None


def iter_products(xml_path: str | Path, *, max_products: Optional[int] = None) -> Iterator[ProductRecord]:
    """
    Streaming parse: itera solo sobre <Product ...>.
    No carga el XML completo en memoria.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    count = 0
    # iterparse end-event: cuando cierra un Product, ya tenemos su contenido
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        tag = _strip_ns(elem.tag)
        if tag != "Product":
            continue

        attrib = dict(elem.attrib)
        rec = ProductRecord(
            id=attrib.get("ID", ""),
            user_type_id=attrib.get("UserTypeID"),
            parent_id=attrib.get("ParentID"),
            raw_attrib=attrib,
        )

        # Heurística opcional: buscar un Name interno (si existe)
        # Esto puede cambiar según schema STEP; si no existe, queda None.
        name_elem = elem.find(".//Name")
        if name_elem is not None and name_elem.text:
            rec.name = name_elem.text.strip()

        yield rec
        count += 1

        # liberar memoria
        elem.clear()

        if max_products is not None and count >= max_products:
            return


def write_products_jsonl(
    xml_path: str | Path,
    out_path: str | Path,
    *,
    max_products: Optional[int] = None
) -> int:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rec in iter_products(xml_path, max_products=max_products):
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
            n += 1
    return n
