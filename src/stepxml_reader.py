from __future__ import annotations

from lxml import etree
from typing import Iterator, Iterable, Optional, Union
import os


class XmlStreamReader:
    """
    Reader streaming robusto para XML grandes.
    Usa iterparse en 'end' + limpieza agresiva para no saturar RAM.
    Compatible con versiones de lxml donde iterparse NO acepta parser=...
    """

    @staticmethod
    def stream_elements(
        file_path: str,
        tag: Union[str, Iterable[str]],
        *,
        limit: Optional[int] = None,
        match_localname: bool = False,
    ) -> Iterator[etree._Element]:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No se encontró el archivo: {file_path}")

        tags = [tag] if isinstance(tag, str) else list(tag)
        count = 0

        if match_localname:
            # Sin filtro por tag en C, filtramos por localname en Python (más robusto)
            ctx = etree.iterparse(
                file_path,
                events=("end",),
                recover=True,
                huge_tree=True,
                remove_comments=True,
                remove_pis=True,
            )

            for _, elem in ctx:
                local = etree.QName(elem).localname
                if local in tags:
                    yield elem
                    count += 1
                    if limit is not None and count >= limit:
                        break

                # limpieza SIEMPRE
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
            return

        # Fast path: filtro por tag en C (más rápido) – funciona si no hay namespace raro
        ctx = etree.iterparse(
            file_path,
            events=("end",),
            tag=tags if len(tags) > 1 else tags[0],
            recover=True,
            huge_tree=True,
            remove_comments=True,
            remove_pis=True,
        )

        for _, elem in ctx:
            yield elem
            count += 1
            if limit is not None and count >= limit:
                break

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
