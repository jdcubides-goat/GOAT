# core/dataset_understanding.py
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

import xml.etree.ElementTree as ET


# ==============================================================================
# Utils
# ==============================================================================
def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

def _iter_products(xml_path: Path) -> Iterator[ET.Element]:
    ctx = ET.iterparse(str(xml_path), events=("end",))
    for _, elem in ctx:
        if elem.tag != "Product":
            continue
        ut = elem.attrib.get("UserTypeID")
        # si existe GoldenRecord, filtramos; si no existe, no filtramos
        if ut and ut != "PMDM.PRD.GoldenRecord":
            elem.clear()
            continue
        yield elem
        elem.clear()

def _extract_values(product_elem: ET.Element) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    values_node = product_elem.find("Values")
    if values_node is None:
        return out

    for v in values_node:
        if v.tag not in ("Value", "MultiValue"):
            continue
        aid = v.attrib.get("AttributeID")
        if not aid:
            continue

        if v.tag == "MultiValue":
            for sv in v.findall("Value"):
                t = _norm_ws(sv.text or "")
                if t:
                    out.setdefault(aid, []).append(t)
        else:
            t = _norm_ws(v.text or "")
            if t:
                out.setdefault(aid, []).append(t)

    return out

def _pick_first(values: Dict[str, List[str]], aid: str) -> Optional[str]:
    arr = values.get(aid) or []
    return arr[0] if arr else None

def _hash_key(s: str) -> str:
    return sha1(s.encode("utf-8")).hexdigest()[:12]


# ==============================================================================
# Canonical IDs (fallbacks). OJO: el sistema además “descubre” por patrones.
# ==============================================================================
@dataclass
class CanonicalIds:
    web_name: str = "THD.PR.WebName"
    model: str = "THD.PR.Model"
    brand_primary: str = "THD.PR.BrandID"
    brand_alt: str = "THD.PR.Brand"
    tipo_marca: str = "THD.PR.TipoMarca"

    dept: str = "THD.HR.WebDepartment"
    cat: str = "THD.HR.WebCategory"
    subcat: str = "THD.HR.WebSubcategory"

    web_long: str = "THD.PR.WebLongDescription"
    web_short: str = "THD.PR.WebShortDescription"
    es_desc: str = "THD.PR.SpanishDescription"
    en_desc: str = "THD.PR.EnglishDescription"


# ==============================================================================
# 1) Scan attribute IDs
# ==============================================================================
def scan_attribute_ids(xml_path: Path, max_products: int = 350) -> Dict[str, Any]:
    seen = Counter()
    products_scanned = 0
    for prod in _iter_products(xml_path):
        values = _extract_values(prod)
        for aid in values.keys():
            seen[aid] += 1
        products_scanned += 1
        if max_products and products_scanned >= max_products:
            break

    top = [{"attribute_id": k, "count_in_sample": int(v)} for k, v in seen.most_common(400)]
    return {
        "file": xml_path.name,
        "products_scanned": products_scanned,
        "unique_attribute_ids": len(seen),
        "top_attribute_ids": top,
        "all_attribute_ids_sample": [k for k, _ in seen.most_common()],  # útil para FieldRegistry
    }


