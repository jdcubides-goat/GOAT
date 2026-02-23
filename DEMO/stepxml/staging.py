from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Tuple

from core.models import HierarchyNode, ProductRecord, ParseReport, StagingBundle
from core.utils import write_json, write_jsonl, ensure_dir


def build_category_paths(hierarchy: Dict[str, HierarchyNode]) -> Dict[str, str]:
    """
    Builds a best-effort category path using ParentID chaining.
    Output: node_id -> "A > B > C"
    """
    children: Dict[str, List[str]] = defaultdict(list)
    roots: List[str] = []

    for node_id, node in hierarchy.items():
        if node.parent_id and node.parent_id in hierarchy:
            children[node.parent_id].append(node_id)
        else:
            roots.append(node_id)

    def path_for(node_id: str) -> str:
        parts = []
        cur = node_id
        seen = set()
        while cur and cur not in seen and cur in hierarchy:
            seen.add(cur)
            n = hierarchy[cur]
            parts.append(n.name or n.node_id)
            cur = n.parent_id if n.parent_id in hierarchy else None
        parts.reverse()
        return " > ".join([p for p in parts if p])

    out: Dict[str, str] = {}
    for node_id in hierarchy.keys():
        out[node_id] = path_for(node_id) or node_id
    return out


def build_product_context_map(
    products: Dict[str, ProductRecord],
    category_paths: Dict[str, str],
) -> Tuple[Dict[str, Dict[str, str]], int, int]:
    """
    Returns:
      - product_context_map: product_id -> {category_key, category_path}
      - products_without_parent_count
      - products_unmatched_category_count
    """
    ctx: Dict[str, Dict[str, str]] = {}
    without_parent = 0
    unmatched = 0

    for pid, p in products.items():
        if not p.parent_id:
            without_parent += 1
            continue
        cat_key = p.parent_id
        cat_path = category_paths.get(cat_key)
        if not cat_path:
            unmatched += 1
            cat_path = ""
        ctx[pid] = {
            "category_key": cat_key,
            "category_path": cat_path,
        }

    return ctx, without_parent, unmatched


def compute_report(hierarchy: Dict[str, HierarchyNode], products: Dict[str, ProductRecord]) -> ParseReport:
    rep = ParseReport()
    rep.hierarchy_nodes = len(hierarchy)
    rep.attribute_links = sum(len(n.attribute_links) for n in hierarchy.values())

    levels = defaultdict(int)
    for n in hierarchy.values():
        levels[n.user_type_id or ""] += 1
    rep.hierarchy_levels = dict(levels)

    rep.products = len(products)
    if products:
        rep.avg_attributes_per_product = sum(len(p.values) for p in products.values()) / float(len(products))
    return rep


def persist_staging(bundle: StagingBundle, outputs_dir: Path) -> None:
    ensure_dir(outputs_dir)

    # Hierarchy JSONL
    h_rows = []
    for node_id, node in bundle.hierarchy_index.items():
        h_rows.append({
            "node_id": node.node_id,
            "user_type_id": node.user_type_id,
            "parent_id": node.parent_id or "",
            "name": node.name,
            "attribute_links": [
                {
                    "attribute_id": l.attribute_id,
                    "mandatory": l.mandatory,
                    "display_sequence": l.display_sequence,
                    "mandatory_for_submit_value": l.mandatory_for_submit_value,
                    "mandatory_for_submit_code": l.mandatory_for_submit_code,
                }
                for l in node.attribute_links
            ],
        })
    write_jsonl(outputs_dir / "staging_hierarchy.jsonl", h_rows)

    # Products JSONL
    p_rows = []
    for pid, p in bundle.products_index.items():
        p_rows.append({
            "product_id": p.product_id,
            "user_type_id": p.user_type_id,
            "parent_id": p.parent_id or "",
            "name": p.name,
            "values": {k: {"text": v.text, "id_code": v.id_code} for k, v in p.values.items()},
        })
    write_jsonl(outputs_dir / "staging_products.jsonl", p_rows)

    # Context map JSONL
    ctx_rows = []
    for pid, ctx in bundle.product_context_map.items():
        ctx_rows.append({"product_id": pid, **ctx})
    write_jsonl(outputs_dir / "product_context_map.jsonl", ctx_rows)

    # Report JSON
    write_json(outputs_dir / "parse_report.json", bundle.report.__dict__)
