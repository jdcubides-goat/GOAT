import argparse
from pathlib import Path
from lxml import etree
import sys

# Agrega src al path
sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from stepxml_reader import XmlStreamReader


def debug_products(xml_dir: str):
    xml_path = None

    # buscar el primer ProductSampleData
    for f in Path(xml_dir).glob("*ProductSampleData*.xml"):
        xml_path = f
        break

    if not xml_path:
        print("No se encontró archivo ProductSampleData en", xml_dir)
        return

    print("\nDEBUG FILE:", xml_path.name)

    found = 0
    checked = 0

    for elem in XmlStreamReader.stream_elements(
        str(xml_path),
        tag_name="Product",
        match_localname=True
    ):
        checked += 1

        # Filtrar solo GoldenRecord
        user_type = (elem.get("UserTypeID") or "").strip()
        if user_type != "PMDM.PRD.GoldenRecord":
            continue

        # Buscar nodo Values
        values_nodes = [
            c for c in elem
            if etree.QName(c).localname == "Values"
        ]

        if not values_nodes:
            continue

        values_node = values_nodes[0]

        value_children = [
            c for c in values_node
            if etree.QName(c).localname == "Value"
        ]

        # Si no tiene hijos Value, seguir buscando
        if len(value_children) == 0:
            if checked <= 5:
                print("EMPTY PRODUCT:", elem.get("ID"), "ParentID:", elem.get("ParentID"))
            continue

        # Si llegamos aquí, encontramos un producto con valores reales
        print("\nFOUND PRODUCT WITH VALUES")
        print("Product ID:", elem.get("ID"))
        print("ParentID:", elem.get("ParentID"))
        print("Values count:", len(value_children))

        print("\nFirst 5 Value samples:")
        for i, vv in enumerate(value_children[:5]):
            print(f"  VALUE[{i}] AttributeID:", vv.get("AttributeID"))
            print(f"  VALUE[{i}] Text:", (vv.text or "").strip())

        print("\nPRODUCT_XML_SNIPPET:")
        print(etree.tostring(elem, pretty_print=True, encoding="unicode")[:4000])

        found += 1
        break

    if found == 0:
        print("\nNO SE ENCONTRÓ NINGÚN Product GoldenRecord CON <Value> dentro de <Values>.")
        print("Esto indica que los valores podrían estar fuera del nodo Product.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml-dir", required=True)
    parser.add_argument("--debug-product", action="store_true")
    args = parser.parse_args()

    if args.debug_product:
        debug_products(args.xml_dir)


if __name__ == "__main__":
    main()
