import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from lxml import etree


def localname(tag: str) -> str:
    return etree.QName(tag).localname


def iter_products(path: Path):
    # streaming robusto
    for _, elem in etree.iterparse(str(path), events=("end",), recover=True, huge_tree=True):
        if localname(elem.tag) != "Product":
            continue

        # solo GoldenRecord
        if (elem.get("UserTypeID") or "").strip() != "PMDM.PRD.GoldenRecord":
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            continue

        yield elem

        # limpieza memoria
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]


def extract_values(elem) -> dict[str, list[str]]:
    out = defaultdict(list)
    values_node = None
    for c in elem:
        if localname(c.tag) == "Values":
            values_node = c
            break
    if values_node is None:
        return out

    for v in values_node:
        if localname(v.tag) != "Value":
            continue
        aid = v.get("AttributeID")
        if not aid:
            continue
        txt = (v.text or "").strip()
        if txt:
            out[aid].append(txt)
    return out


def to_float_safe(x: str):
    try:
        return float(x.replace(",", "").strip())
    except Exception:
        return None


def build_category_context(product_xml: Path, out_path: Path,
                           min_products: int = 30,
                           min_strong_attrs: int = 8,
                           strong_attr_presence: float = 0.60,
                           sample_names_n: int = 12,
                           top_attrs_n: int = 25):
    """
    Produce un JSON con:
    - categorías detectadas
    - contexto por categoría
    - decisión: generate_category_description (True/False) con razón
    """

    # buckets
    cat_products = defaultdict(list)       # cat_key -> list[product_id]
    cat_names = defaultdict(list)          # cat_key -> list[webname]
    cat_attr_presence = defaultdict(Counter)  # cat_key -> Counter(AttributeID -> count_products_with_attr)

    # para labels de categoría (dept/cat/subcat)
    cat_labels = {}  # cat_key -> dict

    for p in iter_products(product_xml):
        pid = p.get("ID")
        parent_id = p.get("ParentID")  # INT.L4-Sxxxx

        vals = extract_values(p)

        # labels web
        dept = (vals.get("THD.HR.WebDepartment", [None])[0] if vals else None)
        cat = (vals.get("THD.HR.WebCategory", [None])[0] if vals else None)
        subcat = (vals.get("THD.HR.WebSubcategory", [None])[0] if vals else None)
        webname = (vals.get("THD.PR.WebName", [None])[0] if vals else None)

        # clave de categoría: ParentID (lo más formal)
        # fallback: si ParentID viene vacío, usar dept|cat|subcat
        if parent_id:
            cat_key = parent_id
        else:
            cat_key = f"{dept}|{cat}|{subcat}"

        cat_products[cat_key].append(pid)
        if webname:
            cat_names[cat_key].append(webname)

        # contar presencia por producto (no por cantidad de valores)
        for aid in vals.keys():
            cat_attr_presence[cat_key][aid] += 1

        # guardar labels (una vez)
        if cat_key not in cat_labels:
            cat_labels[cat_key] = {
                "parent_id": parent_id,
                "web_department": dept,
                "web_category": cat,
                "web_subcategory": subcat,
            }

    # armar output
    categories_out = []

    for cat_key, plist in cat_products.items():
        n = len(plist)
        pres = cat_attr_presence[cat_key]

        # top atributos por presencia
        top_attrs = pres.most_common(top_attrs_n)

        # strong attrs: atributos presentes en >= 60% de productos (configurable)
        strong = []
        for aid, c in pres.items():
            if n > 0 and (c / n) >= strong_attr_presence:
                strong.append((aid, c, round(c / n, 3)))
        strong.sort(key=lambda x: (-x[2], -x[1], x[0]))

        # decision gate
        reasons = []
        if n < min_products:
            reasons.append(f"SKIP: products<{min_products} (tiene {n})")

        if len(strong) < min_strong_attrs:
            reasons.append(f"SKIP: strong_attrs<{min_strong_attrs} (tiene {len(strong)})")

        generate = (len(reasons) == 0)

        # sample names
        samples = cat_names.get(cat_key, [])[:sample_names_n]

        categories_out.append({
            "category_key": cat_key,
            "labels": cat_labels.get(cat_key, {}),
            "products_count": n,
            "top_attributes_by_presence": top_attrs,
            "strong_attributes": strong[:30],
            "sample_web_names": samples,
            "generate_category_description": generate,
            "skip_reasons": reasons,
        })

    # ordenar por tamaño
    categories_out.sort(key=lambda x: x["products_count"], reverse=True)

    out = {
        "source_file": product_xml.name,
        "categories_total": len(categories_out),
        "gating_rules": {
            "min_products": min_products,
            "min_strong_attrs": min_strong_attrs,
            "strong_attr_presence": strong_attr_presence
        },
        "categories": categories_out
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK ->", str(out_path))
    print("Categorias:", len(categories_out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-xml", required=True)
    ap.add_argument("--out", default="outputs/category_context.json")
    ap.add_argument("--min-products", type=int, default=30)
    ap.add_argument("--min-strong-attrs", type=int, default=8)
    ap.add_argument("--strong-presence", type=float, default=0.60)
    args = ap.parse_args()

    build_category_context(
        product_xml=Path(args.product_xml),
        out_path=Path(args.out),
        min_products=args.min_products,
        min_strong_attrs=args.min_strong_attrs,
        strong_attr_presence=args.strong_presence
    )


if __name__ == "__main__":
    main()
