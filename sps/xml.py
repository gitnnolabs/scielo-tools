import html
import os
import re
from datetime import date

from django.utils.dateparse import parse_date
from lxml import etree
from wagtail.images import get_image_model

from labeling.fragments import (
    append_fragment,
    extract_subsection,
    iter_front_blocks,
    normalize_aff_ids,
    parse_xml_fragment,
    process_special_content,
    sanitize_inline_xml_fragment,
)
from labeling.segmentation import process_labeled_text
from sps.xref import make_text_xref_fn_from_refs

_XREF_SPLIT_RE = re.compile(r'(<xref[^>]*>.*?</xref>)', re.DOTALL)
MONTHS = {
    "january": 1,
    "jan": 1,
    "enero": 1,
    "janeiro": 1,
    "february": 2,
    "feb": 2,
    "febrero": 2,
    "fevereiro": 2,
    "march": 3,
    "mar": 3,
    "marzo": 3,
    "marco": 3,
    "março": 3,
    "april": 4,
    "apr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "maio": 5,
    "june": 6,
    "jun": 6,
    "junio": 6,
    "junho": 6,
    "july": 7,
    "jul": 7,
    "julio": 7,
    "julho": 7,
    "august": 8,
    "aug": 8,
    "agosto": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "septiembre": 9,
    "setembro": 9,
    "october": 10,
    "oct": 10,
    "octubre": 10,
    "outubro": 10,
    "november": 11,
    "nov": 11,
    "noviembre": 11,
    "novembro": 11,
    "december": 12,
    "dec": 12,
    "diciembre": 12,
    "dezembro": 12,
}


def _apply_to_segments(text, fn):
    """Apply fn only to plain-text segments, leaving existing <xref> tags intact."""
    parts = _XREF_SPLIT_RE.split(text)
    return ''.join(fn(part) if i % 2 == 0 else part for i, part in enumerate(parts))


def _apply_xref_map(paragraph, xref_map):
    """Apply xref_map replacements one citation at a time.

    Each citation is applied via a fresh _apply_to_segments pass so that
    <xref> tags created by earlier iterations are respected as boundaries
    for later, shorter keys (e.g. "20" is replaced first, then "2" must
    not touch the already-created rid="B20" attribute).
    """
    for cit_text, rid in sorted(xref_map.items(), key=lambda x: -len(x[0])):
        replacement = f'<xref ref-type="bibr" rid="{rid}">{cit_text}</xref>'
        paragraph = _apply_to_segments(
            paragraph, lambda seg, ct=cit_text, r=replacement: seg.replace(ct, r)
        )
    return paragraph


def _append_formula_fragment(node_dest, value):
    if not value:
        return
    fragment = value.strip()
    if fragment.startswith("&lt;"):
        fragment = html.unescape(fragment)
    fragment = fragment.replace(
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"',
        "",
    )
    try:
        wrapper = etree.fromstring(f"<root>{fragment}</root>".encode("utf-8"))
    except etree.XMLSyntaxError:
        parser = etree.XMLParser(recover=True)
        wrapper = etree.fromstring(
            f"<root>{fragment}</root>".encode("utf-8"), parser=parser
        )
        if not len(wrapper):
            append_fragment(node_dest, value)
            return

    if wrapper.text:
        node_dest.text = (node_dest.text or "") + wrapper.text
    for child in list(wrapper):
        node_dest.append(child)


def _append_node_contents(node_dest, node_src):
    if node_src.text:
        if len(node_dest):
            node_dest[-1].tail = (node_dest[-1].tail or "") + node_src.text
        else:
            node_dest.text = (node_dest.text or "") + node_src.text
    for child in list(node_src):
        node_dest.append(child)


def _append_inline_text_fragment(node_dest, value):
    node_tmp = etree.Element("_tmp")
    append_fragment(node_tmp, value)
    _append_node_contents(node_dest, node_tmp)


def _is_abstract_paragraph(block):
    return block.block_type in {"paragraph", "paragraph_with_language"} and block.value.get(
        "label"
    ) == "<abstract>"


def _is_abstract_continuation(block):
    if block.block_type == "paragraph" and block.value.get("label") in {
        "<p>",
        "<abstract>",
    }:
        return True
    return _is_abstract_paragraph(block)


def _apply_process_labeled_text(paragraph, data_back):
    """Apply process_labeled_text to each plain-text segment independently."""
    def process_segment(seg):
        if not seg:
            return seg
        refs = process_labeled_text(seg, data_back)
        for r in refs:
            if r.get('refid') and not re.search(
                rf'<xref[^>]*>{re.escape(r["cita"])}</xref>', seg
            ):
                seg = seg.replace(
                    r['cita'],
                    f'<xref ref-type="bibr" rid="{r["refid"]}">{r["cita"]}</xref>',
                )
        return seg
    return _apply_to_segments(paragraph, process_segment)