# ==============================================================================
# 2) Field Registry (detect + suggest)
# ==============================================================================
def build_field_registry(scan_products: Dict[str, Any], ids: CanonicalIds, detected_locale: str) -> Dict[str, Any]:
    aids = set(scan_products.get("all_attribute_ids_sample") or [])

    def present(aid: str) -> bool:
        return aid in aids

    # Detect candidates by patterns (globalizable)
    def find_by_regex(pattern: str) -> List[str]:
        rx = re.compile(pattern, re.IGNORECASE)
        return [a for a in aids if rx.search(a)]

    detected = {
        "web_name": [a for a in [ids.web_name] if present(a)] + find_by_regex(r"\bWebName\b"),
        "brand": [a for a in [ids.brand_primary, ids.brand_alt] if present(a)] + find_by_regex(r"\bBrand\b"),
        "model": [a for a in [ids.model] if present(a)] + find_by_regex(r"\bModel\b"),
        "web_long": [a for a in [ids.web_long] if present(a)] + find_by_regex(r"WebLongDescription"),
        "web_short": [a for a in [ids.web_short] if present(a)] + find_by_regex(r"WebShortDescription"),
        "spanish_desc": [a for a in [ids.es_desc] if present(a)] + find_by_regex(r"SpanishDescription"),
        "english_desc": [a for a in [ids.en_desc] if present(a)] + find_by_regex(r"EnglishDescription"),
        "category_labels": [a for a in [ids.dept, ids.cat, ids.subcat] if present(a)],
        "category_description_candidates": find_by_regex(r"(Category|WebCategory|Department|Subcategory).*Description|MarketingText|SEO.*Description"),
    }

    # Resolve writeback targets with safe defaults
    # Long/Short: prefer existing standard if present, else propose standard anyway (demo writes to standard)
    wb_long = ids.web_long if present(ids.web_long) else "THD.PR.WebLongDescription"
    wb_short = ids.web_short if present(ids.web_short) else "THD.PR.WebShortDescription"

    # Naming SEO: ALWAYS safe custom field for demo
    wb_name_seo = "THD.PR.WebNameSEO"

    # Translation: suggest opposite language field if exists; else propose an “EN” field name
    if detected_locale.startswith("es"):
        wb_translation = detected["english_desc"][0] if detected["english_desc"] else "THD.PR.WebLongDescriptionEN"
    elif detected_locale.startswith("en"):
        wb_translation = detected["spanish_desc"][0] if detected["spanish_desc"] else "THD.PR.WebLongDescriptionES"
    else:
        wb_translation = detected["english_desc"][0] if detected["english_desc"] else "THD.PR.WebLongDescriptionEN"

    return {
        "fields_detected": detected,
        "writeback_targets": {
            "case_long": wb_long,
            "case_short": wb_short,
            "case_naming_seo": wb_name_seo,
            "case_translation_localization": wb_translation,
        },
        "suggested_new_fields_if_missing": {
            "case_naming_seo": wb_name_seo,
            "case_translation_localization": wb_translation,
        },
    }


# ==============================================================================
# 3) Product profiling + readiness
# ==============================================================================
_ES_MARKERS = {"EL", "LA", "LOS", "LAS", "PARA", "CON", "EN", "SIN", "DE", "DEL", "AL"}
_EN_MARKERS = {"THE", "WITH", "FOR", "IN", "WITHOUT", "AND", "OR", "OF"}

def detect_locale(text_samples: List[str]) -> Dict[str, Any]:
    if not text_samples:
        return {"locale": "und", "confidence": 0.0, "evidence": "no_text_samples"}

    es_score = 0
    en_score = 0
    total_tokens = 0

    for s in text_samples[:140]:
        tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+", s)
        tokens_up = [t.upper() for t in tokens]
        total_tokens += len(tokens_up)
        es_score += sum(1 for t in tokens_up if t in _ES_MARKERS)
        en_score += sum(1 for t in tokens_up if t in _EN_MARKERS)

    if total_tokens == 0:
        return {"locale": "und", "confidence": 0.0, "evidence": "no_tokens"}

    if es_score > en_score:
        conf = min(0.95, (es_score - en_score) / max(1, total_tokens) * 10 + 0.55)
        return {"locale": "es-MX", "confidence": round(conf, 2), "evidence": {"es_score": es_score, "en_score": en_score}}
    if en_score > es_score:
        conf = min(0.95, (en_score - es_score) / max(1, total_tokens) * 10 + 0.55)
        return {"locale": "en-US", "confidence": round(conf, 2), "evidence": {"es_score": es_score, "en_score": en_score}}

    return {"locale": "und", "confidence": 0.3, "evidence": {"es_score": es_score, "en_score": en_score}}

