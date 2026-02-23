import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from lxml import etree


def localname(tag: str) -> str:
    return etree.QName(tag).localname


def iter_products(path: Path):
    for _, elem in etree.iterparse(str(path), events=("end",), recover=True, huge_tree=True):
        if localname(elem.tag) != "Product":
            continue

        if (elem.get("UserTypeID") or "").strip() != "PMDM.PRD.GoldenRecord":
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            continue

        yield elem

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


def should_include_file(path: Path) -> bool:
    name = path.name.lower()
    if not name.endswith(".xml"):
        return False
    # solo productos (no PPH)
    return "productsampledata" in name


def apply_gating(categories_out, min_products: int, min_strong_attrs: int, strong_attr_presence: float):
    """
    Aplica reglas de decisión sin depender de strong_attributes_all.
    Espera que cada categoría tenga:
      - products_count
      - strong_attributes  (lista de tuples: (aid, count, ratio))
    """
    for c in categories_out:
        n = c.get("products_count", 0)
        strong = c.get("strong_attributes_all") or c.get("strong_attributes") or []
        reasons = []

        if n < min_products:
            reasons.append(f"SKIP: products<{min_products} (tiene {n})")

        if len(strong) < min_strong_attrs:
            reasons.append(f"SKIP: strong_attrs<{min_strong_attrs} (tiene {len(strong)})")

        c["generate_category_description"] = (len(reasons) == 0)
        c["skip_reasons"] = reasons

    return categories_out



def build_context_for_one_file(product_xml: Path,
                               sample_names_n: int,
                               top_attrs_n: int,
                               strong_attr_presence: float):
    cat_products = defaultdict(int)            # cat_key -> count
    cat_names = defaultdict(list)              # cat_key -> list names
    cat_attr_presence = defaultdict(Counter)   # cat_key -> Counter(aid -> products_with_attr)
    cat_labels = {}                            # cat_key -> labels

    for p in iter_products(product_xml):
        parent_id = p.get("ParentID")
        vals = extract_values(p)

        dept = (vals.get("THD.HR.WebDepartment", [None])[0] if vals else None)
        cat = (vals.get("THD.HR.WebCategory", [None])[0] if vals else None)
        subcat = (vals.get("THD.HR.WebSubcategory", [None])[0] if vals else None)
        webname = (vals.get("THD.PR.WebName", [None])[0] if vals else None)

        cat_key = parent_id if parent_id else f"{dept}|{cat}|{subcat}"

        cat_products[cat_key] += 1

        if webname and len(cat_names[cat_key]) < sample_names_n:
            cat_names[cat_key].append(webname)

        for aid in vals.keys():
            cat_attr_presence[cat_key][aid] += 1

        if cat_key not in cat_labels:
            cat_labels[cat_key] = {
                "parent_id": parent_id,
                "web_department": dept,
                "web_category": cat,
                "web_subcategory": subcat,
            }

    categories = []
    for cat_key, n in cat_products.items():
        pres = cat_attr_presence[cat_key]
        top_attrs = pres.most_common(top_attrs_n)

        strong = []
        for aid, c in pres.items():
            ratio = (c / n) if n else 0.0
            if ratio >= strong_attr_presence:
                strong.append((aid, c, round(ratio, 3)))
        strong.sort(key=lambda x: (-x[2], -x[1], x[0]))

        categories.append({
            "category_key": cat_key,
            "labels": cat_labels.get(cat_key, {}),
            "products_count": n,
            "top_attributes_by_presence": top_attrs,
            "strong_attributes_all": strong,  # se recorta luego
            "sample_web_names": cat_names.get(cat_key, []),
        })

    categories.sort(key=lambda x: x["products_count"], reverse=True)
    return categories


