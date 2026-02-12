from __future__ import annotations

import argparse
import json
from pathlib import Path

from stepxml.reader import iter_xml_events
from stepxml.utils import summarize_events, guess_product_like_tags


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Inspect STEP XML files (streaming).")
    p.add_argument("--xml", required=True, help="Path to STEP XML file")
    p.add_argument("--max-events", type=int, default=20000, help="Max events to parse (default: 20000)")
    p.add_argument("--tags", nargs="*", default=None, help="Optional tags of interest (exact tag names)")
    p.add_argument("--out", default=None, help="Optional output JSON report path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    xml_path = Path(args.xml)

    events = list(
        iter_xml_events(
            xml_path,
            tags_of_interest=args.tags,
            max_events=args.max_events,
        )
    )

    report = summarize_events(events, top_n=40)
    report["guessed_product_like_tags"] = guess_product_like_tags(report["top_tags"])

    print("\n=== STEP XML SPY REPORT ===")
    print(f"File: {xml_path}")
    print(f"Unique tags: {report['unique_tags']}")
    print(f"Events counted: {report['total_events_counted']}")
    print("\nTop tags:")
    for tag, cnt in report["top_tags"]:
        print(f"  {tag:40s} {cnt}")

    print("\nGuessed product-like tags (heuristic):")
    for tag, cnt in report["guessed_product_like_tags"]:
        print(f"  {tag:40s} {cnt}")

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