def profile_products(product_xml: Path, ids: CanonicalIds, max_products: int = 6000) -> Dict[str, Any]:
    n = 0
    coverage = Counter()
    dept_counter = Counter()
    cat_counter = Counter()
    subcat_counter = Counter()
    brand_counter = Counter()
    attr_presence = Counter()

    has_long = 0
    has_short = 0
    has_es = 0
    has_en = 0

    text_samples: List[str] = []

    for prod in _iter_products(product_xml):
        values = _extract_values(prod)
        pid = prod.attrib.get("ID")
        parent_id = prod.attrib.get("ParentID")

        if pid: coverage["product_id"] += 1
        if parent_id: coverage["parent_id"] += 1

        web_name = _pick_first(values, ids.web_name) or _norm_ws(prod.findtext("Name") or "")
        if web_name: coverage["web_name"] += 1

        brand = _pick_first(values, ids.brand_primary) or _pick_first(values, ids.brand_alt)
        if brand: coverage["brand"] += 1; brand_counter[brand] += 1

        model = _pick_first(values, ids.model)
        if model: coverage["model"] += 1

        dept = _pick_first(values, ids.dept)
        cat = _pick_first(values, ids.cat)
        sub = _pick_first(values, ids.subcat)

        if dept: coverage["department"] += 1; dept_counter[dept] += 1
        if cat: coverage["category"] += 1; cat_counter[cat] += 1
        if sub: coverage["subcategory"] += 1; subcat_counter[sub] += 1

        if _pick_first(values, ids.web_long): has_long += 1
        if _pick_first(values, ids.web_short): has_short += 1
        if _pick_first(values, ids.es_desc): has_es += 1
        if _pick_first(values, ids.en_desc): has_en += 1

        for aid in values.keys():
            attr_presence[aid] += 1

        if web_name and len(text_samples) < 250:
            text_samples.append(web_name)

        n += 1
        if max_products and n >= max_products:
            break

    def top_counter(c: Counter, k: int = 15) -> List[Dict[str, Any]]:
        return [{"value": v, "count": int(cnt)} for v, cnt in c.most_common(k)]

    def pct(x: int) -> float:
        return (x / n * 100.0) if n else 0.0

    readiness = {
        "case_long": round(min(100.0, pct(coverage["web_name"]) * 0.6 + pct(coverage["brand"]) * 0.2 + pct(coverage["department"]) * 0.2), 1),
        "case_short": round(min(100.0, pct(coverage["web_name"]) * 0.7 + pct(coverage["brand"]) * 0.15 + pct(coverage["category"]) * 0.15), 1),
        "case_naming_seo": round(min(100.0, pct(coverage["web_name"]) * 0.8 + pct(coverage["category"]) * 0.2), 1),
        "case_translation_localization": round(min(100.0, max(pct(has_es), pct(has_en), pct(coverage["web_name"]))), 1),
    }

    return {
        "products_sampled": n,
        "coverage_pct": {k: round((v / n) * 100.0, 2) if n else 0.0 for k, v in coverage.items()},
        "descriptions_presence_pct": {
            "web_long": round((has_long / n) * 100.0, 2) if n else 0.0,
            "web_short": round((has_short / n) * 100.0, 2) if n else 0.0,
            "spanish_desc": round((has_es / n) * 100.0, 2) if n else 0.0,
            "english_desc": round((has_en / n) * 100.0, 2) if n else 0.0,
        },
        "top_departments": top_counter(dept_counter),
        "top_categories": top_counter(cat_counter),
        "top_subcategories": top_counter(subcat_counter),
        "top_brands": top_counter(brand_counter),
        "top_attribute_ids_by_presence": [
            {"attribute_id": aid, "pct_products": round((cnt / n) * 100.0, 2)} for aid, cnt in attr_presence.most_common(30)
        ],
        "text_samples": text_samples[:120],
        "readiness_scores": readiness,
    }


