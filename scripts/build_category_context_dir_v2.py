#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from lxml import etree


# -----------------------------
# Reader robusto (iterparse)
# -----------------------------
def iter_products(xml_path: Path) -> Iterator[etree._Element]:
    """
    Itera <Product> de GoldenRecord en streaming.
    Importante: NO usar 'parser=' en iterparse (lxml no lo acepta).
    """
    context = etree.iterparse(
        str(xml_path),
        events=("end",),
        tag="Product",
        recover=True,
        huge_tree=True,
    )
    for _, elem in context:
        # Filtramos GoldenRecord
        if elem.get("UserTypeID") == "PMDM.PRD.GoldenRecord":
            yield elem

        # Limpieza memoria
        elem.clear()
        while elem.getprevious() is not None:
            del elem.getparent()[0]


def extract_values_dict(product_elem: etree._Element) -> Dict[str, List[str]]:
    """
    Devuelve dict(AttributeID -> [values...]) desde <Values><Value ...>text</Value></Values>
    """
    out: Dict[str, List[str]] = defaultdict(list)
    values_node = product_elem.find("Values")
    if values_node is None:
        return out

    for child in values_node:
        # Normalmente es <Value AttributeID="...">text</Value>
        if child.tag == "Value":
            aid = child.get("AttributeID")
            if not aid:
                continue
            txt = (child.text or "").strip()
            if txt:
                out[aid].append(txt)

        # Si aparecen MultiValue u otros, se puede extender después
    return out


def first(values: Dict[str, List[str]], key: str) -> Optional[str]:
    v = values.get(key)
    if not v:
        return None
    return v[0]


# -----------------------------
# Heurísticas de keywords/señales
# -----------------------------
STOPWORDS = {
    "DE","LA","EL","Y","EN","PARA","CON","POR","DEL","LAS","LOS","UN","UNA","UNO",
    "A","AL","O","U","E","THE","AND","OR","IN","ON"
}

def keywords_from_names(names: List[str], top_k: int = 15) -> List[str]:
    """
    Saca keywords simples por frecuencia desde WebName.
    """
    c = Counter()
    for n in names:
        tokens = re.findall(r"[A-ZÁÉÍÓÚÜÑ0-9]+", n.upper())
        for t in tokens:
            if len(t) < 3:
                continue
            if t in STOPWORDS:
                continue
            # evitar tokens muy numéricos tipo "128GB" sí sirve, lo dejamos
            c[t] += 1
    return [w for w, _ in c.most_common(top_k)]


def compute_signals(strong_attr_ids: List[str], keywords: List[str]) -> Dict[str, bool]:
    """
    Señales básicas para orientar “qué describir” en una categoría.
    """
    has_dimensions = any(a in strong_attr_ids for a in ("THD.CT.ALTO","THD.CT.ANCHO","THD.CT.LARGO","THD.PR.EachAlto","THD.PR.EachAncho"))
    has_material   = any(a in strong_attr_ids for a in ("THD.CT.MATERIAL",))
    has_color      = any(a in strong_attr_ids for a in ("THD.CT.COLOR",))
    has_model      = any(a in strong_attr_ids for a in ("THD.CT.MODELO","THD.PR.Model"))

    tech_like = any(k in keywords for k in ("SMARTPHONE","RAM","PROCESADOR","ANDROID","GB","5G","BLUETOOTH","HDMI","USB","WIFI"))
    home_like = any(k in keywords for k in ("COCINA","MEZCLADORA","LLAVE","CAMPANA","EMPOTRE","EMPOTRABLE","ACERO","INOX","CROMO"))

    return {
        "has_dimensions": bool(has_dimensions),
        "has_material": bool(has_material),
        "has_color": bool(has_color),
        "has_model": bool(has_model),
        "is_tech_like": bool(tech_like),
        "is_home_like": bool(home_like),
    }


def recommended_focus(signals: Dict[str, bool]) -> List[str]:
    focus = []
    if signals["has_dimensions"]:
        focus.append("dimensiones_y_peso")
    if signals["has_material"]:
        focus.append("materiales_y_acabados")
    if signals["has_color"]:
        focus.append("variantes_de_color")
    if signals["has_model"]:
        focus.append("modelos_y_especificaciones")
    if signals["is_tech_like"]:
        focus.extend(["capacidad_y_rendimiento","conectividad","compatibilidad"])
    if signals["is_home_like"]:
        focus.extend(["uso_en_el_hogar","instalacion","durabilidad"])
    # dedupe manteniendo orden
    seen = set()
    out = []
    for x in focus:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# -----------------------------
