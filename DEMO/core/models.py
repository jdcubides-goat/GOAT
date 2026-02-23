from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AttributeLink:
    attribute_id: str
    mandatory: Optional[bool] = None
    display_sequence: Optional[int] = None
    mandatory_for_submit_value: Optional[str] = None  # e.g. "Yes"/"No"
    mandatory_for_submit_code: Optional[str] = None   # e.g. "Y"/"N"


@dataclass
class HierarchyNode:
    node_id: str
    user_type_id: str
    parent_id: Optional[str]
    name: str
    attribute_links: List[AttributeLink] = field(default_factory=list)


@dataclass
class ValueRecord:
    text: str
    id_code: Optional[str] = None  # Value@ID when present


@dataclass
class ProductRecord:
    product_id: str
    user_type_id: str
    parent_id: Optional[str]
    name: str
    values: Dict[str, ValueRecord] = field(default_factory=dict)


@dataclass
class ParseReport:
    pph_files: List[str] = field(default_factory=list)
    product_files: List[str] = field(default_factory=list)

    hierarchy_nodes: int = 0
    attribute_links: int = 0
    hierarchy_levels: Dict[str, int] = field(default_factory=dict)

    products: int = 0
    products_without_parent: int = 0
    products_unmatched_category: int = 0
    avg_attributes_per_product: float = 0.0

    warnings: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)


@dataclass
class StagingBundle:
    hierarchy_index: Dict[str, HierarchyNode]
    products_index: Dict[str, ProductRecord]
    category_path_index: Dict[str, str]
    product_context_map: Dict[str, Dict[str, str]]
    report: ParseReport