# ==============================================================================
# 4) PPH optional + Category Map (parent_id stats)
# ==============================================================================
def parse_pph(pph_xml: Path, max_nodes: int = 5000) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    n = 0
    ctx = ET.iterparse(str(pph_xml), events=("end",))
    for _, elem in ctx:
        if elem.tag != "Product":
            continue

        node_id = elem.attrib.get("ID")
        ut = elem.attrib.get("UserTypeID")
        parent_id = elem.attrib.get("ParentID")
        values = _extract_values(elem)
        name = _norm_ws(elem.findtext("Name") or "") or node_id or ""

        labels = {
            "department": _pick_first(values, "THD.HR.WebDepartment"),
            "category": _pick_first(values, "THD.HR.WebCategory"),
            "subcategory": _pick_first(values, "THD.HR.WebSubcategory"),
        }

        if node_id:
            out[node_id] = {
                "node_id": node_id,
                "parent_id": parent_id,
                "user_type": ut,
                "name": name,
                "labels": labels,
                "attribute_ids_present": list(values.keys()),
            }

        elem.clear()
        n += 1
        if max_nodes and n >= max_nodes:
            break
    return out

def build_category_map(product_xml: Path, ids: CanonicalIds, pph_nodes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    counts = Counter()
    breadcrumbs = {}
    attr_presence_by_parent = defaultdict(Counter)

    for prod in _iter_products(product_xml):
        parent_id = prod.attrib.get("ParentID") or ""
        if not parent_id:
            continue

        values = _extract_values(prod)
        dept = _pick_first(values, ids.dept) or ""
        cat = _pick_first(values, ids.cat) or ""
        sub = _pick_first(values, ids.subcat) or ""

        if (not dept or not cat) and pph_nodes and parent_id in pph_nodes:
            lbl = (pph_nodes[parent_id].get("labels") or {})
            dept = dept or (lbl.get("department") or "")
            cat = cat or (lbl.get("category") or "")
            sub = sub or (lbl.get("subcategory") or "")

        bc = " > ".join([x for x in [dept, cat, sub] if x]) or parent_id
        breadcrumbs[parent_id] = bc
        counts[parent_id] += 1

        for aid in values.keys():
            attr_presence_by_parent[parent_id][aid] += 1

    all_categories = []
    for pid, cnt in counts.most_common():
        ap = attr_presence_by_parent[pid]
        top_attrs = [{"attribute_id": a, "pct": round((c / cnt) * 100.0, 2)} for a, c in ap.most_common(25)]
        all_categories.append({
            "category_key": pid,
            "breadcrumb": breadcrumbs.get(pid, pid),
            "product_count": int(cnt),
            "top_attribute_ids": top_attrs,
        })

    return {
        "unique_category_keys": len(counts),
        "all_categories": all_categories,
        "top_categories_preview": all_categories[:12],
    }


# ==============================================================================
# 5) Dictionaries + Pack Candidates (3–5 packs/categoría)
# ==============================================================================
def _load_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = _norm_ws(ln)
        if ln and not ln.startswith("#"):
            lines.append(ln)
    return lines

def _seed_terms_from_breadcrumb(breadcrumb: str) -> List[str]:
    tokens = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+", breadcrumb)
    stop = {"de","la","el","y","en","para","con","del","los","las","un","una"}
    out = []
    for t in tokens:
        tl = t.lower()
        if tl in stop or len(tl) < 3:
            continue
        out.append(tl)
    seen = set()
    res = []
    for t in out:
        if t not in seen:
            res.append(t)
            seen.add(t)
    return res[:15]

def _suggest_tone_options(breadcrumb: str, top_attr_ids: List[str]) -> List[str]:
    bc = (breadcrumb or "").lower()
    if any(k in bc for k in ["herramient", "eléctric", "electric", "constru", "plomer", "ferreter"]):
        return ["technical", "confident", "clear"]
    if any(k in bc for k in ["hogar", "decor", "muebl", "cocina", "baño", "jard"]):
        return ["friendly", "premium", "clear"]
    if any(a in top_attr_ids for a in ["THD.CT.POTENCIA", "THD.CT.CAPACIDAD"]):
        return ["technical", "clear"]
    return ["clear", "friendly", "premium"]

def _prompt_candidates_for_tone(tone: str) -> Dict[str, str]:
    # Registry v0 (IDs, luego se convierten en prompts reales)
    if tone == "technical":
        return {"long": "long_v1_technical", "short": "short_v1_technical", "name": "name_seo_v1_technical", "tr": "translate_v1"}
    if tone == "premium":
        return {"long": "long_v1_premium", "short": "short_v1_premium", "name": "name_seo_v1_premium", "tr": "translate_v1"}
    if tone == "friendly":
        return {"long": "long_v1_friendly", "short": "short_v1_friendly", "name": "name_seo_v1_friendly", "tr": "translate_v1"}
    if tone == "compliance":
        return {"long": "long_v1_compliance", "short": "short_v1_compliance", "name": "name_seo_v1_safe", "tr": "translate_v1"}
    return {"long": "long_v1_clear", "short": "short_v1_clear", "name": "name_seo_v1_clear", "tr": "translate_v1"}

def build_pack_candidates(
    category_key: str,
    breadcrumb: str,
    product_count: int,
    detected_locale: str,
    field_registry: Dict[str, Any],
    banned_words: List[str],
    banned_claims: List[str],
    top_attr_ids: List[str],
) -> Dict[str, Any]:
    tone_opts = _suggest_tone_options(breadcrumb, top_attr_ids)
    seed_terms = _seed_terms_from_breadcrumb(breadcrumb)

    packs = []
    for tone in tone_opts[:4]:
        pc = _prompt_candidates_for_tone(tone)
        pack_id = f"{category_key}::{tone}::{_hash_key(breadcrumb + tone)}"
        packs.append({
            "pack_id": pack_id,
            "tone": tone,
            "prompt_templates": {
                "case_long": pc["long"],
                "case_short": pc["short"],
                "case_naming_seo": pc["name"],
                "case_translation_localization": pc["tr"],
            },
            "guardrails": {
                "banned_words": banned_words,
                "banned_claims": banned_claims,
                "no_price_promo_shipping": True,
                "facts_must_come_from_data": True,
            },
            "seo_seed_terms": seed_terms,
            "style": {
                "long_max_chars_default": 1200,
                "short_max_chars_default": 120,
                "name_max_chars_default": 80,
            },
        })

    # Default: choose technical if strong tech attributes, else clear/premium
    default_pack_id = packs[0]["pack_id"] if packs else None
    if any(a in top_attr_ids for a in ["THD.CT.POTENCIA", "THD.CT.VOLTAJE", "THD.CT.CAPACIDAD"]):
        for p in packs:
            if p["tone"] == "technical":
                default_pack_id = p["pack_id"]
                break
    else:
        for p in packs:
            if p["tone"] in ("clear", "premium"):
                default_pack_id = p["pack_id"]
                break

    return {
        "category_key": category_key,
        "breadcrumb": breadcrumb,
        "product_count": product_count,
        "locale": detected_locale,
        "writeback_targets": field_registry["writeback_targets"],
        "pack_candidates": packs,
        "default_pack_id": default_pack_id,
    }


# ==============================================================================
# 6) Category Knowledge Base (merge incremental)
# ==============================================================================
def kb_load(kb_path: Path) -> Dict[str, Dict[str, Any]]:
    kb = {}
    for row in _read_jsonl(kb_path):
        ck = row.get("category_key")
        if ck:
            kb[ck] = row
    return kb

def kb_save(kb_path: Path, kb: Dict[str, Dict[str, Any]]) -> None:
    rows = list(kb.values())
    rows.sort(key=lambda r: (r.get("needs_review", False), -(r.get("product_count", 0))))
    _write_jsonl(kb_path, rows)

def kb_merge_categories(
    kb: Dict[str, Dict[str, Any]],
    categories: List[Dict[str, Any]],
    detected_locale: str,
) -> Dict[str, Any]:
    """
    If category_key not in kb => add with needs_review True.
    If exists => update counts/stats.
    """
    new_keys = 0
    updated = 0

    for c in categories:
        ck = c["category_key"]
        bc = c.get("breadcrumb") or ck
        pcnt = int(c.get("product_count", 0))

        if ck not in kb:
            kb[ck] = {
                "category_key": ck,
                "breadcrumb": bc,
                "product_count": pcnt,
                "locale": detected_locale,
                "needs_review": True,
                "notes": {"source": "auto_detected_from_dataset"},
                "history": [],
            }
            new_keys += 1
        else:
            kb[ck]["breadcrumb"] = bc
            kb[ck]["product_count"] = pcnt
            kb[ck]["locale"] = kb[ck].get("locale") or detected_locale
            updated += 1

    return {"new_categories_added": new_keys, "categories_updated": updated}


# ==============================================================================
# 7) Orchestrator
# ==============================================================================
from typing import Any, Dict, Optional
from pathlib import Path

def analyze_dataset(
    product_xml: Optional[Path] = None,
    pph_xml: Optional[Path] = None,
    outputs_dir: Optional[Path] = None,
    knowledge_dir: Optional[Path] = None,
    ids: CanonicalIds = CanonicalIds(),
    **kwargs: Any,
) -> Dict[str, Any]:
    """Analyze STEP exports and persist derived artifacts.

    Backwards-compatible aliases supported via kwargs:
      - product_xml_path / pph_xml_path
      - product_xml (string path) / pph_xml (string path)

    If outputs_dir / knowledge_dir are not provided, defaults are created under ./outputs.
    """

    # --------------------------------------------------------------------------
    # Parameter normalization (support older call-sites)
    # --------------------------------------------------------------------------
    if product_xml is None:
        product_xml = kwargs.get("product_xml_path") or kwargs.get("product_xml")
    if pph_xml is None:
        pph_xml = kwargs.get("pph_xml_path") or kwargs.get("pph_xml")

    # Allow string paths
    if isinstance(product_xml, (str, bytes)):
        product_xml = Path(product_xml)
    if isinstance(pph_xml, (str, bytes)):
        pph_xml = Path(pph_xml)

    if product_xml is None:
        raise TypeError("analyze_dataset: missing required argument 'product_xml'")

    if outputs_dir is None:
        outputs_dir = Path.cwd() / "outputs"
    if isinstance(outputs_dir, (str, bytes)):
        outputs_dir = Path(outputs_dir)

    if knowledge_dir is None:
        knowledge_dir = outputs_dir / "knowledge"
    if isinstance(knowledge_dir, (str, bytes)):
        knowledge_dir = Path(knowledge_dir)

    # (de aquí en adelante dejas tu lógica tal cual)

    # ---- from here, keep your original implementation EXACTLY the same ----
    # (pega aquí el cuerpo de tu función actual, sin cambiar lógica)
    # Example: everything you currently do: parsing, profiling, writing JSONL, etc.

    # IMPORTANT:
    # Return the same dict you already return today.
    # ----------------------------------------------------------------------

    # PLACEHOLDER (REMOVE): raise if you forget to paste original body
    # raise NotImplementedError("Paste the original analyze_dataset body here.")
    # dictionaries global
    banned_words = _load_lines(knowledge_dir / "dictionaries" / "global_banned_words.txt")
    banned_claims = _load_lines(knowledge_dir / "dictionaries" / "global_banned_claims.txt")

    # scans
    scan_products = scan_attribute_ids(product_xml, max_products=350)
    scan_pph = None
    pph_nodes = None
    if pph_xml and pph_xml.exists():
        scan_pph = scan_attribute_ids(pph_xml, max_products=250)
        pph_nodes = parse_pph(pph_xml)

    # product profile + locale
    prof = profile_products(product_xml, ids=ids, max_products=6000)
    locale_info = detect_locale(prof.get("text_samples") or [])
    detected_locale = locale_info.get("locale", "und")

    # field registry
    field_registry = build_field_registry(scan_products, ids=ids, detected_locale=detected_locale)

    # category map
    cat_map = build_category_map(product_xml, ids=ids, pph_nodes=pph_nodes)
    categories = cat_map.get("all_categories", [])

    # category description availability (heurística simple por patrones en PPH scan)
    category_desc_found = False
    if scan_pph:
        for row in scan_pph.get("top_attribute_ids", []):
            aid = row.get("attribute_id", "")
            if re.search(r"(Category|WebCategory|Department|Subcategory).*Description|MarketingText|SEO.*Description", aid, re.IGNORECASE):
                category_desc_found = True
                break

    # KB merge
    kb_path = knowledge_dir / "category_kb.jsonl"
    kb = kb_load(kb_path)
    kb_merge_stats = kb_merge_categories(kb, categories, detected_locale=detected_locale)
    kb_save(kb_path, kb)

    # pack candidates per category (store in outputs)
    packs_out = []
    for c in categories:
        ck = c["category_key"]
        bc = c.get("breadcrumb") or ck
        pcnt = int(c.get("product_count", 0))
        top_attr_ids = [x["attribute_id"] for x in (c.get("top_attribute_ids") or [])]

        # If breadcrumb missing or weak, mark as needs_review (globalizable)
        if bc.strip() == ck.strip():
            kb[ck]["needs_review"] = True

        packs_out.append(
            build_pack_candidates(
                category_key=ck,
                breadcrumb=bc,
                product_count=pcnt,
                detected_locale=detected_locale,
                field_registry=field_registry,
                banned_words=banned_words,
                banned_claims=banned_claims,
                top_attr_ids=top_attr_ids,
            )
        )

    # persist outputs
    _write_json(outputs_dir / "dataset_report.json", {
        "inputs": {"product_xml": product_xml.name, "pph_xml": pph_xml.name if pph_xml else None, "pph_provided": bool(pph_xml)},
        "attribute_scan": {"product_sample": scan_products, "pph_sample": scan_pph},
        "locale_detection": locale_info,
        "field_registry": field_registry,
        "product_profile": prof,
        "category_map_summary": {
            "unique_category_keys": cat_map.get("unique_category_keys"),
            "top_categories_preview": cat_map.get("top_categories_preview", []),
        },
        "category_description_available": category_desc_found,
        "knowledge_base_merge": kb_merge_stats,
        "next_actions": _next_actions(category_desc_found),
    })

    _write_jsonl(outputs_dir / "category_map.jsonl", categories)
    _write_jsonl(outputs_dir / "category_packs_v1_candidates.jsonl", packs_out)

    # save KB again if we changed needs_review flags
    kb_save(kb_path, kb)

    return {
        "report_path": str(outputs_dir / "dataset_report.json"),
        "category_packs_path": str(outputs_dir / "category_packs_v1_candidates.jsonl"),
        "kb_path": str(kb_path),
    }

def _next_actions(category_desc_found: bool) -> List[str]:
    if category_desc_found:
        return [
            "Category descriptions detected. Next: link node descriptions into category context and proceed to prompt registry.",
            "Enable generation module for cases 1–4 using pack routing + guardrails.",
        ]
    return [
        "No category descriptions detected. Offer: (A) request from client; (B) generate category descriptions from product evidence with strict guardrails.",
        "Enable editable category packs in UI (choose default tone/template per category).",
    ]
