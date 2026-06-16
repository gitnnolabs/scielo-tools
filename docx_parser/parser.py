import html
import os
import re
import zipfile

import docx
from django.core.files.base import ContentFile
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from lxml import etree, objectify
from wagtail.images import get_image_model

ImageModel = get_image_model()

WML_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DRAWINGML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
MATHML_NS = "http://www.w3.org/1998/Math/MathML"
PACKAGE_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class DocxParser:

    @staticmethod
    def open_docx(filename):
        return docx.Document(filename)

    def replace_mfenced_pipe(self, mathml_root):
        nsmap = {"mml": MATHML_NS}
        for mfenced in mathml_root.xpath(".//mml:mfenced", namespaces=nsmap):
            if mfenced.get("open") or mfenced.get("close"):
                continue
            if mfenced.get("separators", "") != "|":
                continue
            mrow = etree.Element(f"{{{MATHML_NS}}}mrow")
            mo_open = etree.SubElement(mrow, f"{{{MATHML_NS}}}mo")
            mo_open.text = "("
            mo_close = etree.SubElement(mrow, f"{{{MATHML_NS}}}mo")
            mo_close.text = ")"
            for child in list(mfenced):
                mrow.append(child)
            parent = mfenced.getparent()
            if parent is not None:
                parent.replace(mfenced, mrow)
        return mathml_root

    def _read_numbering(self, docx_path):
        mapping = {}
        with zipfile.ZipFile(docx_path, "r") as archive:
            if "word/numbering.xml" not in archive.namelist():
                return None
            tree = etree.fromstring(archive.read("word/numbering.xml"))
            nsmap = tree.nsmap
            w_ns = f"{{{WML_NS}}}"
            for abstract in tree.findall(f".//{w_ns}abstractNum" if WML_NS in str(nsmap) else ".//w:abstractNum", namespaces=nsmap):
                aid = abstract.get(f"{w_ns}abstractNumId" if WML_NS in str(nsmap) else next(iter(nsmap)) + "}abstractNumId", abstract.get("abstractNumId", ""))
                if aid not in mapping:
                    mapping[aid] = {}
                for lvl in abstract.findall(f".//{w_ns}lvl" if WML_NS in str(nsmap) else ".//w:lvl", namespaces=nsmap):
                    ilvl = lvl.get(f"{w_ns}ilvl" if WML_NS in str(nsmap) else "ilvl", lvl.get("ilvl", "0"))
                    fmt_el = lvl.find(f".//{w_ns}numFmt" if WML_NS in str(nsmap) else ".//w:numFmt", namespaces=nsmap)
                    fmt = fmt_el.get(f"{w_ns}val" if WML_NS in str(nsmap) else "val", "bullet") if fmt_el is not None else "bullet"
                    mapping[aid][ilvl] = fmt
            for num in tree.findall(f".//{w_ns}num" if WML_NS in str(nsmap) else ".//w:num", namespaces=nsmap):
                num_id = num.get(f"{w_ns}numId" if WML_NS in str(nsmap) else "numId", num.get("numId", ""))
                ref_el = num.find(f".//{w_ns}abstractNumId" if WML_NS in str(nsmap) else ".//w:abstractNumId", namespaces=nsmap)
                if ref_el is not None:
                    ref_aid = ref_el.get(f"{w_ns}val" if WML_NS in str(nsmap) else "val", ref_el.get("val", ""))
                    if ref_aid in mapping:
                        mapping[ref_aid]["numId"] = num_id
        return mapping

    def _read_hyperlinks(self, docx_path):
        links = {}
        with zipfile.ZipFile(docx_path, "r") as archive:
            rels_path = "word/_rels/document.xml.rels"
            if rels_path not in archive.namelist():
                return links
            rels_root = etree.fromstring(archive.read(rels_path))
            for rel in rels_root:
                r_id = rel.get("Id", "")
                target = rel.get("Target", "")
                if "hyperlink" in rel.get("Type", ""):
                    links[r_id] = target
        return links

    def _extract_hyperlinks(self, element, rels_map):
        links = []
        raw = etree.fromstring(etree.tostring(element))
        for hyperlink in raw.xpath(".//w:hyperlink|.//a:hlinkClick", namespaces={
            "w": WML_NS, "a": DRAWINGML_NS,
        }):
            r_id = hyperlink.get(f"{{{REL_NS}}}id", "")
            if r_id and r_id in rels_map:
                links.append(rels_map[r_id])
        return " ".join(links) if links else None


    def extract_content(self, doc, doc_path, merge_front=True):
        list_types = self._read_numbering(doc_path)
        self._read_hyperlinks(doc_path)

        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        xslt_path = os.path.join(BASE_DIR, "omml2mml.xsl")
        transform = etree.XSLT(etree.parse(xslt_path))

        def _match_paragraph(text):
            if re.search(r"(?im)^\s*(?:<italic>)?\s*(palabra(?:s)?\s*clave|palavras?\s*-?\s*chave|keywords?)\s*(?:</italic>)?\s*(?::|<italic>\s*:\s*</italic>)\s*(.+)$", text):
                return "<kwd-group>"
            if re.search(r"(?i)^resumen|^resumo|^abstract", text):
                return "<abstract>"
            if re.search(r"(?i)aceptado|accepted|aceited|aprovado", text):
                return "<date-accepted>"
            if re.search(r"(?i)recibido|received|recebido", text):
                return "<date-received>"
            return False

        def _matches_section(a, b):
            try:
                return a.get("size") == b.get("size") and a.get("bold") == b.get("bold") and a.get("isupper") == b.get("isupper")
            except Exception:
                return False

        def _identify_section(sections, size, bold, text):
            if size == 0:
                return sections
            isupper = text.isupper()
            s = {"size": size, "bold": bold, "isupper": isupper, "count": 0}
            if not sections:
                sections.append(s)
                return sections
            for existing in sections:
                if _matches_section(s, existing):
                    existing["count"] += 1
                    return sections
            sections.append(s)
            return sections

        def _clean_labels(text):
            text = re.sub(r"\[\s*/?\s*[\w-]+(?:\s+[^\]]+)?\s*\]", "", text)
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"\s+([;:,.])", r"\1", text)
            return text.strip()


        def _section_priority(sections):
            return (-sections["size"], not sections["bold"], not sections["isupper"])


        def _extract_table(element):
            def _cell_text(cell):
                p_texts = []
                for p in cell.xpath(".//w:p"):
                    parts = []
                    for child in p.xpath(".//w:t | .//w:br"):
                        if child.tag.endswith("t"):
                            parts.append(html.escape(child.text or "", quote=False))
                        elif child.tag.endswith("br"):
                            parts.append("<br/>")
                    pt = "".join(parts)
                    if pt.strip() or "<br/>" in pt:
                        p_texts.append(pt)
                if not p_texts:
                    return html.escape("".join(t.text or "" for t in cell.xpath(".//w:t")), quote=False)
                return "<br/>".join(p_texts)

            table_html = '<table border="1">\n'
            rowspan_map = {}
            rows = element.xpath(".//w:tr")
            for i, row in enumerate(rows):
                table_html += "  <tr>\n"
                j = 0
                for cell in row.xpath(".//w:tc"):
                    while (i, j) in rowspan_map and rowspan_map[(i, j)] > 0:
                        rowspan_map[(i, j)] -= 1
                        j += 1

                    rs = 1
                    cs = 1
                    vmerge_skip = False

                    vm = cell.xpath(".//w:vMerge")
                    if vm:
                        val = vm[0].get(qn("w:val"))
                        if val == "restart":
                            rs = 1
                            k = i + 1
                            while k < len(rows):
                                try:
                                    nc = rows[k].xpath(".//w:tc")[j]
                                    nvm = nc.xpath(".//w:vMerge")
                                except (IndexError, AttributeError):
                                    break
                                if nvm and nvm[0].get(qn("w:val")) is None:
                                    rs += 1
                                else:
                                    break
                                k += 1
                            for d in range(rs):
                                rowspan_map[(i + d, j)] = rs - d - 1
                        else:
                            vmerge_skip = True

                    gs = cell.xpath(".//w:gridSpan")
                    if gs:
                        cs = int(gs[0].get(qn("w:val")))

                    if not vmerge_skip:
                        ct = _clean_labels(_cell_text(cell))
                        tag = "th" if i == 0 else "td"
                        attrs = ""
                        if rs > 1:
                            attrs += f' rowspan="{rs}"'
                        if cs > 1:
                            attrs += f' colspan="{cs}"'
                        table_html += f"    <{tag}{attrs}>{ct}</{tag}>\n"
                    j += 1 + (cs - 1)
                table_html += "  </tr>\n"
            table_html += "</table>"
            return table_html


        content = []
        sections = []
        images = []
        found_fb = False
        review_fb = True
        start_markers = ["introducción", "introduction", "introdução"]

        current_list = []
        current_num_id = None

        for element in doc.element.body:
            is_list_item = False
            if isinstance(element, CT_P):
                obj = {}
                paragraph = element
                text_parts = []

                _ns = {"w": WML_NS}
                is_list_item = paragraph.find(".//w:numPr", namespaces=_ns) is not None

                obj_image = False
                for drawing in element.findall(".//w:drawing", namespaces={"w": WML_NS, "a": DRAWINGML_NS}):
                    blip = drawing.find(".//a:blip", namespaces={"w": WML_NS, "a": DRAWINGML_NS})
                    if blip is not None:
                        obj_image = True
                        r_id = blip.get(f"{{{REL_NS}}}embed")
                        image_part = doc.part.related_parts[r_id]
                        image_data = image_part.blob
                        image_name = image_part.partname.split("/")[-1]
                        if image_name not in images:
                            images.append(image_name)
                            wagtail_image = ImageModel.objects.create(
                                title=image_name,
                                file=ContentFile(image_data, name=image_name),
                            )
                            obj["type"] = "image"
                            obj["image"] = wagtail_image.id

                ns_m = {"m": MATH_NS, "w": WML_NS}
                for formula in element.findall(".//m:oMathPara", namespaces=ns_m):
                    obj_image = True
                    mathml_result = transform(formula)
                    mathml_root = etree.fromstring(str(mathml_result))
                    mathml_root = self.replace_mfenced_pipe(mathml_root)
                    obj["type"] = "formula"
                    obj["formula"] = etree.tostring(mathml_root, pretty_print=True, encoding="unicode")

                if not obj_image:
                    if is_list_item:
                        numPr_el = paragraph.find(".//w:numPr", namespaces=_ns)
                        num_id_val = numPr_el.find(".//w:numId", namespaces=_ns).get(qn("w:val")) if numPr_el is not None else None
                        list_type = "bullet"
                        if list_types and num_id_val:
                            for _k, info in list_types.items():
                                if info.get("numId") == num_id_val:
                                    if info.get("0") == "decimal":
                                        list_type = "order"
                                    break
                        if num_id_val != current_num_id:
                            current_num_id = num_id_val
                            if current_list:
                                current_list.append("[/list]")
                                content.append({"type": "list", "list": "\n".join(current_list)})
                                current_list = []
                            current_list.append(f'[list list-type="{list_type}"]')
                    else:
                        if current_list:
                            current_list.append("[/list]")
                            content.append({"type": "list", "list": "\n".join(current_list)})
                            current_list = []

                    for child in paragraph:
                        w_ns = f"{{{WML_NS}}}"
                        if child.tag == f"{w_ns}hyperlink":
                            for r in child.findall("w:r", namespaces=_ns):
                                t_el = r.find("w:t", namespaces=_ns)
                                if t_el is not None and t_el.text:
                                    text_parts.append(t_el.text)
                        elif child.tag == f"{w_ns}r":
                            sz = child.find(".//w:sz", namespaces=_ns)
                            if sz is None:
                                sz = paragraph.find(".//w:rPr/w:sz", namespaces=_ns)
                            obj["font_size"] = int(objectify.fromstring(etree.tostring(sz, encoding="unicode")).get(qn("w:val"))) / 2 if sz is not None else 0

                            b_tag = child.find(".//w:b", namespaces=_ns)
                            if b_tag is None:
                                b_tag = paragraph.find(".//w:rPr/w:b", namespaces=_ns)
                            obj["bold"] = b_tag is not None and b_tag.get(qn("w:val"), "1") in (None, "1", "true", "True")

                            i_tag = child.find(".//w:i", namespaces=_ns)
                            if i_tag is None:
                                i_tag = paragraph.find(".//w:rPr/w:i", namespaces=_ns)
                            obj["italic"] = i_tag is not None and i_tag.get(qn("w:val"), "1") in (None, "1", "true", "True")

                            cleaned = _clean_labels(child.text or "")

                            sections = _identify_section(sections, obj.get("font_size", 0), obj.get("bold", False), cleaned)

                            if obj.get("italic"):
                                text_parts.append(f"<italic>{cleaned}</italic>")
                            else:
                                text_parts.append(cleaned)

                            if _match_paragraph(cleaned):
                                obj["paraph"] = _match_paragraph(cleaned)
                                obj["type"] = obj["paraph"]

                            if review_fb:
                                found_fb = any(w in cleaned.lower() for w in start_markers)

                            if found_fb:
                                found_fb = False
                                review_fb = False
                                sections = [sections[-1]] if sections else []
                                if merge_front:
                                    fb_text = ""
                                    tmp = []
                                    abstract_mode = False
                                    for c in content:
                                        if abstract_mode:
                                            if not c.get("text") or c.get("spacing"):
                                                abstract_mode = False
                                            else:
                                                tmp.append(c)
                                                continue
                                        if c.get("paraph"):
                                            tmp.append(c)
                                            abstract_mode = c["paraph"] == "<abstract>"
                                        else:
                                            fb_text += "\n" + (c.get("text") or c.get("table") or "")
                                    tmp.append({"type": "first_block", "text": fb_text})
                                    content = tmp
                                start_markers = []

                        if child.tag == f"{{{MATH_NS}}}oMath":
                            if "text" not in obj or not isinstance(obj["text"], list):
                                obj["type"] = "compound"
                                obj["text"] = []
                            if text_parts:
                                obj["text"].append({"type": "text", "value": " ".join(text_parts)})
                                text_parts = []
                            mathml_result = transform(child)
                            mathml_root = etree.fromstring(str(mathml_result))
                            self.replace_mfenced_pipe(mathml_root)
                            obj["text"].append({"type": "formula", "value": etree.tostring(mathml_root, pretty_print=True, encoding="unicode")})

                    if "text" not in obj:
                        obj["text"] = _clean_labels(" ".join(text_parts))
                        if _match_paragraph(obj["text"]):
                            obj["paraph"] = _match_paragraph(obj["text"])
                            obj["type"] = obj["paraph"]
                        if is_list_item:
                            obj.pop("font_size", None)
                            current_list.append(f'[list-item]{obj["text"]}[/list-item]')
                    if isinstance(obj.get("text"), list) and text_parts:
                        obj["text"].append({"type": "text", "value": " ".join(text_parts)})
                        text_parts = []

            elif isinstance(element, CT_Tbl):
                obj = {"type": "table", "table": _extract_table(element)}

            if not is_list_item:
                content.append(obj)

        sections.sort(key=_section_priority)
        return sections, content
