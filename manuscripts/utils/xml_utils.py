import re
from types import SimpleNamespace

from lxml import etree

from sps.xml import get_xml

from manuscripts.utils.helpers import (
    _block,
    _raw_reference,
    to_dict_list,
)


def _plain_text(node):
    return " ".join("".join(node.itertext()).split())


def _get_inner_xml(node):
    xml_str = etree.tostring(node, encoding="unicode", with_tail=False)
    xml_str = re.sub(r'\s*xmlns(:[a-zA-Z0-9]+)?="[^"]+"', '', xml_str)
    match = re.match(r'^<p(?:\s+[^>]*)?>(.*)</p>$', xml_str, re.DOTALL)
    if match:
        return match.group(1).strip()
    return xml_str.strip()


def parse_xml_structure(xml_content):
    root = etree.fromstring(xml_content)
    front = []

    title = root.xpath(".//article-meta/title-group/article-title[1]")
    if title:
        front.append({
            "type": "paragraph_with_language",
            "value": {
                "label": "<article-title>",
                "language": root.get("{http://www.w3.org/XML/1998/namespace}lang", "en"),
                "paragraph": _plain_text(title[0])
            }
        })

    for trans_title in root.xpath(".//article-meta/title-group/trans-title-group"):
        lang = trans_title.get("{http://www.w3.org/XML/1998/namespace}lang")
        title_text = trans_title.xpath("string(./trans-title)")
        if title_text:
            front.append({
                "type": "paragraph_with_language",
                "value": {
                    "label": "<trans-title>",
                    "language": lang,
                    "paragraph": title_text.strip()
                }
            })

    for contrib in root.xpath(".//article-meta/contrib-group/contrib[@contrib-type='author']"):
        surname = contrib.xpath("string(./name/surname)")
        given_names = contrib.xpath("string(./name/given-names)")
        orcid = contrib.xpath("string(./contrib-id[@contrib-id-type='orcid'])")
        xrefs = contrib.xpath("./xref[@ref-type='aff']")
        affids = ",".join(x.get("rid", "").replace("aff", "") for x in xrefs)
        char = xrefs[0].text if xrefs else ""
        front.append({
            "type": "author_paragraph",
            "value": {
                "label": "<contrib>",
                "paragraph": f"{given_names} {surname}".strip(),
                "surname": surname,
                "given_names": given_names,
                "orcid": orcid,
                "affid": affids,
                "char": char,
            }
        })

    for aff in root.xpath(".//article-meta/aff"):
        affid = aff.get("id", "").replace("aff", "")
        char = aff.xpath("string(./label)")
        orgname = aff.xpath("string(./institution[@content-type='orgname'])")
        orgdiv1 = aff.xpath("string(./institution[@content-type='orgdiv1'])")
        orgdiv2 = aff.xpath("string(./institution[@content-type='orgdiv2'])")
        city = aff.xpath("string(.//city)")
        state = aff.xpath("string(.//state)")
        country = aff.xpath("string(.//country)")
        code_country = aff.xpath("string(.//country/@country)")
        original = _plain_text(aff)
        front.append({
            "type": "aff_paragraph",
            "value": {
                "label": "<aff>",
                "paragraph": original,
                "affid": affid,
                "char": char,
                "orgname": orgname,
                "orgdiv1": orgdiv1,
                "orgdiv2": orgdiv2,
                "city": city,
                "state": state,
                "country": country,
                "code_country": code_country,
                "original": original,
            }
        })

    for abstract in root.xpath(".//article-meta/abstract | .//article-meta/trans-abstract"):
        label = "<abstract>"
        lang = abstract.get("{http://www.w3.org/XML/1998/namespace}lang") or root.get("{http://www.w3.org/XML/1998/namespace}lang", "en")
        title_node = abstract.xpath("./title[1]")
        title_text = title_node[0].text if title_node else "Abstract"
        front.append({
            "type": "paragraph",
            "value": {
                "label": "<abstract-title>",
                "paragraph": title_text
            }
        })
        for p in abstract.xpath("./p"):
            front.append({
                "type": "paragraph_with_language",
                "value": {
                    "label": label,
                    "language": lang,
                    "paragraph": _get_inner_xml(p)
                }
            })

    for kwd_group in root.xpath(".//article-meta/kwd-group"):
        lang = kwd_group.get("{http://www.w3.org/XML/1998/namespace}lang")
        title_node = kwd_group.xpath("./title[1]")
        title_text = title_node[0].text if title_node else "Keywords"
        front.append({
            "type": "paragraph",
            "value": {
                "label": "<kwd-title>",
                "paragraph": title_text
            }
        })
        kwds = ", ".join(k.text for k in kwd_group.xpath("./kwd") if k.text)
        front.append({
            "type": "paragraph_with_language",
            "value": {
                "label": "<kwd-group>",
                "language": lang,
                "paragraph": kwds
            }
        })

    body = []
    for node in root.xpath("./body//*"):
        if node.tag == "title":
            body.append(_block("<sec>", _plain_text(node)))
        elif node.tag == "p":
            body.append(_block("<p>", _get_inner_xml(node)))

    back = []
    for position, node in enumerate(root.xpath(".//ref-list/ref"), 1):
        ref_id = node.get("id") or f"B{position}"
        text = _plain_text(node)
        block = _raw_reference(position, text)
        block["value"]["refid"] = ref_id
        back.append(block)

    warnings = []
    supported = {"article", "front", "journal-meta", "article-meta", "title-group", "article-title",
                 "body", "back", "ref-list", "ref", "mixed-citation", "element-citation",
                 "sec", "title", "p", "xref", "italic", "bold", "sub", "sup"}
    unsupported = sorted({etree.QName(node).localname for node in root.iter()} - supported)
    if unsupported:
        warnings.append(
            {"code": "UNMODELED_XML_NODES", "nodes": unsupported, "message": "Nós preservados somente no XML-base."}
        )
    return front, body, back, warnings


