import hashlib
import json
import logging
import re

from lxml import etree

from reference.marking import mark_references
from reference.models import ElementCitation, Reference, ReferenceStatus
from reference.utils.references import parse_reference_list, stz_norm

logger = logging.getLogger(__name__)

meses = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
    "janeiro": "01",
    "fevereiro": "02",
    "março": "03",
    "abril": "04",
    "maio": "05",
    "junho": "06",
    "julho": "07",
    "agosto": "08",
    "setembro": "09",
    "outubro": "10",
    "novembro": "11",
    "dezembro": "12",
}


def get_number_of_month(texto):
    texto = texto.lower()
    for mes, numero in meses.items():
        if re.search(rf"\b{mes}\b", texto):
            return numero
    return None


def append_citation_pages(root, pages):
    value = str(pages).strip().replace("–", "-").replace("—", "-")
    if not value:
        return
    if "-" in value:
        left, right = [part.strip() for part in value.split("-", 1)]
        if left and right:
            etree.SubElement(root, "fpage").text = left
            etree.SubElement(root, "lpage").text = right
            return
    if value.lower().startswith("e") or (value.isdigit() and len(value) >= 5):
        etree.SubElement(root, "elocation-id").text = value
        return
    etree.SubElement(root, "fpage").text = value
    etree.SubElement(root, "lpage").text = value


def append_ext_link(root, uri):
    etree.SubElement(
        root,
        "ext-link",
        attrib={
            "ext-link-type": "uri",
            "{http://www.w3.org/1999/xlink}href": uri,
        },
    ).text = uri


def append_access_date(root, access_date):
    match = re.search(r"\b\d{4}\b", access_date)
    if not match:
        etree.SubElement(
            root,
            "date-in-citation",
            attrib={"content-type": "access-date"},
        ).text = access_date
        return
    year = match.group()
    month = get_number_of_month(access_date) or "01"
    etree.SubElement(
        root,
        "date-in-citation",
        attrib={
            "content-type": "access-date",
            "iso-8601-date": year + "-" + month + "-00",
        },
    ).text = access_date


def get_xml(json_reference):
    try:
        json_reference = json.loads(json_reference)
    except json.JSONDecodeError as exc:
        logger.error("Malformed JSON from IA: %s", exc)
        return etree.Element("error")

    reftype = json_reference.get("reftype")
    if not reftype:
        logger.error("Missing reftype in IA JSON: %s", json_reference)
        return etree.Element("error")

    needs_xlink = reftype in (
        "webpage",
        "data",
        "software",
        "database",
    ) or bool(json_reference.get("uri"))
    if needs_xlink:
        root = etree.Element(
            "element-citation",
            attrib={"publication-type": reftype},
            nsmap={"xlink": "http://www.w3.org/1999/xlink"},
        )
    else:
        root = etree.Element(
            "element-citation",
            attrib={"publication-type": reftype},
        )

    if "authors" in json_reference:
        person_group = etree.SubElement(
            root,
            "person-group",
            attrib={"person-group-type": "author"},
        )
        for author in json_reference["authors"]:
            if "collab" in author and "surname" not in author and "fname" not in author:
                etree.SubElement(person_group, "collab").text = author["collab"]
                continue
            name = etree.Element("name")
            if "surname" in author:
                etree.SubElement(name, "surname").text = author["surname"]
            if "fname" in author:
                etree.SubElement(name, "given-names").text = author["fname"]
            if "collab" in author:
                etree.SubElement(name, "collab").text = author["collab"]
            person_group.append(name)

    if reftype == "journal":
        if "title" in json_reference:
            etree.SubElement(root, "article-title").text = json_reference["title"]
        if "source" in json_reference:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "vol" in json_reference:
            etree.SubElement(root, "volume").text = str(json_reference["vol"])
        if "num" in json_reference:
            etree.SubElement(root, "issue").text = str(json_reference["num"])
        if "pages" in json_reference:
            append_citation_pages(root, json_reference["pages"])
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]

    if reftype == "book":
        if "chapter_title" in json_reference:
            etree.SubElement(root, "part-title").text = json_reference["chapter_title"]
        if "title" in json_reference and "chapter_title" not in json_reference:
            etree.SubElement(root, "source").text = json_reference["title"]
        elif "source" in json_reference:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "vol" in json_reference:
            etree.SubElement(root, "volume").text = str(json_reference["vol"])
        if "pages" in json_reference:
            append_citation_pages(root, json_reference["pages"])
        if "organization" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference[
                "organization"
            ]
        elif "publisher" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference["publisher"]
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]

    if reftype == "thesis":
        if "title" in json_reference:
            etree.SubElement(root, "source").text = json_reference["title"]
        if "degree" in json_reference:
            etree.SubElement(
                root, "comment", attrib={"content-type": "degree"}
            ).text = json_reference["degree"]
        if "organization" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference[
                "organization"
            ]

    if reftype == "confproc":
        if "title" in json_reference:
            etree.SubElement(root, "conf-name").text = json_reference["title"]
        elif "conf_name" in json_reference:
            etree.SubElement(root, "conf-name").text = json_reference["conf_name"]
        if "source" in json_reference:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "conf_loc" in json_reference:
            etree.SubElement(root, "conf-loc").text = json_reference["conf_loc"]
        if "conf_date" in json_reference:
            etree.SubElement(root, "conf-date").text = str(json_reference["conf_date"])
        if "conf_num" in json_reference:
            etree.SubElement(root, "conf-num").text = str(json_reference["conf_num"])
        if "organization" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference[
                "organization"
            ]
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]

    if reftype == "data":
        if "title" in json_reference:
            etree.SubElement(root, "data-title").text = json_reference["title"]
        if "source" in json_reference:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "version" in json_reference:
            etree.SubElement(root, "version").text = str(json_reference["version"])
        if "uri" in json_reference:
            append_ext_link(root, json_reference["uri"])
        if "organization" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference[
                "organization"
            ]
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]
        if "access_date" in json_reference:
            append_access_date(root, json_reference["access_date"])

    if reftype in ("webpage", "software", "database", "legal-doc"):
        if "title" in json_reference:
            etree.SubElement(root, "source").text = json_reference["title"]
        elif "source" in json_reference and root.find("source") is None:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "uri" in json_reference:
            append_ext_link(root, json_reference["uri"])
        if "organization" in json_reference:
            etree.SubElement(root, "publisher-name").text = json_reference[
                "organization"
            ]
        if "country" in json_reference:
            etree.SubElement(root, "publisher-loc").text = json_reference["country"]
        if "version" in json_reference and reftype == "software":
            etree.SubElement(root, "version").text = str(json_reference["version"])
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]
        if "access_date" in json_reference:
            append_access_date(root, json_reference["access_date"])

    if reftype == "other":
        if "title" in json_reference:
            etree.SubElement(root, "source").text = json_reference["title"]
        elif "source" in json_reference:
            etree.SubElement(root, "source").text = json_reference["source"]
        if "doi" in json_reference:
            etree.SubElement(
                root, "pub-id", attrib={"pub-id-type": "doi"}
            ).text = json_reference["doi"]
        if "uri" in json_reference:
            append_ext_link(root, json_reference["uri"])

    if "date" in json_reference:
        etree.SubElement(root, "year").text = str(json_reference["date"])

    return root


