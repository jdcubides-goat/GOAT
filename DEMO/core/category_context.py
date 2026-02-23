from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from .models import StagingBundle


_STOPWORDS_ES = {
    "de","la","el","los","las","y","o","en","para","con","sin","por","a","un","una","uno",
    "del","al","se","su","sus","es","son","como","más","menos","muy","ya","no","si","sí",
    "este","esta","estos","estas","that","the","and","or"
}

_token_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")


def _tokens(text: str) -> List[str]:
    toks = [t.lower() for t in _token_re.findall(text or "")]
    toks = [t for t in toks if len(t) >= 3 and t not in _STOPWORDS_ES]
    return toks


def build_category_context(bundle: StagingBundle, top_attr_n: int = 20, top_kw_n: int = 15) -> List[Dict]:
    """
    Creates category context rows for UI + LLM prompts.
    Based only on:
      - hierarchy_index (PPH)
      - products_index + product_context_map
      - category_path_index
    """
    # products per category
    cat_to_products: Dict[str, List[str]] = defaultdict(list)
    for pid, ctx in bundle.product_context_map.items():
        ck = (ctx.get("category_key") or "").strip()
        if ck:
            cat_to_products[ck].append(pid)

    rows: List[Dict] = []
    for cat_key, node in bundle.hierarchy_index.items():
        prod_ids = cat_to_products.get(cat_key, [])
        products_count = len(prod_ids)

        # attribute frequency across products in this category
        attr_counter = Counter()
        kw_counter = Counter()

        for pid in prod_ids:
            p = bundle.products_index.get(pid)
            if not p:
                continue
            attr_counter.update(list(p.values.keys()))
            kw_counter.update(_tokens(p.name))

        top_attrs = [a for a, _ in attr_counter.most_common(top_attr_n)]
        top_kws = [k for k, _ in kw_counter.most_common(top_kw_n)]

        # PPH attribute links available for this category
        pph_links = []
        for l in (node.attribute_links or []):
            pph_links.append({
                "attribute_id": l.attribute_id,
                "mandatory": l.mandatory,
                "display_sequence": l.display_sequence,
                "mandatory_for_submit_value": l.mandatory_for_submit_value,
                "mandatory_for_submit_code": l.mandatory_for_submit_code,
            })

        rows.append({
            "category_key": cat_key,
            "category_name": node.name,
            "user_type_id": node.user_type_id,
            "parent_id": node.parent_id or "",
            "category_path": bundle.category_path_index.get(cat_key, ""),
            "products_count": products_count,
            "top_attribute_ids": top_attrs,
            "keywords": top_kws,
            "pph_attribute_links": pph_links,
        })

    # Sort by products_count desc then name
    rows.sort(key=lambda r: (-int(r.get("products_count", 0)), str(r.get("category_path") or r.get("category_name") or "")))
    return rows