# Construcción de contexto por categoría
# -----------------------------
@dataclass
class CategoryAgg:
    category_key: str
    products_count: int = 0
    web_department: Counter = None
    web_category: Counter = None
    web_subcategory: Counter = None
    attr_presence: Counter = None
    web_names: List[str] = None

    def __post_init__(self):
        self.web_department = Counter()
        self.web_category = Counter()
        self.web_subcategory = Counter()
        self.attr_presence = Counter()
        self.web_names = []


def build_category_context(xml_dir: Path,
                           min_products: int = 30,
                           strong_presence: float = 0.9,
                           min_strong_attrs: int = 8) -> List[dict]:
    categories: Dict[str, CategoryAgg] = {}

    xml_files = sorted([p for p in xml_dir.glob("*.xml") if p.is_file()])
    if not xml_files:
        raise FileNotFoundError(f"No encontré .xml en: {xml_dir}")

    for xf in xml_files:
        # iteramos productos GoldenRecord
        any_products = False
        for prod in iter_products(xf):
            any_products = True
            parent_id = prod.get("ParentID") or "NO_PARENT"
            if parent_id not in categories:
                categories[parent_id] = CategoryAgg(category_key=parent_id)

            agg = categories[parent_id]
            agg.products_count += 1

            vals = extract_values_dict(prod)

            # labels web (si existen)
            wd = first(vals, "THD.HR.WebDepartment")
            wc = first(vals, "THD.HR.WebCategory")
            ws = first(vals, "THD.HR.WebSubcategory")
            if wd: agg.web_department[wd] += 1
            if wc: agg.web_category[wc] += 1
            if ws: agg.web_subcategory[ws] += 1

            # presencia de atributos (keys)
            for aid in vals.keys():
                agg.attr_presence[aid] += 1

            # nombres para keywords
            wn = first(vals, "THD.PR.WebName")
            if wn:
                agg.web_names.append(wn)

        # si el archivo no tenía GoldenRecord, lo ignoramos silenciosamente
        if not any_products:
            continue

    results: List[dict] = []
    for ck, agg in sorted(categories.items(), key=lambda x: x[1].products_count, reverse=True):
        n = agg.products_count
        # strong attrs = presence ratio >= strong_presence
        strong_attrs = []
        strong_ids_only = []
        for aid, cnt in agg.attr_presence.most_common():
            ratio = cnt / n if n else 0
            if ratio >= strong_presence:
                strong_attrs.append([aid, cnt, round(ratio, 4)])
                strong_ids_only.append(aid)

        labels = {
            "parent_id": ck,
            "web_department": (agg.web_department.most_common(1)[0][0] if agg.web_department else None),
            "web_category": (agg.web_category.most_common(1)[0][0] if agg.web_category else None),
            "web_subcategory": (agg.web_subcategory.most_common(1)[0][0] if agg.web_subcategory else None),
        }

        sample_names = agg.web_names[:12]
        kw = keywords_from_names(sample_names, top_k=15) if sample_names else []

        sig = compute_signals(strong_ids_only, kw)
        focus = recommended_focus(sig)

        skip_reasons = []
        if n < min_products:
            skip_reasons.append(f"min_products<{min_products}")
        if len(strong_attrs) < min_strong_attrs:
            skip_reasons.append(f"min_strong_attrs<{min_strong_attrs}")
        if labels["web_subcategory"] is None and labels["web_category"] is None:
            skip_reasons.append("no_web_labels")

        generate = (len(skip_reasons) == 0)

        results.append({
            "category_key": ck,
            "labels": labels,
            "products_count": n,
            "keywords": kw,
            "signals": sig,
            "recommended_focus": focus,
            "generate_category_description": generate,
            "skip_reasons": skip_reasons,
            "evidence": {
                "strong_attributes": strong_attrs,
                "top_attributes_by_presence": agg.attr_presence.most_common(25),
                "sample_web_names": sample_names,
            }
        })

    return results


# -----------------------------
# CLI
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml-dir", required=True, help="Directorio con STEPXMLs (data/real)")
    ap.add_argument("--out", required=True, help="Salida JSONL (una categoría por línea)")
    ap.add_argument("--min-products", type=int, default=30)
    ap.add_argument("--strong-presence", type=float, default=0.9)
    ap.add_argument("--min-strong-attrs", type=int, default=8)
    args = ap.parse_args()

    xml_dir = Path(args.xml_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cats = build_category_context(
        xml_dir=xml_dir,
        min_products=args.min_products,
        strong_presence=args.strong_presence,
        min_strong_attrs=args.min_strong_attrs,
    )

    with out_path.open("w", encoding="utf-8") as f:
        for c in cats:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"OK -> {out_path} | categories={len(cats)}")

if __name__ == "__main__":
    main()
