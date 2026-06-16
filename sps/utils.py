import copy
import html as html_lib
import os
import re

from django.conf import settings
from lxml import etree
from packtools import HTMLGenerator, data_checker
from packtools.sps.formats.pdf.pipeline import docx
from packtools.sps.formats.pdf.pipeline.xml import extract_article_main_language
from packtools.sps.models.article_license import ArticleLicense
from packtools.sps.pid_provider.models.journal_meta import JournalID, Publisher, Title
from packtools.sps.pid_provider.xml_sps_lib import XMLWithPre
from packtools.sps.validation.xml_validator import get_validation_results

from sps import exceptions
from sps.xref import apply_xml_xrefs_to_docx

_BIBR_REF_ANCHOR_RE = re.compile(r'(<a\b(?=[^>]*\bname="(B\d+_ref)")(?!(?=[^>]*\bid=))[^>]*)(>)')
_BIBR_REF_HREF_RE = re.compile(r'href="#(B\d+)(?:(?:%20|\s+)B\d+)+_ref"')
_HTML_ASSET_ATTR_RE = re.compile(r'(?P<attr>\b(?:src|href))="(?P<value>[^"#?:]+)"')


_BIBR_LINK_STYLE = """
<style>
.xref a[href^="#"] {
  cursor: pointer;
  pointer-events: auto;
}
li:target,
[id$="_ref"]:target {
  scroll-margin-top: 1.5rem;
}
</style>
"""

_BIBR_LINK_SCRIPT = """
<script>
document.addEventListener("click", function (event) {
  var link = event.target.closest && event.target.closest(".xref a[href^='#']");
  if (!link) {
    return;
  }
  var targetId = decodeURIComponent(link.getAttribute("href").slice(1));
  var namedTargets = document.getElementsByName(targetId);
  var target = document.getElementById(targetId) || (namedTargets.length ? namedTargets[0] : null);
  if (!target) {
    return;
  }
  event.preventDefault();
  var scrollTarget = target.closest("li") || target;
  scrollTarget.scrollIntoView({ behavior: "smooth", block: "start" });
  if (history.pushState) {
    history.pushState(null, "", "#" + targetId);
  } else {
    location.hash = targetId;
  }
}, true);
</script>
"""


def _normalize_html_bibr_links(html: str) -> str:
    def add_id(match):
        return f'{match.group(1)} id="{match.group(2)}"{match.group(3)}'

    html = _BIBR_REF_ANCHOR_RE.sub(add_id, html)
    return _BIBR_REF_HREF_RE.sub(lambda match: f'href="#{match.group(1)}_ref"', html)


def _normalize_html_asset_links(html: str, asset_url_map: dict | None = None) -> str:
    if not asset_url_map:
        return html

    def replace(match):
        value = match.group("value")
        asset_url = asset_url_map.get(os.path.basename(value))
        if not asset_url:
            return match.group(0)
        return f'{match.group("attr")}="{html_lib.escape(asset_url, quote=True)}"'

    return _HTML_ASSET_ATTR_RE.sub(replace, html)


def validate_xml_document(xml_file_path, output_root_dir, params):
    if not os.path.exists(output_root_dir):
        os.makedirs(output_root_dir)

    base_fname, fext = os.path.splitext(os.path.basename(xml_file_path))
    path_csv = os.path.join(output_root_dir, f"{base_fname}.validation.csv")
    path_exceptions = os.path.join(output_root_dir, f"{base_fname}.exceptions.json")

    try:
        validator = data_checker.XMLDataChecker(
            path_csv, path_exceptions, xml_file_path
        )
        validator.validate(params=params, csv_per_xml=False)
    except Exception as e:
        raise exceptions.XMLFileValidationError(f"Error during XML validation: {e}")

    return path_csv, path_exceptions


def _extract_journal_data(xmltree):
    try:
        license_code = None
        for lic in ArticleLicense(xmltree).licenses:
            code = lic.get("code")
            if code:
                license_code = code
                break
        return {
            "abbrev_journal_title": Title(xmltree).abbreviated_journal_title,
            "publisher_name_list": Publisher(xmltree).publishers_names,
            "nlm_journal_title": JournalID(xmltree).nlm_ta,
            "license_code": license_code,
        }
    except Exception:
        return {}


