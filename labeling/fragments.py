import html
import re

from lxml import etree


class StreamBlockAdapter:
    __slots__ = ("block_type", "value")

    def __init__(self, block_type, value):
        self.block_type = block_type
        self.value = value


INLINE_XML_TAG_NAMES = (
    "italic", "xref", "bold", "sub", "sup",
    "underline", "sc", "strike", "br",
)

_INLINE_TAG_PATTERN = re.compile(
    rf"</?(?:{'|'.join(INLINE_XML_TAG_NAMES)})(?:\s+[^>]*)?/?>",
    re.IGNORECASE,
)

_TABLE_CELL_PATTERN = re.compile(
    r"(<t[hd](?:\s[^>]*)?>)(.*?)(</t[hd]>)",
    re.DOTALL | re.IGNORECASE,
)


def extract_subsection(text):
    text = text.strip()

    match = re.match(r"(?i)\s*(.+?)\s*:\s*(.+)", text)
    if match:
        label = match.group(1).strip()
        content = match.group(2).strip()
    else:
        label = None
        content = text

    return {"title": label, "content": content}


def find_special_element_id(data_body, label):
    for d in data_body:
        if d["type"] in ["image", "table"]:
            data = d["value"]
            clean_label = re.sub(r"^[\s\.,;:–—-]+", "", label).capitalize()

            if d["type"] == "image":
                figlabel = data.get("figlabel") or ""
                figid = data.get("figid") or ""
                if clean_label == figlabel:
                    return figid or None
                if (
                    figid
                    and len(figid) > 1
                    and figid[0] == clean_label.lower()[:1]
                    and figid[1] in clean_label.lower()
                ):
                    return figid

            if d["type"] == "table":
                tablabel = data.get("tablabel") or ""
                tabid = data.get("tabid") or ""
                if clean_label == tablabel:
                    return tabid or None
                if (
                    tabid
                    and len(tabid) > 1
                    and tabid[0] == clean_label.lower()[:1]
                    and tabid[1] in clean_label.lower()
                ):
                    return tabid

    for d in data_body:
        if d["type"] in ["compound_paragraph"]:
            data = d["value"]
            clean_label = re.sub(r"^[\s\.,;:–—-]+", "", label).lower()

            if d["type"] == "compound_paragraph":
                if data["eid"][0] in clean_label[0] and data["eid"][1] in clean_label:
                    return data.get("eid")

    return None


def is_number_parenthesis(text):
    pattern = re.compile(r"^\s*\(\s*(\d+)\s*\)\s*$")
    match = pattern.fullmatch(text)
    if match:
        return f"({match.group(1)})"
    return None


def remove_unpaired_tags(text):
    pattern = re.compile(r"<(/?)([a-zA-Z0-9]+)(?:\s[^>]*)?>")

    result = []
    stack = []

    i = 0
    for match in pattern.finditer(text):
        is_closing, tag_name = match.groups()
        is_closing = bool(is_closing)

        if match.start() > i:
            result.append(text[i:match.start()])

        tag_text = text[match.start():match.end()]

        if not is_closing:
            stack.append((tag_name, len(result)))
            result.append(tag_text)
        else:
            if stack and stack[-1][0] == tag_name:
                stack.pop()
                result.append(tag_text)

        i = match.end()

    if i < len(text):
        result.append(text[i:])

    for tag_name, pos in sorted(stack, reverse=True, key=lambda x: x[1]):
        result.pop(pos)

    return "".join(result)


def escape_angle_brackets_outside_tags(text):
    if not text or "<" not in text:
        return text

    parts = []
    pos = 0
    for match in _INLINE_TAG_PATTERN.finditer(text):
        if match.start() > pos:
            parts.append(text[pos:match.start()].replace("<", "&lt;"))
        parts.append(match.group(0))
        pos = match.end()
    if pos < len(text):
        parts.append(text[pos:].replace("<", "&lt;"))
    return "".join(parts)


def iter_front_blocks(article_docx, data_front=None):
    if data_front:
        try:
            first = data_front[0]
        except (IndexError, TypeError, KeyError):
            first = None
        if first is not None:
            if isinstance(first, dict) and "type" in first and "value" in first:
                for item in data_front:
                    yield StreamBlockAdapter(item["type"], item["value"])
                return
            else:
                for item in data_front:
                    if hasattr(item, "block_type"):
                        yield item
                    elif isinstance(item, tuple) and len(item) == 2:
                        yield StreamBlockAdapter(item[0], item[1])
                    else:
                        yield item
                return
    for block in article_docx.content:
        yield block


