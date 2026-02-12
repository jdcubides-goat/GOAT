# scripts/build_ai_jobs_categories_auto.py
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Iterable, Any, Optional

STOPWORDS_ES = {
    "de","la","el","y","en","para","con","sin","por","a","un","una","unos","unas",
    "los","las","al","del","su","sus","se","que","es","son","como","más","menos",
    "o","u","lo","ya","muy","este","esta","estos","estas"
}

def normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^\w\sáéíóúñü]", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def tokenize(s: str) -> List[str]:
    s = normalize_text(s)
    toks = [t for t in s.split(" ") if t and t not in STOPWORDS_ES and len(t) > 2]
    return toks

def safe_get(d: dict, path: List[str], default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

@dataclass
class GroupStats:
    group_key: str
    group_type: str
    product_count: int
    coherence: float
    diversity: float
    top_terms: List[str]
    examples: List[dict]
    score: float

def extract_product_text_signals(p: dict) -> str:
    # Ajusta aquí según tus campos reales
    name = p.get("name") or p.get("product_name") or ""
    short = safe_get(p, ["desc_attrs", "THD.PR.WebShortDescription", "name"], "") or ""
    label = safe_get(p, ["desc_attrs", "THD.PR.Label", "name"], "") or ""
    model = safe_get(p, ["desc_attrs", "THD.PR.Model", "name"], "") or ""
    return " ".join([name, short, label, model])

def build_candidates(products: List[dict]) -> Dict[Tuple[str, str], List[int]]:
    """
    Retorna dict: (group_type, group_key) -> list of product indexes
    group_type indica "nivel" o estrategia de agrupación.
    """
    groups = defaultdict(list)

    for i, p in enumerate(products):
        # Candidate A: ParentID
        parent_id = p.get("parent_id") or p.get("ParentID")
        if parent_id:
            groups[("by_parent_id", str(parent_id))].append(i)

        # Candidate B: ClassificationReference Type+ID (si tienes "classifications")
        classifications = p.get("classifications") or []
        for c in classifications:
            cid = c.get("classification_id")
            ctype = c.get("type")
            if cid and ctype:
                groups[("by_classification", f"{ctype}::{cid}")].append(i)

        # Candidate C (opcional): UserTypeID
        ut = p.get("user_type_id") or p.get("UserTypeID")
        if ut:
            groups[("by_user_type", str(ut))].append(i)

    return groups

def compute_group_stats(
    group_type: str,
    group_key: str,
    idxs: List[int],
    products: List[dict],
    min_products: int = 25,
    max_examples: int = 8,
    topk_terms: int = 35
) -> Optional[GroupStats]:
    n = len(idxs)
    if n < min_products:
        return None

    term_counts = Counter()
    # para diversidad: contamos variedad de "subtipos" internos (por ejemplo SubClass si existe)
    subtype_counts = Counter()

    examples = []
    for j, idx in enumerate(idxs):
        p = products[idx]
        text = extract_product_text_signals(p)
        toks = tokenize(text)
        term_counts.update(toks)

        # Intento de "subtipo" (sin depender de web/erp): usa classification id o subclass si existe
        # Si no hay, cae a primer classification
        sub = safe_get(p, ["erp_hierarchy", "THD.HR.SubClass", "name"], None)
        if not sub:
            cls = (p.get("classifications") or [])
            if cls:
                sub = f"{cls[0].get('type','')}::{cls[0].get('classification_id','')}"
        if sub:
            subtype_counts[str(sub)] += 1

        if len(examples) < max_examples:
            examples.append({
                "product_id": p.get("id") or p.get("product_id"),
                "product_name": p.get("name") or p.get("product_name"),
                "model": safe_get(p, ["desc_attrs","THD.PR.Model","name"], None),
                "short_desc": safe_get(p, ["desc_attrs","THD.PR.WebShortDescription","name"], None),
            })

    if not term_counts:
        return None

    top_terms = [t for t,_ in term_counts.most_common(topk_terms)]
    total_terms = sum(term_counts.values())

    # Coherencia: proporción de masa en top_terms (cuánto comparten vocabulario)
    top_mass = sum(term_counts[t] for t in top_terms[:15])  # top 15 como núcleo
    coherence = top_mass / max(total_terms, 1)

    # Diversidad: entropía normalizada de "subtype" (si todos son iguales, baja; si es caótico, alta)
    if subtype_counts:
        probs = [c / n for c in subtype_counts.values()]
        ent = -sum(p * math.log(p + 1e-12) for p in probs)
        ent_norm = ent / (math.log(len(probs) + 1e-12) if len(probs) > 1 else 1.0)
        diversity = float(ent_norm)
    else:
        diversity = 0.5  # neutro

    # Score: buscamos grupos con coherencia buena y diversidad moderada + tamaño suficiente sin ser gigante
    # penaliza demasiada diversidad (muy genérico) y penaliza casi cero diversidad (demasiado estrecho)
    # tamaño: preferimos 25–800 (ajusta según catálogo)
    size_term = 1.0
    if n > 1500:
        size_term = 0.6
    elif n > 800:
        size_term = 0.8

    diversity_target = 0.55  # “moderado”
    diversity_penalty = 1.0 - min(abs(diversity - diversity_target), 0.55) / 0.55  # 0..1

    score = (coherence * 0.55 + diversity_penalty * 0.35 + size_term * 0.10)

    return GroupStats(
        group_key=group_key,
        group_type=group_type,
        product_count=n,
        coherence=coherence,
        diversity=diversity,
        top_terms=top_terms,
        examples=examples,
        score=score
    )

def select_best_groups(
    products: List[dict],
    min_products: int = 25,
    max_groups: int = 200,
    score_threshold: float = 0.62
) -> List[GroupStats]:
    candidates = build_candidates(products)
    stats = []
    for (gtype, gkey), idxs in candidates.items():
        gs = compute_group_stats(gtype, gkey, idxs, products, min_products=min_products)
        if gs:
            stats.append(gs)

    # Ordena por score desc, luego por tamaño desc (para priorizar impacto)
    stats.sort(key=lambda x: (x.score, x.product_count), reverse=True)

    selected = []
    for s in stats:
        if s.score < score_threshold:
            continue
        selected.append(s)
        if len(selected) >= max_groups:
            break

    return selected

def build_ai_job_payload(gs: GroupStats, tone_rules: dict) -> dict:
    # Importante: NO dependemos de web/erp; solo entregamos señales y ejemplos
    return {
        "job_type": "category_enrichment",
        "category_key": f"{gs.group_type}::{gs.group_key}",
        "inputs": {
            "group_type": gs.group_type,
            "group_key": gs.group_key,
            "product_count": gs.product_count,
            "top_terms": gs.top_terms[:40],
            "examples": gs.examples,
            "tone_rules": tone_rules
        },
        "expected_output_schema": {
            "category_key": "string",
            "title": "string",
            "description": "string (un párrafo breve 250–450 chars aprox)"
        }
    }

def main(
    in_products_path: str,
    out_jobs_path: str,
    min_products: int = 25,
    max_groups: int = 200,
    score_threshold: float = 0.62
):
    with open(in_products_path, "r", encoding="utf-8") as f:
        products = [json.loads(line) for line in f if line.strip()]

    tone_rules = {
        "language": "es-MX",
        "tone": "comercial, claro, profesional, sin exageraciones",
        "style": "informativo, orientado a e-commerce, evita claims no verificables",
        "constraints": [
            "No inventar especificaciones técnicas, materiales, dimensiones, garantías, certificaciones",
            "No usar adjetivos subjetivos (p. ej. funcional, práctico, resistente, premium)",
            "Si algo no aplica a todos los productos, usar 'según el producto' o 'puedes encontrar opciones con'"
        ]
    }

    selected = select_best_groups(
        products=products,
        min_products=min_products,
        max_groups=max_groups,
        score_threshold=score_threshold
    )

    with open(out_jobs_path, "w", encoding="utf-8") as out:
        for gs in selected:
            payload = build_ai_job_payload(gs, tone_rules)
            out.write(json.dumps(payload, ensure_ascii=False) + "\n")

    print(f"Productos: {len(products)}")
    print(f"Grupos seleccionados: {len(selected)}")
    if selected:
        print("Top 10 grupos:")
        for s in selected[:10]:
            print(f"- {s.group_type} | {s.group_key} | n={s.product_count} | score={s.score:.3f} | coh={s.coherence:.3f} | div={s.diversity:.3f}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-products", required=True, help="Ruta a outputs/product_compact_*.jsonl")
    ap.add_argument("--out-jobs", required=True, help="Ruta a outputs/ai_jobs_categories_auto.jsonl")
    ap.add_argument("--min-products", type=int, default=25)
    ap.add_argument("--max-groups", type=int, default=200)
    ap.add_argument("--score-threshold", type=float, default=0.62)
    args = ap.parse_args()

    main(
        in_products_path=args.in_products,
        out_jobs_path=args.out_jobs,
        min_products=args.min_products,
        max_groups=args.max_groups,
        score_threshold=args.score_threshold
    )