def validate_zip(zip_path: str) -> tuple[list, list]:
    rows = []
    exceptions = []
    for xml_with_pre in XMLWithPre.create(path=zip_path):
        xmltree = xml_with_pre.xmltree
        rules = {"journal_data": _extract_journal_data(xmltree)}
        for result in get_validation_results(xmltree, rules):
            if not result:
                continue
            if result.get("response") == "exception":
                exceptions.append(result)
                continue
            if result.get("response") == "OK":
                continue
            group = result.get("group", "")
            item = result.get("item") or ""
            sub_item = result.get("sub_item") or ""
            attribute = "/".join(filter(None, [item, sub_item]))
            rows.append(
                {
                    "group": group,
                    "title": result.get("title"),
                    "parent": result.get("parent"),
                    "parent_id": result.get("parent_id"),
                    "parent_article_type": result.get("parent_article_type"),
                    "item": item,
                    "sub_item": sub_item,
                    "attribute": attribute,
                    "validation_type": result.get("validation_type"),
                    "response": result.get("response"),
                    "expected_value": result.get("expected_value"),
                    "got_value": result.get("got_value"),
                    "advice": result.get("advice"),
                }
            )
    return rows, exceptions


def prepare_xml_for_pdf(xml_tree):
    """
    Return a rendering-only XML copy with the values required by packtools PDF.

    Manuscripts can legitimately reach SciELO Tools before journal, DOI, issue, and
    other publication metadata are assigned. The packtools PDF pipeline still
    expects some of those nodes to exist, so provide neutral display fallbacks
    without changing the canonical SPS XML.
    """
    tree = copy.deepcopy(xml_tree)

    front = tree.find("front")
    if front is None:
        front = etree.Element("front")
        tree.insert(0, front)

    journal_meta = front.find("journal-meta")
    if journal_meta is None:
        journal_meta = etree.Element("journal-meta")
        front.insert(0, journal_meta)

    journal_title_group = journal_meta.find("journal-title-group")
    if journal_title_group is None:
        journal_title_group = etree.SubElement(journal_meta, "journal-title-group")
    if journal_title_group.find("journal-title") is None:
        etree.SubElement(journal_title_group, "journal-title").text = (
            "Journal not assigned"
        )

    article_meta = front.find("article-meta")
    if article_meta is None:
        article_meta = etree.SubElement(front, "article-meta")

    if article_meta.find('.//article-id[@pub-id-type="doi"]') is None:
        etree.SubElement(article_meta, "article-id", {"pub-id-type": "doi"}).text = (
            "pending"
        )

    subject = article_meta.find(
        './/subj-group[@subj-group-type="heading"]/subject'
    )
    if subject is None:
        article_categories = article_meta.find("article-categories")
        if article_categories is None:
            article_categories = etree.SubElement(article_meta, "article-categories")
        subj_group = etree.SubElement(
            article_categories, "subj-group", {"subj-group-type": "heading"}
        )
        etree.SubElement(subj_group, "subject").text = (
            tree.get("article-type") or "article"
        )

    if article_meta.find(".//article-title") is None:
        title_group = article_meta.find("title-group")
        if title_group is None:
            title_group = etree.SubElement(article_meta, "title-group")
        etree.SubElement(title_group, "article-title").text = "Untitled article"

    if tree.find(".//fn-group") is None:
        back = tree.find("back")
        if back is None:
            back = etree.SubElement(tree, "back")
        fn_group = etree.SubElement(back, "fn-group")
        fn = etree.SubElement(fn_group, "fn", {"fn-type": "other"})
        etree.SubElement(fn, "p").text = ""

    return tree


