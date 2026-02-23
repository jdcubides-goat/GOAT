from __future__ import annotations

from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

from core.models import AttributeLink, HierarchyNode
from core.utils import safe_int, norm_ws
from stepxml.reader import XmlStream, find_child, find_child_text, iter_children, iter_products


def _parse_bool(v: str) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def extract_hierarchy_from_streams(
    streams: List[XmlStream],
) -> Dict[str, HierarchyNode]:
    """
    Extract hierarchy nodes from PPH files.

    Expected structure (as in your exports):
    - <Product ID="INT.L4-..." UserTypeID="PMDM.PRD.INT.Level4" ParentID="INT.L3-...">
        <Name>...</Name>
        <AttributeLink AttributeID="THD.CT.X" Mandatory="true/false">
            <MetaData>
                <Value AttributeID="PMDM.AT.DisplaySequence">90</Value>
                <Value AttributeID="PMDM.AT.PDS.MandatoryForSubmit" ID="Y">Yes</Value>
            </MetaData>
        </AttributeLink>
      </Product>

    Merge strategy: merge attribute_links by attribute_id (later wins for metadata fields).
    """
    nodes: Dict[str, HierarchyNode] = {}

    for st in streams:
        try:
            st.fileobj.seek(0)
        except Exception:
            pass

        for p in iter_products(st):
            node_id = (p.attrib.get("ID") or "").strip()
            user_type = (p.attrib.get("UserTypeID") or "").strip()
            parent_id = (p.attrib.get("ParentID") or "").strip() or None
            if not node_id:
                continue

            name = norm_ws(find_child_text(p, "Name"))

            links: Dict[str, AttributeLink] = {}
            for al in iter_children(p, "AttributeLink"):
                attr_id = (al.attrib.get("AttributeID") or "").strip()
                if not attr_id:
                    continue
                mandatory = _parse_bool(al.attrib.get("Mandatory"))
                link = AttributeLink(attribute_id=attr_id, mandatory=mandatory)

                md = find_child(al, "MetaData")
                if md is not None:
                    for v in iter_children(md, "Value"):
                        md_attr = (v.attrib.get("AttributeID") or "").strip()
                        txt = norm_ws(v.text or "")
                        vid = (v.attrib.get("ID") or "").strip() or None

                        if md_attr == "PMDM.AT.DisplaySequence":
                            link.display_sequence = safe_int(txt)
                        elif md_attr == "PMDM.AT.PDS.MandatoryForSubmit":
                            link.mandatory_for_submit_value = txt or None
                            link.mandatory_for_submit_code = vid

                links[attr_id] = link

            if node_id in nodes:
                ex = nodes[node_id]
                # merge scalar
                if user_type:
                    ex.user_type_id = user_type
                if parent_id:
                    ex.parent_id = parent_id
                if name:
                    ex.name = name
                # merge links
                existing_by_attr = {l.attribute_id: l for l in ex.attribute_links}
                for attr_id, link in links.items():
                    existing_by_attr[attr_id] = link
                ex.attribute_links = list(existing_by_attr.values())
            else:
                nodes[node_id] = HierarchyNode(
                    node_id=node_id,
                    user_type_id=user_type,
                    parent_id=parent_id,
                    name=name,
                    attribute_links=list(links.values()),
                )

    return nodes
