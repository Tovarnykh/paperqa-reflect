"""Deterministic text extraction from openly accessible JATS article XML."""

import re
import xml.etree.ElementTree as ET


def jats_text(payload: bytes) -> bytes:
    """Keep title, abstract and entire body, including captions and table text.

    This is a text-only representation, not a PDF or figure interpretation.
    Reference lists, front-matter affiliations and external supplements are omitted.
    XML is parsed locally; external DTDs/entities are never fetched.
    """
    article = ET.fromstring(payload)
    body = article.find("body")
    if body is None:
        raise ValueError("JATS article has no main body")
    parts = []
    nodes = [article.find("front/article-meta/title-group/article-title")]
    nodes += article.findall("front/article-meta/abstract")
    nodes.append(body)
    for node in nodes:
        if node is None:
            continue
        for child in node.iter():
            if child.tag in {"title", "p", "sec", "fig", "table-wrap", "tr"}:
                child.tail = "\n\n" + (child.tail or "")
            elif child.tag in {"td", "th", "label"}:
                child.tail = " " + (child.tail or "")
        value = "".join(node.itertext())
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in value.split("\n\n")]
        parts.extend(p for p in paragraphs if p)
    text = "\n\n".join(parts) + "\n"
    if len(text) < 5000:
        raise ValueError("Article text is unexpectedly short")
    return text.encode("utf-8")


def source_to_document(payload: bytes, document: dict) -> bytes:
    if document.get("transform") == "jats-body-text-v1":
        return jats_text(payload)
    if document.get("transform"):
        raise ValueError("Unknown source transformation")
    return payload
