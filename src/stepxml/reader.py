from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, Optional, Tuple
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class XmlEvent:
    tag: str
    attrib: Dict[str, str]
    text: str
    path: str


def _strip_ns(tag: str) -> str:
    # "{namespace}Tag" -> "Tag"
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def iter_xml_events(
    xml_path: str | Path,
    *,
    tags_of_interest: Optional[Iterable[str]] = None,
    max_events: Optional[int] = None,
) -> Iterator[XmlEvent]:
    """
    Streaming XML parser (iterparse) to handle large STEP XML files.
    Yields XmlEvent with computed element path.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML not found: {xml_path}")

    toi = set(_strip_ns(t) for t in tags_of_interest) if tags_of_interest else None

    # Track current path using a stack of tags
    stack: list[str] = []
    yielded = 0

    # We listen to start/end to maintain stack and compute path
    context = ET.iterparse(str(xml_path), events=("start", "end"))

    for event, elem in context:
        tag = _strip_ns(elem.tag)

        if event == "start":
            stack.append(tag)
            continue

        # event == "end"
        # path includes this elem tag at the end
        path = "/" + "/".join(stack)

        if (toi is None) or (tag in toi):
            text = (elem.text or "").strip()
            yield XmlEvent(tag=tag, attrib=dict(elem.attrib), text=text, path=path)
            yielded += 1
            if max_events is not None and yielded >= max_events:
                return

        # Pop stack and free memory
        if stack:
            stack.pop()
        elem.clear()