def merge_global(global_map, file_categories):
    """
    Consolida por category_key:
    - suma products_count
    - suma presencia de atributos
    - conserva labels (primero no-null)
    - junta sample_web_names (sin crecer infinito)
    """
    for c in file_categories:
        k = c["category_key"]
        if k not in global_map:
            global_map[k] = {
                "category_key": k,
                "labels": c["labels"],
                "products_count": 0,
                "attr_presence": Counter(),
                "sample_web_names": [],
            }

        global_map[k]["products_count"] += c["products_count"]

        # sumar presencia de atributos
        for aid, cnt in c["top_attributes_by_presence"]:
            global_map[k]["attr_presence"][aid] += cnt

        # labels: llenar si faltan
        gl = global_map[k]["labels"]
        for lk, lv in c["labels"].items():
            if gl.get(lk) is None and lv is not None:
                gl[lk] = lv

        # samples (cap 20)
        for nm in c["sample_web_names"]:
            if len(global_map[k]["sample_web_names"]) >= 20:
                break
            global_map[k]["sample_web_names"].append(nm)


def finalize_global(global_map, top_attrs_n: int, strong_attr_presence: float):
    out = []
    for k, v in global_map.items():
        n = v["products_count"]
        pres = v["attr_presence"]

        top_attrs = pres.most_common(top_attrs_n)

        strong = []
        for aid, c in pres.items():
            ratio = (c / n) if n else 0.0
            if ratio >= strong_attr_presence:
                strong.append((aid, c, round(ratio, 3)))
        strong.sort(key=lambda x: (-x[2], -x[1], x[0]))

        out.append({
            "category_key": k,
            "labels": v["labels"],
            "products_count": n,
            "top_attributes_by_presence": top_attrs,
            "strong_attributes_all": strong,
            "sample_web_names": v["sample_web_names"],
        })

    out.sort(key=lambda x: x["products_count"], reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml-dir", required=True, help="Carpeta con XMLs (data/real)")
    ap.add_argument("--out", default="outputs/category_context_dir.json")
    ap.add_argument("--min-products", type=int, default=30)
    ap.add_argument("--min-strong-attrs", type=int, default=8)
    ap.add_argument("--strong-presence", type=float, default=0.60)
    ap.add_argument("--sample-names", type=int, default=12)
    ap.add_argument("--top-attrs", type=int, default=25)
    args = ap.parse_args()

    xml_dir = Path(args.xml_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in xml_dir.iterdir() if should_include_file(p)])
    if not files:
        raise SystemExit(f"No encontré ProductSampleData en: {xml_dir}")

    per_file = []
    global_map = {}

    for f in files:
        cats = build_context_for_one_file(
            product_xml=f,
            sample_names_n=args.sample_names,
            top_attrs_n=args.top_attrs,
            strong_attr_presence=args.strong_presence
        )
        merge_global(global_map, cats)
        per_file.append({
            "file": f.name,
            "categories_total": len(cats),
            "categories": cats
        })

    global_categories = finalize_global(global_map, args.top_attrs, args.strong_presence)

    # aplicar gating global (y recortar strong)
    for c in global_categories:
        c["strong_attributes"] = c["strong_attributes_all"][:30]
        del c["strong_attributes_all"]

    global_categories = apply_gating(global_categories, args.min_products, args.min_strong_attrs, args.strong_presence)

    # también recortar strong en per_file
    for pf in per_file:
        for c in pf["categories"]:
            c["strong_attributes"] = c["strong_attributes_all"][:30]
            del c["strong_attributes_all"]
        pf["categories"] = apply_gating(pf["categories"], args.min_products, args.min_strong_attrs, args.strong_presence)

    out = {
        "xml_dir": str(xml_dir),
        "files_total": len(files),
        "gating_rules": {
            "min_products": args.min_products,
            "min_strong_attrs": args.min_strong_attrs,
            "strong_attr_presence": args.strong_presence
        },
        "global": {
            "categories_total": len(global_categories),
            "categories": global_categories
        },
        "per_file": per_file
    }

    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK ->", out_path)
    print("Files:", len(files), "| Global categories:", len(global_categories))


if __name__ == "__main__":
    main()