def build_ref_list(results):
    root = etree.Element("ref-list")
    etree.SubElement(root, "title").text = "References"

    for index, item in enumerate(results, start=1):
        ref = etree.SubElement(root, "ref", attrib={"id": f"B{index}"})
        mixed = etree.SubElement(ref, "mixed-citation")
        mixed.text = item.get("mixed_citation") or ""

        marked_xml = item.get("data") or ""
        if not marked_xml:
            logger.warning("Missing element-citation XML for ref B%s", index)
            continue
        try:
            citation_node = etree.fromstring(marked_xml.encode("utf-8"))
        except etree.XMLSyntaxError as exc:
            logger.warning("Invalid element-citation XML for ref B%s: %s", index, exc)
            continue
        if citation_node.tag == "error":
            logger.warning("Error element-citation for ref B%s", index)
            continue
        ref.append(citation_node)

    return etree.tostring(root, pretty_print=True, encoding="unicode")


def resolve_reference_result(mixed_citation, user=None, output_type="json"):
    normalized = stz_norm(mixed_citation)
    checksum = hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    try:
        reference = Reference.objects.get(checksum=checksum)
    except Reference.DoesNotExist:
        reference = Reference.objects.create(
            mixed_citation=mixed_citation,
            status=ReferenceStatus.CREATING,
            creator=user,
        )
        get_reference(reference.id)

    element = reference.element_citation.first()
    if output_type in ("xml", "jats"):
        data = element.marked_xml if element else ""
    else:
        data = element.marked if element else {}

    return {
        "mixed_citation": reference.mixed_citation,
        "data": data,
    }


def resolve_references_result(references, user=None, output_type="json"):
    return [
        resolve_reference_result(citation, user=user, output_type=output_type)
        for citation in parse_reference_list(references)
    ]


def get_reference(obj_id):
    logger.info("Starting get_reference for ID=%s", obj_id)
    try:
        obj_reference = Reference.objects.get(id=obj_id)
        logger.info("Marking citation: %r", obj_reference.mixed_citation)
        marked = list(mark_references(obj_reference.mixed_citation))

        citations_created = 0
        for item in marked:
            for i in item["choices"]:
                try:
                    marked_data = json.loads(i) if isinstance(i, str) else i
                except json.JSONDecodeError:
                    marked_data = {"raw": i}
                citation = ElementCitation.objects.create(
                    reference=obj_reference,
                    marked=marked_data,
                    marked_xml=etree.tostring(
                        get_xml(i), pretty_print=True, encoding="unicode"
                    ),
                )
                citations_created += 1
                logger.debug(
                    "Created ElementCitation ID=%s for marked citation: %s",
                    citation.pk,
                    i,
                )

        obj_reference.status = ReferenceStatus.READY
        obj_reference.save()
        logger.info(
            "get_reference completed for ID=%s. Citations created: %d",
            obj_id,
            citations_created,
        )
    except Exception as exc:
        logger.error("Error in get_reference for ID=%s: %s", obj_id, exc, exc_info=True)
        raise
