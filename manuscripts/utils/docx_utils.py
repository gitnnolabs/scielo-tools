from docx_parser.parser import DocxParser
from labeling.segmentation import (
    _looks_like_frontmatter,
    create_labeled_object,
    create_special_content_object,
)
from sps.xref import build_text_xref_replacer, read_marks, validate_marks

from manuscripts.utils.helpers import _block, _raw_reference


def _xref_map(document):
    result = {}
    for reference in read_marks(document):
        rid = reference["rid"]
        for citation in reference["citations"]:
            if citation:
                result[citation] = rid
    return result


def _apply_xrefs(body, document):
    replacer = build_text_xref_replacer(document)
    xref_map = _xref_map(document)
    for item in body:
        value = item.get("value", {})
        if value.get("label") != "<p>":
            continue
        text = value.get("paragraph") or ""
        for citation, rid in sorted(xref_map.items(), key=lambda pair: -len(pair[0])):
            if citation in text and f">{citation}</xref>" not in text:
                text = text.replace(
                    citation, f'<xref ref-type="bibr" rid="{rid}">{citation}</xref>'
                )
        value["paragraph"] = replacer(text)


def extract_docx_structure(document, source_path):
    sections, content = DocxParser().extract_content(document, source_path, merge_front=False)
    front, body, back = [], [], []
    references = []
    state = {
        "label": None,
        "label_next": None,
        "label_next_reset": None,
        "reset": False,
        "repeat": None,
        "body_trans": False,
        "body": False,
        "back": False,
        "references": False,
    }
    counts = {"numref": 0, "numtab": 0, "numfig": 0, "numeq": 0}

    for item in content:
        item_type = item.get("type")
        text = item.get("text") or ""
        if item_type == "first_block":
            if text.strip():
                front.append(_block("<article-title>", text, "paragraph_with_language"))
            continue
        if item_type in {"image", "table", "list", "compound"}:
            obj, counts = create_special_content_object(item, body, counts)
            if obj:
                image = obj.get("value", {}).get("image")
                if hasattr(image, "pk"):
                    obj["value"]["image"] = image.pk
                table_text = str(
                    obj.get("value", {}).get("title") or ""
                ) + " " + str(
                    obj.get("value", {}).get("content") or ""
                )
                if _looks_like_frontmatter(table_text):
                    front.append(obj)
                else:
                    body.append(obj)
            continue
        if not text.strip():
            continue

        obj, _result, state = create_labeled_object(0, item, state, sections)
        if not obj:
            continue
        label = obj.get("value", {}).get("label")
        if state["back"] and label == "<p>":
            references.append(text)
        elif state["back"]:
            back.append(obj)
        elif state["body"]:
            body.append(obj)
        else:
            front.append(obj)

    if not body:
        body = [
            _block("<p>", item["text"])
            for item in content
            if item.get("text") and item.get("type") not in {"first_block"}
        ]
    back.extend(_raw_reference(index, text) for index, text in enumerate(references, 1))
    _apply_xrefs(body, document)
    return front, body, back, validate_marks(document)
