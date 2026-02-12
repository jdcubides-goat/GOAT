from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional, Dict, List, Tuple
from .reader import XmlEvent


def summarize_events(
    events: Iterable[XmlEvent],
    *,
    top_n: int = 30,
) -> Dict[str, object]:
    tag_counts = Counter()
    sample_paths: Dict[str, List[str]] = {}

    for ev in events:
        tag_counts[ev.tag] += 1
        if ev.tag not in sample_paths:
            sample_paths[ev.tag] = []
        if len(sample_paths[ev.tag]) < 3:
            sample_paths[ev.tag].append(ev.path)

    most_common = tag_counts.most_common(top_n)
    return {
        "top_tags": most_common,
        "sample_paths": sample_paths,
        "unique_tags": len(tag_counts),
        "total_events_counted": sum(tag_counts.values()),
    }


def guess_product_like_tags(tag_counts: Iterable[Tuple[str, int]]) -> List[Tuple[str, int]]:
    """
    Heurística simple para encontrar tags candidatas:
    Product, Item, Article, Asset, Classification, etc.
    """
    keywords = ("product", "item", "article", "asset", "class", "category", "part", "sku", "id")
    out = []
    for tag, cnt in tag_counts:
        t = tag.lower()
        if any(k in t for k in keywords):
            out.append((tag, cnt))
    return out