def extract_article_metadata(xml_content):
    tree = etree.fromstring(xml_content)
    title_nodes = tree.xpath(".//article-meta/title-group/article-title")
    title = " ".join(title_nodes[0].itertext()).strip() if title_nodes else ""
    doi = tree.xpath("string(.//article-id[@pub-id-type='doi'][1])").strip().lower()
    pid = (
        tree.xpath("string(.//article-id[@pub-id-type='publisher-id'][1])").strip()
        or tree.xpath("string(.//article-id[@pub-id-type='other'][1])").strip()
    )
    href_values = tree.xpath("//@*[local-name()='href']")
    assets = [value for value in href_values if value and not value.startswith("#")]

    namespaces = {
        "xlink": "http://www.w3.org/1999/xlink",
        "xml": "http://www.w3.org/XML/1998/namespace",
    }
    language = tree.xpath("string(./@xml:lang)", namespaces=namespaces) or "en"
    license_url = tree.xpath("string(.//article-meta/permissions/license/@xlink:href)", namespaces=namespaces) or tree.xpath("string(.//article-meta/permissions/license/@href)")
    elocatid = tree.xpath("string(.//article-meta/elocation-id[1])")
    fpage = tree.xpath("string(.//article-meta/fpage[1])")
    lpage = tree.xpath("string(.//article-meta/lpage[1])")
    seq = tree.xpath("string(.//article-meta/fpage[1]/@seq)")

    artdate_str = None
    pub_date_node = tree.xpath(".//article-meta/pub-date[@date-type='pub']") or tree.xpath(".//article-meta/pub-date")
    if pub_date_node:
        day = pub_date_node[0].xpath("string(day)").strip()
        month = pub_date_node[0].xpath("string(month)").strip()
        year = pub_date_node[0].xpath("string(year)").strip()
        if year:
            month_str = month.zfill(2) if month else "01"
            day_str = day.zfill(2) if day else "01"
            if not month_str.isdigit() or int(month_str) < 1 or int(month_str) > 12:
                month_str = "01"
            if not day_str.isdigit() or int(day_str) < 1 or int(day_str) > 31:
                day_str = "01"
            artdate_str = f"{year}-{month_str}-{day_str}"

    return {
        "title": title,
        "doi": doi,
        "pid": pid,
        "assets": assets,
        "language": language,
        "license": license_url,
        "elocatid": elocatid,
        "fpage": fpage,
        "lpage": lpage,
        "seq": seq,
        "artdate": artdate_str,
    }


def _article_adapter(article):
    journal = article.journal
    return SimpleNamespace(
        title=article.title,
        content=[],
        acronym=(journal.acronym if journal else ""),
        title_nlm=(journal.title_nlm if journal else ""),
        journal_title=(journal.title if journal else ""),
        short_title=(journal.short_title if journal else ""),
        pissn=(journal.pissn if journal else ""),
        eissn=(journal.eissn if journal else ""),
        pubname=(journal.publisher_name if journal else ""),
        issue=article.issue,
        language=article.language or "en",
        license=article.license or "",
        artdate=article.artdate,
        ahpdate=article.ahpdate,
        elocatid=article.elocatid or "",
        fpage=article.fpage or "",
        lpage=article.lpage or "",
        seq=article.seq or "",
        dateiso=article.artdate.strftime("%Y-%m-%d") if article.artdate else "",
    )


def generate_structure_xml(structure):
    front_raw = to_dict_list(structure.front)
    body_raw = to_dict_list(structure.body)
    back_raw = to_dict_list(structure.back)

    xml, normalized_body = get_xml(
        _article_adapter(structure.article),
        front_raw,
        body_raw,
        back_raw,
    )
    if normalized_body != body_raw:
        structure.body = normalized_body
        structure.save(update_fields=["body", "updated"])
    if structure.base_xml:
        base = etree.fromstring(structure.base_xml.encode("utf-8"))
        generated = etree.fromstring(xml.encode("utf-8"))

        xpaths_to_sync = (
            "./body",
            "./back/ref-list",
            ".//article-meta/title-group/article-title",
            ".//article-meta/contrib-group",
            ".//article-meta/aff",
            ".//article-meta/abstract",
            ".//article-meta/trans-abstract",
            ".//article-meta/kwd-group",
            ".//article-meta/permissions",
        )
        for xpath in xpaths_to_sync:
            sources = generated.xpath(xpath)
            targets = base.xpath(xpath)

            if not sources:
                for t in targets:
                    t.getparent().remove(t)
                continue

            if targets:
                first_target = targets[0]
                parent = first_target.getparent()
                index = parent.index(first_target)
                for t in targets:
                    parent.remove(t)
                for i, s in enumerate(sources):
                    parent.insert(index + i, s)
            else:
                parent_xpath = xpath.rsplit("/", 1)[0]
                parent_targets = base.xpath(parent_xpath)
                if parent_targets:
                    parent = parent_targets[0]
                    for s in sources:
                        parent.append(s)
        return etree.tostring(base, encoding="utf-8", xml_declaration=True)
    return xml.encode("utf-8")
