from __future__ import annotations
from typing import Iterable
from lxml import etree
from .reader import StepEntity

def write_sample(
    entities: Iterable[StepEntity],
    output_path: str,
    root_tag: str,    # Ej: Products o Classifications
    child_tag: str,   # Ej: Product o Classification
    max_n: int = 100,
) -> int:
    
    root = etree.Element("STEP-ProductInformation")
    # Creamos el contenedor correcto (Products o Classifications)
    container_el = etree.SubElement(root, root_tag)

    count = 0
    for ent in entities:
        if count >= max_n:
            break

        # Creamos el elemento correcto (Product o Classification)
        ent_el = etree.SubElement(container_el, child_tag, ID=ent.id)
        
        if ent.user_type_id:
            ent_el.set("UserTypeID", ent.user_type_id)
        if ent.parent_id:
            ent_el.set("ParentID", ent.parent_id)

        name_el = etree.SubElement(ent_el, "Name")
        name_el.text = ent.name or ""

        for ctype, cid in ent.classifications:
            etree.SubElement(ent_el, "ClassificationReference", Type=ctype, ClassificationID=cid)

        if ent.values:
            values_el = etree.SubElement(ent_el, "Values")
            for aid, sv in ent.values.items():
                v_attrib = {"AttributeID": aid}
                if sv.value_id: v_attrib["ID"] = sv.value_id
                if sv.unit_id: v_attrib["UnitID"] = sv.unit_id
                if sv.derived: v_attrib["Derived"] = "true"

                v_el = etree.SubElement(values_el, "Value", **v_attrib)
                v_el.text = sv.text

        count += 1

    tree = etree.ElementTree(root)
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding="UTF-8")
    return count