def generate_pdf_for_xml_document(xml_file_path, output_root_dir, params):
    if not os.path.exists(output_root_dir):
        os.makedirs(output_root_dir)

    base_name = os.path.basename(xml_file_path)
    f_name, f_ext = os.path.splitext(base_name)
    path_pdf = os.path.join(output_root_dir, f"{f_name}.pdf")
    path_docx = os.path.join(output_root_dir, f"{f_name}.docx")

    try:
        xml_root = etree.parse(xml_file_path).getroot()
        language = extract_article_main_language(xml_root)
        rendered_xml = prepare_xml_for_pdf(xml_root)

        data = {
            "base_layout": os.path.join(
                settings.BASE_DIR, "docx_parser", "layouts", "two_cols.docx"
            ),
        }
        assets_dir = params.get("assets_dir")
        if assets_dir:
            data["assets_dir"] = assets_dir

        doc = docx.pipeline_docx(rendered_xml, data)
        doc = apply_xml_xrefs_to_docx(doc, rendered_xml)
        doc.save(path_docx)

        _convert_docx_to_pdf(path_docx, path_pdf)
    except Exception as e:
        raise exceptions.XMLFilePDFGenerationError(
            f"Error generating PDF: {e}"
        )

    return path_pdf, path_docx, language


def _convert_docx_to_pdf(docx_path, pdf_path):
    import subprocess
    outdir = os.path.dirname(pdf_path)
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            outdir,
            docx_path,
        ],
        capture_output=True,
        timeout=120,
        check=True,
    )
    generated = os.path.join(
        outdir,
        os.path.splitext(os.path.basename(docx_path))[0] + ".pdf",
    )
    if os.path.isfile(generated) and generated != pdf_path:
        os.rename(generated, pdf_path)
    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"PDF not generated at {pdf_path}")


def generate_html_for_xml_document(xml_file_path, output_root_dir, config, asset_url_map=None):
    if not os.path.exists(output_root_dir):
        os.makedirs(output_root_dir)

    config = config or {}
    try:
        generator = HTMLGenerator.parse(
            xml_file_path,
            valid_only=config.get("valid_only", False),
            xslt=config.get("xslt", "3.0"),
            output_style=config.get("output_style", "website"),
            css=config.get("css", ""),
            print_css=config.get("print_css", ""),
            js=config.get("js", ""),
            bootstrap_css=config.get("bootstrap_css", ""),
            article_css=config.get("article_css", ""),
            math_elem_preference=config.get("math_elem_preference", "mml:math"),
            math_js=config.get("math_js", ""),
            permlink=config.get("permlink", ""),
            url_article_page=config.get("url_article_page", ""),
            url_download_ris=config.get("url_download_ris", ""),
            gs_abstract=config.get("gs_abstract", False),
            design_system_static_img_path=config.get(
                "design_system_static_img_path", ""
            ),
        )
    except Exception as e:
        raise exceptions.XMLFileParsingError(f"Error parsing XML file: {e}")

    base_name = os.path.splitext(os.path.basename(xml_file_path))[0]
    try:
        lang, result = next(iter(generator))
    except StopIteration as e:
        raise exceptions.XMLFileHTMLGenerationError(
            "The XML does not define a document language."
        ) from e
    except Exception as e:
        raise exceptions.XMLFileHTMLGenerationError(
            f"Error converting XML to HTML: {e}"
        ) from e

    path_html = os.path.join(output_root_dir, f"{base_name}-{lang}.html")
    body = etree.tostring(
        result,
        pretty_print=True,
        encoding="unicode",
        method="html",
    )

    stylesheets = []
    for key in ("bootstrap_css", "article_css", "css", "print_css"):
        href = config.get(key)
        if href and href not in stylesheets:
            stylesheets.append(href)
    stylesheet_tags = "".join(
        f'<link rel="stylesheet" href="{html_lib.escape(href, quote=True)}">'
        for href in stylesheets
    )

    scripts = []
    for key in ("js", "math_js"):
        src = config.get(key)
        if src and src not in scripts:
            scripts.append(src)
    script_tags = "".join(
        f'<script src="{html_lib.escape(src, quote=True)}"></script>' for src in scripts
    )

    html = (
        "<!DOCTYPE html>\n"
        f'<html lang="{html_lib.escape(lang, quote=True)}">'
        '<head><meta charset="utf-8">'
        f"<title>{html_lib.escape(base_name)}</title>{stylesheet_tags}{_BIBR_LINK_STYLE}</head>"
        f"<body>{body}{script_tags}{_BIBR_LINK_SCRIPT}</body></html>"
    )
    html = _normalize_html_bibr_links(html)
    html = _normalize_html_asset_links(html, asset_url_map)
    with open(path_html, "w", encoding="utf-8") as fp:
        fp.write(html)

    return path_html, lang
