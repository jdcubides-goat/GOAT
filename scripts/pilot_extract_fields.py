#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, Iterator, List, Optional, Tuple

import xml.etree.ElementTree as ET


def iter_products(xml_path: Path) -> Iterator[ET.Element]:
    # Iterparse robusto por "end" de Product
    # OJO: algunos STEPXML incluyen otros Product en otros bloques; filtramos por UserTypeID GoldenRecord.
    ctx = ET.iterparse(str(xml_path), events=("end",))
    for event, elem in ctx:
        if elem.tag != "Product":
            continue

        user_type = elem.attrib.get("UserTypeID", "")
        if user_type != "PMDM.PRD.GoldenRecord":
            # Evita "Product" de otros contexts
            elem.clear()
            continue

        yield elem
        elem.clear()


def extract_values(product_elem: ET.Element) -> Dict[str, List[Dict[str, Optional[str]]]]:
    """
    Devuelve:
      {
        "THD.PR.WebName": [{"text": "...", "id": None}],
        "THD.HR.WebSubcategory": [{"text": "...", "id": "S5950"}],
        ...
      }
    """
    out: Dict[str, List[Dict[str, Optional[str]]]] = {}
    values_node = product_elem.find("Values")
    if values_node is None:
        return out

    for v in values_node:
        # Value o MultiValue (si aparecen)
        if v.tag not in ("Value", "MultiValue"):
            continue
        aid = v.attrib.get("AttributeID")
        if not aid:
            continue

        # En MultiValue, normalmente hay sub-Value; en Value el texto está directo
        if v.tag == "MultiValue":
            for sv in v.findall("Value"):
                out.setdefault(aid, []).append(
                    {"text": (sv.text or "").strip() or None, "id": sv.attrib.get("ID")}
                )
        else:
            out.setdefault(aid, []).append(
                {"text": (v.text or "").strip() or None, "id": v.attrib.get("ID")}
            )

    return out


def pick_text(values: Dict[str, List[Dict[str, Optional[str]]]], aid: str) -> Optional[str]:
    arr = values.get(aid) or []
    for item in arr:
        t = item.get("text")
        if t:
            return t
    return None


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_xmls(xml_dir: Path) -> Tuple[List[Path], List[Path]]:
    # Separar ProductSample vs PPH por nombre
    all_xml = sorted(xml_dir.glob("*.xml"))
    product_files = [p for p in all_xml if "ProductSampleData" in p.name]
    pph_files = [p for p in all_xml if "PPHSampleData" in p.name]
    return product_files, pph_files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xml-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit-products", type=int, default=0, help="0 = sin límite")
    args = ap.parse_args()

    xml_dir = Path(args.xml_dir)
    out_path = Path(args.out)

    product_files, pph_files = find_xmls(xml_dir)
    if not product_files:
        raise SystemExit(f"No encontré ProductSampleData en {xml_dir}")

    rows: List[Dict[str, Any]] = []
    seen = 0

    for pf in product_files:
        for prod in iter_products(pf):
            prod_id = prod.attrib.get("ID")
            parent_id = prod.attrib.get("ParentID")
            name_hdr = (prod.findtext("Name") or "").strip() or None

            values = extract_values(prod)

            web_name = pick_text(values, "THD.PR.WebName") or name_hdr
            web_dept = pick_text(values, "THD.HR.WebDepartment")
            web_cat = pick_text(values, "THD.HR.WebCategory")
            web_subcat = pick_text(values, "THD.HR.WebSubcategory")
            tipo_marca = pick_text(values, "THD.PR.TipoMarca")
            model = pick_text(values, "THD.PR.Model")

            row = {
                "product_id": prod_id,
                "parent_id": parent_id,              # útil si luego conectas PPH
                "category_last_level": web_subcat,   # lo que pediste (último nivel)
                "labels": {
                    "web_department": web_dept,
                    "web_category": web_cat,
                    "web_subcategory": web_subcat,
                },
                "web_name": web_name,
                "tipo_marca": tipo_marca,
                "model": model,
                "source_file": pf.name,
            }

            rows.append(row)
            seen += 1
            if args.limit_products and seen >= args.limit_products:
                break
        if args.limit_products and seen >= args.limit_products:
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"OK: {len(rows)} productos -> {out_path}")
    print(f"ProductSampleData encontrados: {len(product_files)} | PPH encontrados: {len(pph_files)}")


if __name__ == "__main__":
    main()