def extract_date(texto):
    try:
        parsed = parse_date(texto or "")
        if parsed:
            return (parsed.strftime("%d"), parsed.strftime("%m"), parsed.strftime("%Y"))

        # Patrón para detectar YYYY-MM-DD, YYYY/MM/DD, DD-MM-YYYY, DD/MM/YYYY
        patron_fecha = (
            r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b|\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b"
        )

        match = re.search(patron_fecha, texto or "")
        if match:
            if match.group(1):  # Formato YYYY-MM-DD o YYYY/MM/DD
                año = match.group(1)
                mes = match.group(2).zfill(2)
                dia = match.group(3).zfill(2)
            else:  # Formato DD-MM-YYYY o DD/MM/YYYY
                dia = match.group(4).zfill(2)
                mes = match.group(5).zfill(2)
                año = match.group(6)
            return (dia, mes, año)

        normalized = _strip_accents((texto or "").lower())
        month_names = "|".join(sorted(MONTHS, key=len, reverse=True))
        patterns = [
            rf"\b({month_names})\.?\s+(\d{{1,2}}),?\s+(\d{{4}})\b",
            rf"\b(\d{{1,2}})\s+(?:de\s+)?({month_names})\.?,?\s+(?:de\s+)?(\d{{4}})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if not match:
                continue
            if match.group(1).isdigit():
                dia, mes, año = match.group(1), MONTHS[match.group(2)], match.group(3)
            else:
                mes, dia, año = MONTHS[match.group(1)], match.group(2), match.group(3)
            parsed = date(int(año), int(mes), int(dia))
            return (parsed.strftime("%d"), parsed.strftime("%m"), parsed.strftime("%Y"))
    except Exception:
        pass

    return None  # No se encontró


def _strip_accents(text):
    return (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ã", "a")
        .replace("õ", "o")
        .replace("ç", "c")
        .replace("ñ", "n")
    )


def _wrap_table_rows(table_element):
    """Wrap <tr> rows inside <table> with proper <thead>/<tbody> elements.

    The packtools PDF pipeline (extract_table_data) looks for .//thead and
    .//tbody to extract header and data rows. HTML tables stored in the
    structure have <tr> directly under <table>, so this function normalises
    the tree in-place before the element is appended to the XML tree.

    - Rows where every cell is <th> are grouped into <thead>.
    - All remaining rows are grouped into <tbody>.
    - Already-wrapped tables (existing thead/tbody) are left untouched.
    """
    for table in table_element.iter("table"):
        # Skip tables that already have thead or tbody
        if table.find("thead") is not None or table.find("tbody") is not None:
            continue

        direct_rows = [child for child in list(table) if child.tag == "tr"]
        if not direct_rows:
            continue

        # Remove the bare <tr> elements from the table first
        for tr in direct_rows:
            table.remove(tr)

        header_rows = []
        data_rows = []
        header_done = False
        for tr in direct_rows:
            cells = list(tr)
            if not header_done and cells and all(c.tag == "th" for c in cells):
                header_rows.append(tr)
            else:
                header_done = True
                data_rows.append(tr)

        insert_index = 0
        if header_rows:
            thead = etree.SubElement(table, "thead")
            for tr in header_rows:
                thead.append(tr)
            # Move thead to front
            table.remove(thead)
            table.insert(insert_index, thead)
            insert_index += 1

        if data_rows:
            tbody = etree.SubElement(table, "tbody")
            for tr in data_rows:
                tbody.append(tr)
            table.remove(tbody)
            table.insert(insert_index, tbody)


def get_xml(article_docx, data_front, data, data_back, xref_map=None):
    # Build narrative Author (year) xref replacer from data_back reference texts
    _text_xref_refs = [
        {
            'rid': item['value'].get('refid') or f'B{i + 1}',
            'ref_text': item['value'].get('paragraph') or '',
        }
        for i, item in enumerate(data_back)
        if item.get('value')
    ]
    _text_xref_fn = make_text_xref_fn_from_refs(_text_xref_refs)

    # Crear el elemento raíz
    nsmap = {
        "mml": "http://www.w3.org/1998/Math/MathML",
        "xlink": "http://www.w3.org/1999/xlink",
    }
    root = etree.Element(
        "article",
        nsmap=nsmap,
        attrib={
            "article-type": "research-article",
            "dtd-version": "1.1",
            "specific-use": "sps-1.9",
            "{http://www.w3.org/XML/1998/namespace}lang": article_docx.language or "en",
        }
        #'{http://www.w3.org/1998/Math/MathML}mml': 'http://www.w3.org/1998/Math/MathML',
        #'{http://www.w3.org/1999/xlink}xlink': 'http://www.w3.org/1999/xlink'}
    )

    # Añadir un elemento hijo
    front = etree.SubElement(root, "front")
    body = etree.SubElement(root, "body")
    back = etree.SubElement(root, "back")
    node_reflist = etree.SubElement(back, "ref-list")

    subsec = None
    continue_t = False
    arr_subarticle = []

    node = etree.SubElement(front, "journal-meta")

    if article_docx.acronym:
        node_tmp = etree.SubElement(node, "journal-id")
        node_tmp.set("journal-id-type", "publisher-id")
        node_tmp.text = article_docx.acronym

    if article_docx.title_nlm:
        node_tmp = etree.SubElement(node, "journal-id")
        node_tmp.set("journal-id-type", "nlm-ta")
        node_tmp.text = article_docx.title_nlm

    node_tmp = etree.SubElement(node, "journal-title-group")

    if article_docx.journal_title:
        node_tmp2 = etree.SubElement(node_tmp, "journal-title")
        node_tmp2.text = article_docx.journal_title

    if article_docx.short_title:
        node_tmp2 = etree.SubElement(node_tmp, "abbrev-journal-title")
        node_tmp2.set("abbrev-type", "publisher")
        node_tmp2.text = article_docx.short_title

    if article_docx.pissn:
        node_tmp = etree.SubElement(node, "issn")
        node_tmp.set("pub-type", "ppub")
        node_tmp.text = article_docx.pissn

    if article_docx.eissn:
        node_tmp = etree.SubElement(node, "issn")
        node_tmp.set("pub-type", "epub")
        node_tmp.text = article_docx.eissn

    node_tmp = etree.SubElement(node, "publisher")

    if article_docx.pubname:
        node_tmp2 = etree.SubElement(node_tmp, "publisher-name")
        node_tmp2.text = article_docx.pubname

    ##### Article Meta

    translates = []
    current_trans = []

    for block in iter_front_blocks(article_docx, data_front):
        if (
            block.block_type == "paragraph_with_language"
            and block.value.get("label") == "<translate-front>"
        ):
            # Si ya tenemos contenido acumulado, lo guardamos como parte
            if current_trans:
                translates.append(current_trans)
                current_trans = []
        current_trans.append(block)

    if current_trans:
        translates.append(current_trans)

    for i, data_t in enumerate(translates):
        if i == 0:
            node = etree.SubElement(front, "article-meta")
        else:
            subarticle = etree.SubElement(root, "sub-article")
            arr_subarticle.append(subarticle)
            subarticle.attrib["article-type"] = "translation"
            subarticle.attrib["id"] = f"S{len(arr_subarticle)}"
            subarticle.attrib["{http://www.w3.org/XML/1998/namespace}lang"] = data_t[
                0
            ].value["language"]

            node = etree.SubElement(subarticle, "front-stub")

        val = next(
            (
                b.value["paragraph"]
                for b in data_t
                if b.block_type == "paragraph"
                and b.value.get("label") == "<article-id>"
            ),
            None,
        )

        if val:
            node_tmp = etree.SubElement(node, "article-id")
            node_tmp.set("pub-id-type", "doi")
            node_tmp.text = val

        val = next(
            (
                b.value["paragraph"]
                for b in data_t
                if b.block_type == "paragraph" and b.value.get("label") == "<subject>"
            ),
            None,
        )

        if val:
            node_tmp = etree.SubElement(node, "article-categories")
            node_tmp2 = etree.SubElement(node_tmp, "subj-group")
            node_tmp2.set("subj-group-type", "heading")
            node_tmp3 = etree.SubElement(node_tmp2, "subject")
            node_tmp3.text = val

        val = next(
            (
                b.value["paragraph"]
                for b in data_t
                if b.block_type == "paragraph_with_language"
                and b.value.get("label") == "<article-title>"
            ),
            None,
        )

        if val:
            node_tmp = etree.SubElement(node, "title-group")
            node_tmp2 = etree.SubElement(node_tmp, "article-title")
            append_fragment(node_tmp2, val)

            vals = [
                b
                for b in data_t
                if b.block_type == "paragraph_with_language"
                and b.value.get("label") == "<trans-title>"
            ]

            for val in vals:
                node_tmp2 = etree.SubElement(node_tmp, "trans-title-group")
                node_tmp2.set(
                    "{http://www.w3.org/XML/1998/namespace}lang",
                    val.value.get("language"),
                )
                node_tmp3 = etree.SubElement(node_tmp2, "trans-title")
                append_fragment(node_tmp3, val.value.get("paragraph"))

        node_tmp = etree.SubElement(node, "contrib-group")

        vals = [b for b in data_t if b.block_type == "author_paragraph"]

        for val in vals:
            node_tmp2 = etree.SubElement(node_tmp, "contrib")
            node_tmp2.set("contrib-type", "author")
            if val.value.get("orcid"):
                node_tmp3 = etree.SubElement(node_tmp2, "contrib-id")
                node_tmp3.set("contrib-id-type", "orcid")
                node_tmp3.text = val.value.get("orcid")
            node_tmp3 = etree.SubElement(node_tmp2, "name")
            if val.value.get("surname"):
                node_tmp4 = etree.SubElement(node_tmp3, "surname")
                append_fragment(node_tmp4, val.value.get("surname"))

            if val.value.get("given_names"):
                node_tmp4 = etree.SubElement(node_tmp3, "given-names")
                append_fragment(node_tmp4, val.value.get("given_names"))

            for aff_id in normalize_aff_ids(val.value.get("affid")):
                node_tmp3 = etree.SubElement(node_tmp2, "xref")
                node_tmp3.set("ref-type", "aff")
                node_tmp3.set("rid", f"aff{aff_id}")
                node_tmp3.text = val.value.get("char") or ("*" * int(aff_id))

        vals = [b for b in data_t if b.block_type == "aff_paragraph"]

        for val in vals:
            aff_ids = normalize_aff_ids(val.value.get("affid"))
            if not aff_ids:
                continue
            aff_id = aff_ids[0]
            node_tmp = etree.SubElement(node, "aff")
            node_tmp.set("id", f"aff{aff_id}")

            node_tmp2 = etree.SubElement(node_tmp, "label")
            node_tmp2.text = val.value.get("char") or ("*" * int(aff_id))

            if val.value.get("orgname"):
                node_tmp2 = etree.SubElement(node_tmp, "institution")
                node_tmp2.set("content-type", "orgname")
                append_fragment(node_tmp2, val.value.get("orgname"))

            if val.value.get("orgdiv1"):
                node_tmp2 = etree.SubElement(node_tmp, "institution")
                node_tmp2.set("content-type", "orgdiv1")
                append_fragment(node_tmp2, val.value.get("orgdiv1"))

            if val.value.get("orgdiv2"):
                node_tmp2 = etree.SubElement(node_tmp, "institution")
                node_tmp2.set("content-type", "orgdiv2")
                append_fragment(node_tmp2, val.value.get("orgdiv2"))

            node_tmp2 = etree.SubElement(node_tmp, "addr-line")

            if val.value.get("city"):
                node_tmp3 = etree.SubElement(node_tmp2, "city")
                append_fragment(node_tmp3, val.value.get("city"))

            if val.value.get("state"):
                node_tmp3 = etree.SubElement(node_tmp2, "state")
                append_fragment(node_tmp3, val.value.get("state"))

            if val.value.get("country"):
                node_tmp2 = etree.SubElement(node_tmp, "country")
                node_tmp2.set("country", val.value.get("code_country"))
                append_fragment(node_tmp2, val.value.get("code_country"))

        node_tmp = etree.SubElement(node, "author-notes")

        for val in vals:
            if val.value.get("text_aff"):
                node_tmp2 = etree.SubElement(node_tmp, "fn")
                node_tmp2.set("fn-type", "other")
                aff_ids = normalize_aff_ids(val.value.get("affid"))
                if not aff_ids:
                    continue
                aff_id = aff_ids[0]
                node_tmp2.set("id", f"fn{aff_id}")

                node_tmp3 = etree.SubElement(node_tmp2, "label")
                node_tmp3.text = val.value.get("char") or ("*" * int(aff_id))

                node_tmp3 = etree.SubElement(node_tmp2, "p")
                append_fragment(node_tmp3, val.value.get("text_aff"))

        if article_docx.artdate:
            node_tmp = etree.SubElement(node, "pub-date")
            node_tmp.set("date-type", "pub")
            node_tmp.set("publication-format", "electronic")

            node_tmp2 = etree.SubElement(node_tmp, "day")
            node_tmp2.text = article_docx.artdate.strftime("%d")

            node_tmp2 = etree.SubElement(node_tmp, "month")
            node_tmp2.text = article_docx.artdate.strftime("%m")

            node_tmp2 = etree.SubElement(node_tmp, "year")
            node_tmp2.text = article_docx.artdate.strftime("%Y")
        
        issue = article_docx.issue

        if issue and (issue.year or issue.month):
            node_tmp = etree.SubElement(node, 'pub-date')
            node_tmp.set('date-type', 'collection')
            node_tmp.set('publication-format', 'electronic')

            if issue.month:
                node_tmp2 = etree.SubElement(node_tmp, 'month')
                node_tmp2.text = issue.month

            if issue.year:
                node_tmp2 = etree.SubElement(node_tmp, 'year')
                node_tmp2.text = issue.year

        if issue and issue.volume:
            node_tmp = etree.SubElement(node, 'volume')
            node_tmp.text = str(issue.volume)

        if issue and issue.number:
            node_tmp = etree.SubElement(node, 'issue')
            node_tmp.text = str(issue.number)

        if article_docx.dateiso:
            node_tmp = etree.SubElement(node, "pub-date")
            node_tmp.set("date-type", "collection")
            node_tmp.set("publication-format", "electronic")

            if (
                article_docx.dateiso.split("-")[2]
                and article_docx.dateiso.split("-")[2] != "00"
            ):
                node_tmp2 = etree.SubElement(node_tmp, "day")
                node_tmp2.text = article_docx.dateiso.split("-")[2]

            if (
                article_docx.dateiso.split("-")[1]
                and article_docx.dateiso.split("-")[1] != "00"
            ):
                node_tmp2 = etree.SubElement(node_tmp, "month")
                node_tmp2.text = article_docx.dateiso.split("-")[1]

            node_tmp2 = etree.SubElement(node_tmp, "year")
            node_tmp2.text = article_docx.dateiso.split("-")[0]

        if article_docx.elocatid:
            node_tmp = etree.SubElement(node, "elocation-id")
            node_tmp.text = article_docx.elocatid

        node_tmp = etree.SubElement(node, "history")

        val = next(
            (
                b.value["paragraph"]
                for b in data_t
                if b.block_type == "paragraph"
                and b.value.get("label") == "<date-received>"
            ),
            None,
        )

        date = extract_date(val)

        if date:
            node_tmp2 = etree.SubElement(node_tmp, "date")
            node_tmp2.set("date-type", "received")

            node_tmp3 = etree.SubElement(node_tmp2, "day")
            node_tmp3.text = date[0]

            node_tmp3 = etree.SubElement(node_tmp2, "month")
            node_tmp3.text = date[1]

            node_tmp3 = etree.SubElement(node_tmp2, "year")
            node_tmp3.text = date[2]

        val = next(
            (
                b.value["paragraph"]
                for b in data_t
                if b.block_type == "paragraph"
                and b.value.get("label") == "<date-accepted>"
            ),
            None,
        )

        date = extract_date(val)

        if date:
            node_tmp2 = etree.SubElement(node_tmp, "date")
            node_tmp2.set("date-type", "accepted")

            node_tmp3 = etree.SubElement(node_tmp2, "day")
            node_tmp3.text = date[0]

            node_tmp3 = etree.SubElement(node_tmp2, "month")
            node_tmp3.text = date[1]

            node_tmp3 = etree.SubElement(node_tmp2, "year")
            node_tmp3.text = date[2]

        node_tmp = etree.SubElement(node, "permissions")

        if article_docx.license:
            node_tmp2 = etree.SubElement(node_tmp, "license")
            node_tmp2.set("license-type", "open-access")
            node_tmp2.set("{http://www.w3.org/1999/xlink}href", article_docx.license)
            node_tmp2.set(
                "{http://www.w3.org/XML/1998/namespace}lang", article_docx.language
            )

            node_tmp3 = etree.SubElement(node_tmp2, "license-p")
            node_tmp3.text = "Este es un artículo con licencia..."

        vals = [
            b
            for b in data_t
            if b.block_type == "paragraph"
            and b.value.get("label") == "<abstract-title>"
        ]

        vals2 = [b for b in data_t if _is_abstract_paragraph(b)]

        node_tmp = etree.SubElement(node, "abstract")

        if vals and vals[0]:
            node_tmp2 = etree.SubElement(node_tmp, "title")
            append_fragment(node_tmp2, vals[0].value.get("paragraph"))

        if vals2 and vals2[0]:
            # Encuentra su índice original en article_docx.content
            last_index = data_t.index(vals2[0])

            # Recorre los bloques siguientes
            for block in data_t[last_index:]:
                if _is_abstract_continuation(block):
                    subsection = extract_subsection(block.value.get("paragraph"))

                    if subsection["title"]:
                        node_tmp2 = etree.SubElement(node_tmp, "sec")
                        node_tmp3 = etree.SubElement(node_tmp2, "title")
                        append_fragment(node_tmp3, subsection["title"])
                        node_tmp3 = etree.SubElement(node_tmp2, "p")
                        append_fragment(node_tmp3, subsection["content"])
                    else:
                        node_tmp2 = etree.SubElement(node_tmp, "p")
                        append_fragment(node_tmp2, subsection["content"])
                else:
                    break

        for i, val in enumerate(vals[1:], start=1):
            node_tmp = etree.SubElement(node, "trans-abstract")
            node_tmp.set(
                "{http://www.w3.org/XML/1998/namespace}lang",
                vals2[i].value.get("language") or article_docx.language or "en",
            )

            node_tmp2 = etree.SubElement(node_tmp, "title")
            append_fragment(node_tmp2, val.value.get("paragraph"))

            last_index = data_t.index(vals2[i])

            # Recorre los bloques siguientes
            for block in data_t[last_index:]:
                if _is_abstract_continuation(block):
                    subsection = extract_subsection(block.value.get("paragraph"))

                    if subsection["title"]:
                        node_tmp2 = etree.SubElement(node_tmp, "sec")
                        node_tmp3 = etree.SubElement(node_tmp2, "title")
                        append_fragment(node_tmp3, subsection["title"])
                        node_tmp3 = etree.SubElement(node_tmp2, "p")
                        append_fragment(node_tmp3, subsection["content"])
                    else:
                        node_tmp2 = etree.SubElement(node_tmp, "p")
                        append_fragment(node_tmp2, subsection["content"])
                else:
                    break

        vals = [
            b
            for b in data_t
            if b.block_type == "paragraph" and b.value.get("label") == "<kwd-title>"
        ]

        vals2 = [
            b
            for b in data_t
            if b.block_type == "paragraph_with_language"
            and b.value.get("label") == "<kwd-group>"
        ]

        for i, val in enumerate(vals):
            node_tmp = etree.SubElement(node, "kwd-group")
            node_tmp.set(
                "{http://www.w3.org/XML/1998/namespace}lang",
                vals2[i].value.get("language"),
            )

            node_tmp2 = etree.SubElement(node_tmp, "title")
            append_fragment(node_tmp2, val.value.get("paragraph"))
            # node_tmp2.text = val.value.get('paragraph')

            for kw in vals2[i].value.get("paragraph").split(", "):
                node_tmp2 = etree.SubElement(node_tmp, "kwd")
                append_fragment(node_tmp2, kw)

    countFN = 0
    current_sec = body
    node_sec = None
    for i, d in enumerate(data):
        node = current_sec

        if continue_t:
            continue_t = False
            continue

        if d["value"]["label"] == "<sec>":
            val_p = d["value"]["paragraph"].lower()
            attrib = {}
            if re.search(r"^(intro|sinops|synops)", val_p):
                attrib = {"sec-type": "intro"}
            elif re.search(r"^(caso|case)", val_p):
                attrib = {"sec-type": "cases"}
            elif re.search(r"^(conclus|comment|coment)", val_p):
                attrib = {"sec-type": "conclusions"}
            elif re.search(r"^(discus)", val_p):
                attrib = {"sec-type": "discussion"}
            elif re.search(r"^(materia)", val_p):
                attrib = {"sec-type": "materials"}
            elif re.search(r"^(proced|method|métod|metod)", val_p):
                attrib = {"sec-type": "methods"}
            elif re.search(r"^(result|statement|finding|declara|hallaz)", val_p):
                attrib = {"sec-type": "results"}
            elif re.search(
                r"^(subject|participant|patient|pacient|assunt|sujeto)", val_p
            ):
                attrib = {"sec-type": "subjects"}
            elif re.search(r"^(suplement|material)", val_p):
                attrib = {"sec-type": "supplementary-material"}

            current_sec = etree.SubElement(body, "sec", attrib=attrib)
            node = current_sec
            node_title = etree.SubElement(node, "title")
            append_fragment(node_title, d["value"]["paragraph"])

            subsec = False

        if d["value"]["label"] == "<sub-sec>":
            subsec = True
            node_sec = etree.SubElement(current_sec, "sec")
            node_title = etree.SubElement(node_sec, "title")
            if re.search(r"^<italic>(.*?)</italic>$", d["value"]["paragraph"]):
                sech = d["value"]["paragraph"]
                node_subtitle = etree.SubElement(node_title, "italic")
                append_fragment(node_subtitle, sech)

        if d["value"]["label"] == "<list>":
            re_search = re.search(r'list list-type="(.*?)"\]', d["value"]["paragraph"])
            list_type = re_search.group(1) if re_search else "bullet"
            attrib = {"list-type": list_type}

            if subsec:
                node_p = etree.SubElement(node_sec, "p")
                node_list = etree.SubElement(node_p, "list", attrib=attrib)
            else:
                node_p = etree.SubElement(node, "p")
                node_list = etree.SubElement(node_p, "list", attrib=attrib)

            content_list = re.search(
                r'\[list list-type="[^"]*"\](.*?)\[/list\]',
                d["value"]["paragraph"],
                re.DOTALL,
            )
            content_list = content_list.group(1) if content_list else ""
            node_list_text = content_list.replace(
                "[list-item]", "<list-item><p>"
            ).replace("[/list-item]", "</p></list-item>")

            node_list_text = sanitize_inline_xml_fragment(node_list_text)
            node_list_text = etree.fromstring(f"<root>{node_list_text}</root>")

            for child in node_list_text:
                node_list.append(child)

        if d["value"]["label"] == "<table>" or d["value"]["label"] == "<table-caption>":
            attrib = {"id": d["value"].get("tabid", "")}

            if subsec:
                node_p = etree.SubElement(node_sec, "p")
                node_table = etree.SubElement(node_p, "table-wrap", attrib=attrib)
            else:
                node_p = etree.SubElement(node, "p")
                node_table = etree.SubElement(node_p, "table-wrap", attrib=attrib)

            node_label = etree.SubElement(node_table, "label")
            append_fragment(node_label, d.get("value", {}).get("tablabel"))

            node_caption = etree.SubElement(node_table, "caption")
            node_title = etree.SubElement(node_caption, "title")
            append_fragment(node_title, d.get("value", {}).get("title"))

            node_table_text = d["value"]["content"]

            # Quitar saltos de línea y espacios extra
            node_table_text = re.sub(r"\s*\n\s*", "", node_table_text).replace(
                "<br>", ""
            )
            node_table_text = re.sub(r"&(?!\w+;|#\d+;)", "&amp;", node_table_text)

            tabla_element = parse_xml_fragment(node_table_text)

            # Ensure <table> has proper <thead>/<tbody> structure required by
            # the packtools PDF pipeline to extract headers and data rows.
            _wrap_table_rows(tabla_element)

            # Insertar en el XML principal
            node_table.append(tabla_element)

            node_foot = etree.SubElement(node_p, "table-wrap-foot")

        if d["value"]["label"] == "<table-foot>":
            countFN += 1
            node_fn = etree.SubElement(
                node_foot, "fn", attrib={"id": f"TFN{str(countFN)}"}
            )
            node_fnp = etree.SubElement(node_fn, "p")
            append_fragment(node_fnp, d["value"]["paragraph"])

        if d["value"]["label"] == "<fig>":
            attrib = {"id": d["value"].get("figid", "")}

            if subsec:
                node_p = etree.SubElement(node_sec, "p")
                node_fig = etree.SubElement(node_p, "fig", attrib=attrib)
            else:
                node_p = etree.SubElement(node, "p")
                node_fig = etree.SubElement(node_p, "fig", attrib=attrib)

            etree.SubElement(node_fig, "label").text = d["value"].get("figlabel")
            node_caption = etree.SubElement(node_fig, "caption")
            etree.SubElement(node_caption, "title").text = d["value"].get("title")

            Image = get_image_model()
            image_id = d["value"]["image"]
            image_obj = Image.objects.get(pk=image_id)
            original_filename = os.path.basename(image_obj.title or image_obj.file.name)

            # node_caption = etree.SubElement(node_fig, 'graphic', attrib={'{http://www.w3.org/1999/xlink}ref': f"{d['value']['figid']}.jpeg"})
            node_caption = etree.SubElement(
                node_fig,
                "graphic",
                attrib={"{http://www.w3.org/1999/xlink}href": original_filename},
            )

        if d["value"]["label"] == "<fig-attrib>":
            node_attrib = etree.SubElement(node_fig, "attrib")
            append_fragment(node_attrib, d["value"]["paragraph"])

        if d["value"]["label"] == "<disp-formula>":
            attrib = {"id": d["value"].get("eid", "")}

            if subsec:
                node_p = etree.SubElement(node_sec, "p")
                node_f = etree.SubElement(node_p, "disp-formula", attrib=attrib)
            else:
                node_p = etree.SubElement(node, "p")
                node_f = etree.SubElement(node_p, "disp-formula", attrib=attrib)

            for c in d["value"]["content"]:
                if c["type"] == "text":
                    node_t = etree.SubElement(node_f, "label")
                    append_fragment(node_t, c["value"])
                if c["type"] == "formula":
                    _append_formula_fragment(node_f, c["value"])

        if d["value"]["label"] == "<inline-formula>":
            attrib = {"id": d["value"].get("eid", "")}

            if subsec:
                node_p = etree.SubElement(node_sec, "p")
            else:
                node_p = etree.SubElement(node, "p")

            for c in d["value"]["content"]:
                if c["type"] == "text":
                    _append_inline_text_fragment(node_p, c["value"])
                if c["type"] == "formula":
                    node_f = etree.Element("inline-formula", attrib=attrib)
                    _append_formula_fragment(node_f, c["value"])
                    node_p.append(node_f)

        if d["value"]["label"] == "<p>":
            if subsec:
                node_p = etree.SubElement(node_sec, "p")
            else:
                node_p = etree.SubElement(node, "p")

            # Apply all xref passes to every paragraph, operating segment-by-segment
            # so that citations already marked by tasks.py pre-processing are not
            # double-wrapped, and citations in the same paragraph that were missed
            # still get processed.
            if xref_map:
                d["value"]["paragraph"] = _apply_xref_map(d["value"]["paragraph"], xref_map)
            d["value"]["paragraph"] = _text_xref_fn(d["value"]["paragraph"])
            d["value"]["paragraph"] = _apply_process_labeled_text(d["value"]["paragraph"], data_back)

            elements = process_special_content(d["value"]["paragraph"], data)
            for e in elements:
                d["value"]["paragraph"] = d["value"]["paragraph"].replace(
                    e["label"],
                    f"<xref ref-type=\"{e['reftype']}\" rid=\"{e['id']}\">{e['label']}</xref>",
                )

            append_fragment(node_p, d["value"]["paragraph"])

        if d["value"]["label"] == "<formula>":
            if subsec:
                node_p = etree.SubElement(node_sec, "p")
            else:
                node_p = etree.SubElement(node, "p")

            p_text = ""
            if "content" in d["value"]:
                for val in d["value"]["content"]:
                    if re.search(r"^<italic>(.*?)</italic>$", val["value"]):
                        node_title.text = ""
                        # ph = val['value'].replace('[style name="italic"]', '').replace('[/style]', '')
                        ph = val["value"]
                        node_subtitle = etree.fromstring(f"<root>{ph}</root>")
                        for child in node_subtitle:
                            node_title.append(child)
                    else:
                        # p_text += val['value'].replace('[style name="italic"]', '<italic>').replace('[/style]', '</italic>').replace('xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"', '')
                        p_text += val["value"].replace(
                            'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"',
                            "",
                        )

            node_text = etree.fromstring(
                f"<root><disp-formula>{p_text}</disp-formula></root>"
            )
            for child in node_text:
                node_p.append(child)

    for i, d in enumerate(data_back):
        if d["value"]["label"] == "<sec>":
            node_tit = etree.SubElement(node_reflist, "title")
            append_fragment(node_tit, d["value"]["paragraph"])
        if d["value"]["label"] == "<p>":
            values = d["value"]
            refid = values.get("refid") or f"B{i + 1}"
            node_ref = etree.SubElement(node_reflist, "ref", attrib={"id": refid})
            node_mix = etree.SubElement(node_ref, "mixed-citation")
            append_fragment(node_mix, values["paragraph"])

            if values.get("reftype") == "journal":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(
                    etree.SubElement(node_ref, "article-title"), values["title"]
                )
                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                append_fragment(etree.SubElement(node_ref, "year"), str(values["date"]))
                append_fragment(
                    etree.SubElement(node_ref, "volume"), str(values["vol"])
                )
                append_fragment(
                    etree.SubElement(node_ref, "issue"), str(values["issue"])
                )

                if values["fpage"] and values["fpage"][0] == "e":
                    append_fragment(
                        etree.SubElement(node_ref, "elocation-id"), values["fpage"]
                    )
                else:
                    append_fragment(
                        etree.SubElement(node_ref, "fpage"), str(values["fpage"])
                    )
                    append_fragment(
                        etree.SubElement(node_ref, "lpage"), str(values["lpage"])
                    )

                append_fragment(
                    etree.SubElement(node_ref, "pub-id", attrib={"pub-id-type": "doi"}),
                    values["doi"],
                )

                if values["uri"]:
                    append_fragment(
                        etree.SubElement(
                            node_ref,
                            "ext-link",
                            attrib={
                                "ext-link-type": "uri",
                                "{http://www.w3.org/1999/xlink}href": values["uri"],
                            },
                        ),
                        values["uri"],
                    )

            if values.get("reftype") == "book":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(
                    etree.SubElement(node_ref, "part-title"), values["chapter"]
                )
                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                append_fragment(
                    etree.SubElement(node_ref, "edition"), values["edition"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "publisher-loc"), values["location"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "publisher-name"), values["organization"]
                )
                append_fragment(etree.SubElement(node_ref, "year"), str(values["date"]))
                append_fragment(
                    etree.SubElement(node_ref, "fpage"), str(values["fpage"])
                )
                append_fragment(
                    etree.SubElement(node_ref, "lpage"), str(values["lpage"])
                )

            if values.get("reftype") == "data":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(
                    etree.SubElement(node_ref, "data-title"), values["title"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "version"), values["version"]
                )
                append_fragment(etree.SubElement(node_ref, "year"), str(values["date"]))
                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                append_fragment(
                    etree.SubElement(node_ref, "pub-id", attrib={"pub-id-type": "doi"}),
                    values["doi"],
                )
                if values["uri"]:
                    append_fragment(
                        etree.SubElement(
                            node_ref,
                            "ext-link",
                            attrib={
                                "ext-link-type": "uri",
                                "{http://www.w3.org/1999/xlink}href": values["uri"],
                            },
                        ),
                        values["uri"],
                    )

            if values.get("reftype") == "webpage":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                if values["uri"]:
                    append_fragment(
                        etree.SubElement(
                            node_ref,
                            "ext-link",
                            attrib={
                                "ext-link-type": "uri",
                                "{http://www.w3.org/1999/xlink}href": values["uri"],
                            },
                        ),
                        values["uri"],
                    )
                append_fragment(
                    etree.SubElement(node_ref, "access-date"), values["access_date"]
                )

            if values.get("reftype") == "confproc":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                append_fragment(
                    etree.SubElement(node_ref, "conf-name"), values["title"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "conf-num"), str(values["issue"])
                )
                append_fragment(
                    etree.SubElement(node_ref, "conf-date"), str(values["date"])
                )
                append_fragment(
                    etree.SubElement(node_ref, "conf-loc"), values["location"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "publisher-loc"), values["org_location"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "publisher-name"), values["organization"]
                )
                append_fragment(etree.SubElement(node_ref, "page"), values["pages"])

            if values.get("reftype") == "thesis":
                node_elem = etree.SubElement(
                    node_ref,
                    "element-citation",
                    attrib={"publication-type": values.get("reftype")},
                )
                node_person = etree.SubElement(
                    node_elem, "person-group", attrib={"person-group-type": "author"}
                )
                for a in values["authors"]:
                    node_name = etree.SubElement(node_person, "name")
                    node_sname = etree.SubElement(node_name, "surname")
                    node_gname = etree.SubElement(node_name, "given-names")
                    append_fragment(node_sname, a["value"]["surname"])
                    append_fragment(node_gname, a["value"]["given_names"])

                append_fragment(etree.SubElement(node_ref, "source"), values["source"])
                append_fragment(
                    etree.SubElement(node_ref, "publisher-loc"), values["org_location"]
                )
                append_fragment(
                    etree.SubElement(node_ref, "publisher-name"), values["organization"]
                )
                append_fragment(etree.SubElement(node_ref, "year"), str(values["date"]))
                append_fragment(etree.SubElement(node_ref, "page"), values["pages"])

    # Convertir a una cadena XML
    xml_como_texto = etree.tostring(root, pretty_print=True, encoding="unicode")

    return xml_como_texto, data
