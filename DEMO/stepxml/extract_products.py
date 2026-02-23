from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from core.models import ProductRecord, ValueRecord
from core.utils import norm_ws
from stepxml.reader import XmlStream, find_child, find_child_text, iter_children, iter_products


def extract_products_from_streams(
    streams: List[XmlStream],
    allowed_user_type_ids: Optional[set[str]] = None,
) -> Dict[str, ProductRecord]:
    """
    Extract products from ProductSampleData files.
    Keep Value@ID (LOV code) when present.
    Merge strategy: attribute-level merge; later streams override scalar fields and overwrite same attribute_id.
    """
    products: Dict[str, ProductRecord] = {}

    for st in streams:
        # Reset pointer if possible (Streamlit upload objects support seek)
        try:
            st.fileobj.seek(0)
        except Exception:
            pass

        for p in iter_products(st):
            pid = (p.attrib.get("ID") or "").strip()
            user_type = (p.attrib.get("UserTypeID") or "").strip()
            parent_id = (p.attrib.get("ParentID") or "").strip() or None

            if not pid:
                continue
            if allowed_user_type_ids and user_type and user_type not in allowed_user_type_ids:
                continue

            name = norm_ws(find_child_text(p, "Name"))

            values_elem = find_child(p, "Values")
            values_map: Dict[str, ValueRecord] = {}
            if values_elem is not None:
                for v in iter_children(values_elem, "Value"):
                    attr_id = (v.attrib.get("AttributeID") or "").strip()
                    if not attr_id:
                        continue
                    text = norm_ws(v.text or "")
                    id_code = (v.attrib.get("ID") or "").strip() or None
                    if text:
                        values_map[attr_id] = ValueRecord(text=text, id_code=id_code)

            if pid in products:
                # merge
                existing = products[pid]
                # scalar override if provided
                if user_type:
                    existing.user_type_id = user_type
                if parent_id:
                    existing.parent_id = parent_id
                if name:
                    existing.name = name
                # attribute-level merge (overwrite duplicates)
                for k, vr in values_map.items():
                    existing.values[k] = vr
            else:
                products[pid] = ProductRecord(
                    product_id=pid,
                    user_type_id=user_type,
                    parent_id=parent_id,
                    name=name,
                    values=values_map,
                )

    return products
