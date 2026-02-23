from __future__ import annotations

from typing import Dict, Any, Iterator, Optional
from pathlib import Path
from lxml import etree

from stepxml_reader import XmlStreamReader


def get_child_text(elem: etree._Element, child_local: str) -> Optional[str]:
    # Busca hijo por localname (sin namespace)
    for ch in elem:
        if etree.QName(ch).localname == child_local:
            txt = (ch.text or "").strip()
            return txt or None
    return None


def extract_product(elem: etree._Element) -> Dict[str, Any]:
    pid = (elem.get("ID") or "").strip() or None
    user_type = (elem.get("UserTypeID") or "").strip() or None
    parent_id = (elem.get("ParentID") or "").strip() or None

    # Name en STEP a veces está vacío o viene con locale / children
    name = None
    for ch in elem:
        if etree.QName(ch).localname == "Name":
            # puede ser texto directo o subnodos
            txt = (ch.text or "").strip()
            if txt:
                name = txt
            else:
                # si tiene hijos, concatenamos textos
                txt2 = " ".join([(c.text or "").strip() for c in ch if (c.text or "").strip()])
                name = txt2 or None
            break

    # Values: AttributeID puede repetirse -> lista
    values: Dict[str, list[str]] = {}

    for ch in elem:
        if etree.QName(ch).localname == "Values":
            for v in ch:
                if etree.QName(v).localname != "Value":
                    continue

                aid = (v.get("AttributeID") or "").strip()
                if not aid:
                    continue

                # el valor puede estar en v.text o dentro de hijos (ej: <Value><Value>...</Value></Value>)
                val = (v.text or "").strip()

                if not val:
                    # buscar texto en descendientes
                    texts = []
                    for sub in v.iter():
                        if sub is v:
                            continue
                        t = (sub.text or "").strip()
                        if t:
                            texts.append(t)
                    val = " ".join(texts).strip()

                if val:
                    values.setdefault(aid, []).append(val)

    return {
        "product_id": pid,
        "name": name,
        "user_type": user_type,
        "parent_id": parent_id,
        "values": values,   # <- cambia de attributes a values (listas)
    }


def iter_products_from_file(xml_path: Path, limit: Optional[int] = None) -> Iterator[Dict[str, Any]]:
    # match_localname=True para evitar problemas de namespaces
    for elem in XmlStreamReader.stream_elements(str(xml_path), "Product", limit=limit, match_localname=True):
        yield extract_product(elem)
