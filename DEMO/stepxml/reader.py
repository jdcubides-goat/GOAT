from __future__ import annotations

from dataclasses import dataclass
from typing import IO, Iterator, Optional, Tuple
from xml.etree import ElementTree as ET


@dataclass
class XmlStream:
    filename: str
    fileobj: IO[bytes]


def _localname(tag: str) -> str:
    # "{ns}Tag" -> "Tag"
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def iter_products(stream: XmlStream) -> Iterator[ET.Element]:
    """
    Streaming iterator over <Product ...> elements.
    We parse and yield each Product element, then clear to free memory.
    """
    context = ET.iterparse(stream.fileobj, events=("end",))
    for event, elem in context:
        if _localname(elem.tag) == "Product":
            yield elem
            elem.clear()


def find_child_text(elem: ET.Element, child_localname: str) -> str:
    for ch in list(elem):
        if _localname(ch.tag) == child_localname:
            return (ch.text or "").strip()
    return ""


def find_child(elem: ET.Element, child_localname: str) -> Optional[ET.Element]:
    for ch in list(elem):
        if _localname(ch.tag) == child_localname:
            return ch
    return None


def iter_children(elem: ET.Element, child_localname: str) -> Iterator[ET.Element]:
    for ch in list(elem):
        if _localname(ch.tag) == child_localname:
            yield ch