def plain_paragraph_text(paragraph):
    if not paragraph:
        return ""
    text = str(paragraph)
    text = re.sub(r"(?i)</?(?:italic|i|b|bold|em|strong|sub|sup|br|sc)>", "", text)
    text = re.sub(r"\[\s*/?\s*\w+(?:\s+[^\]]+)?\s*\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_aff_ids(affid):
    if affid is None or affid == "":
        return []

    items = affid if isinstance(affid, list) else [affid]
    result = []
    for item in items:
        if item is None or item == "":
            continue
        if isinstance(item, int):
            result.append(item)
            continue
        if isinstance(item, str) and item.isdigit():
            result.append(int(item))
            continue
        digits = re.sub(r"\D", "", str(item))
        if digits:
            result.append(int(digits))
    return result


def _escape_table_cell_content(inner):
    if not inner:
        return inner
    if "&amp;" in inner or "&lt;" in inner or "&gt;" in inner or "<" in inner:
        inner = re.sub(r"&(?!\w+;|#\d+;)", "&amp;", inner)
        if "<" in inner:
            inner = escape_angle_brackets_outside_tags(inner)
        return inner
    return html.escape(inner, quote=False)


def sanitize_table_html_fragment(table_html):
    if not table_html:
        return table_html
    table_html = re.sub(r"&(?!\w+;|#\d+;)", "&amp;", table_html)

    def fix_cell(match):
        return match.group(1) + _escape_table_cell_content(match.group(2)) + match.group(3)

    return _TABLE_CELL_PATTERN.sub(fix_cell, table_html)


def sanitize_inline_xml_fragment(fragment):
    if not fragment:
        return fragment
    fragment = re.sub(r"&(?!\w+;|#\d+;)", "&amp;", fragment)
    return escape_angle_brackets_outside_tags(fragment)


def parse_xml_fragment(fragment):
    return etree.XML(sanitize_table_html_fragment(fragment))


def append_fragment(node_dest, val):
    if not val:
        parent = node_dest.getparent()
        if parent:
            parent.remove(node_dest)
        return

    clean = re.sub(r"(?i)<br\s*/?>", "", val)
    clean = clean.replace("\n", "")
    clean = clean.replace("&nbsp;", " ")
    clean = re.sub(r"&(?!\w+;|#\d+;)", "&amp;", clean)
    clean = escape_angle_brackets_outside_tags(clean)
    clean = remove_unpaired_tags(clean)
    clean = re.sub(r'<(?![/a-zA-Z_])', '&lt;', clean)

    if clean == "":
        parent = node_dest.getparent()
        if parent:
            parent.remove(node_dest)
        return

    if "<" not in clean:
        node_dest.text = (node_dest.text or "") + clean
        return

    wrapper = etree.XML(f"<_wrap_>{clean}</_wrap_>")

    if wrapper.text:
        node_dest.text = (node_dest.text or "") + wrapper.text

    for child in list(wrapper):
        node_dest.append(child)


def extract_label_and_title(text):
    pattern = (
        r"\b(Imagen|Imágen|Image|Imagem|Figura|Figure|Tabla|Table|Tabela)\s+(\d+)\b"
    )
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        word = match.group(1).capitalize()
        number = match.group(2)
        label = f"{word} {number}"
        rest = text[match.end():]
        rest_clean = re.sub(r"^[\s\.,;:–—-]+", "", rest)
        return {"label": label, "title": rest_clean.strip()}

    return {"label": None, "title": text.strip()}


def process_special_content(text, data_body):
    text = re.sub(r"[\u00A0\u2007\u202F]", " ", text)

    pattern = r"""
        (?<!\w)
        (?:
            Imagen|Imágen|Image|Imagem|
            Figura|Figure|
            Tabla|Table|Tabela|
            Ecuaci[oó]n|Equa(?:ç[aã]o|cao)|Equation|
            F[oó]rmula|Formula|
            Eq\.|Ec\.|Form\.|F[óo]rm\.
        )\s*
        (?:\(\s*\d+\s*\)|\d+)
        (?!\w)
    """

    result = []
    dict_type = {"f": "fig", "t": "table", "e": "disp-formula"}

    for match in re.finditer(pattern, text, re.IGNORECASE | re.UNICODE | re.VERBOSE):
        label = match.group(0)
        id = find_special_element_id(data_body, label)
        if id is None:
            continue
        result.append({
            "label": label,
            "id": id,
            "reftype": dict_type.get(id[0].lower(), "other"),
        })

    return result
