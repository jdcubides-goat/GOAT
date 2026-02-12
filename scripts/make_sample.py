import sys
import os
# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import time
from src.stepxml.reader import iter_elements
from src.stepxml.sampler import write_sample

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--tag", required=True, help="Tag a leer (Product o Classification)")
    ap.add_argument("--container", required=True, help="Tag contenedor (Products o Classifications)")
    
    args = ap.parse_args()

    print(f"⏳ Leyendo: {os.path.basename(args.input)}...")
    t0 = time.perf_counter()
    
    # 1. Crear generador
    gen = iter_elements(args.input, tag_name=args.tag)

    # 2. Escribir muestra
    written = write_sample(
        gen, 
        args.output, 
        root_tag=args.container, 
        child_tag=args.tag, 
        max_n=args.n
    )
    
    t1 = time.perf_counter()
    print(f"✅ Completado en {t1 - t0:.2f}s | Se guardaron {written} registros en: {args.output}")

if __name__ == "__main__":
    main()