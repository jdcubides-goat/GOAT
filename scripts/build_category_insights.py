import argparse
import json
import re
from collections import Counter
from pathlib import Path

STOP = {
    "DE","LA","EL","Y","EN","PARA","CON","SIN","POR","DEL","LAS","LOS","UN","UNA","UNO",
    "A","AL","THE","AND","OF","TO","X","CM","MM","MTS","MT","PULGADAS","PULGADA","GB","TB",
}

DIM_ATTRS = {"THD.CT.ALTO","THD.CT.ANCHO","THD.CT.LARGO","THD.CT.PESO","THD.PR.EachPeso","THD.PR.EachAlto","THD.PR.EachAncho"}
MATERIAL_ATTRS = {"THD.CT.MATERIAL"}
COLOR_ATTRS = {"THD.CT.COLOR"}
MODEL_ATTRS = {"THD.CT.MODELO","THD.PR.Model"}

TECH_HINT_WORDS = {"SMARTPHONE","IPHONE","SAMSUNG","XIAOMI","OPPO","HONOR","ANDROID","GB","RAM","PROCESADOR","DIMENSITY"}
HOME_HINT_WORDS = {"COCINA","MEZCLADORA","LLAVE","MONOMANDO","INTEGRAL","MUEBLE","ALACENA"}

WORD_RE = re.compile(r"[A-ZÁÉÍÓÚÑ0-9]+", re.IGNORECASE)

def tokenize(text: str):
    if not text:
        return []
    toks = WORD_RE.findall(text.upper())
    out = []
    for t in toks:
        if t in STOP:
            continue
        if len(t) <= 2:
            continue
        out.append(t)
    return out

def top_keywords(sample_names, k=12):
    c = Counter()
    for s in sample_names or []:
        c.update(tokenize(s))
    return [w for w,_ in c.most_common(k)]

def presence_map(strong_attributes, top_attributes_by_presence):
    # strong_attributes: [(aid,count,ratio)]
    aids = set()
    for a in strong_attributes or []:
        aids.add(a[0])
    for a in (top_attributes_by_presence or [])[:50]:
        aids.add(a[0])
    return aids

def build_focus(signals, labels):
    focus = []
    subcat = (labels.get("web_subcategory") or "").lower()

    if signals["has_dimensions"]:
        focus.append("dimensiones_y_peso")
    if signals["has_material"]:
        focus.append("materiales_y_acabados")
    if signals["has_color"]:
        focus.append("variantes_de_color")
    if signals["has_model"]:
        focus.append("modelos_y_especificaciones")

    # refuerzos por contexto
    if signals["is_tech_like"]:
        focus.extend(["compatibilidad","capacidad_y_rendimiento","conectividad"])
    if "cocina" in subcat or signals["is_home_like"]:
        focus.extend(["uso_en_el_hogar","instalacion","durabilidad"])

    # dedup manteniendo orden
    seen = set()
    out = []
    for x in focus:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out[:8]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="outputs/category_context_dir.json")
    ap.add_argument("--out", dest="out_path", default="outputs/category_insights.jsonl")
    args = ap.parse_args()

    data = json.loads(Path(args.in_path).read_text(encoding="utf-8"))
    cats = data["global"]["categories"]

    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for c in cats:
            labels = c.get("labels", {})
            strong = c.get("strong_attributes", [])
            top_pres = c.get("top_attributes_by_presence", [])
            sample_names = c.get("sample_web_names", [])

            aids = presence_map(strong, top_pres)
            kws = top_keywords(sample_names, k=14)

            signals = {
                "has_dimensions": any(a in aids for a in DIM_ATTRS),
                "has_material": any(a in aids for a in MATERIAL_ATTRS),
                "has_color": any(a in aids for a in COLOR_ATTRS),
                "has_model": any(a in aids for a in MODEL_ATTRS),
                "is_tech_like": any(w in TECH_HINT_WORDS for w in kws),
                "is_home_like": any(w in HOME_HINT_WORDS for w in kws),
            }

            insight = {
                "category_key": c["category_key"],
                "labels": labels,
                "products_count": c.get("products_count", 0),
                "keywords": kws,
                "signals": signals,
                "recommended_focus": build_focus(signals, labels),
                "generate_category_description": c.get("generate_category_description", False),
                "skip_reasons": c.get("skip_reasons", []),
                # evidencia compacta para IA (sin ruido)
                "evidence": {
                    "strong_attributes": strong[:25],
                    "top_attributes_by_presence": top_pres[:25],
                    "sample_web_names": sample_names[:12],
                },
            }

            f.write(json.dumps(insight, ensure_ascii=False) + "\n")
            n += 1

    print("OK ->", out_path)
    print("categories_written:", n)

if __name__ == "__main__":
    main()
