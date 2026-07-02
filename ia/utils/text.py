import logging
import os
import zipfile

from lxml import etree

logger = logging.getLogger(__name__)


def extract_text_from_docx(docx_path, limit_chars=30000):
    logger.info("Text extractor: using zipfile for %s", os.path.basename(docx_path))
    with zipfile.ZipFile(docx_path) as archive:
        xml_bytes = archive.read("word/document.xml")

    root = etree.fromstring(xml_bytes)
    nsmap = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs = []
    for paragraph in root.xpath("//w:p | //w:tc//w:p", namespaces=nsmap):
        text = "".join(
            t.text or "" for t in paragraph.xpath(".//w:t", namespaces=nsmap)
        )
        text = text.strip()
        if text:
            paragraphs.append(text)

    result = "\n".join(paragraphs)[:limit_chars]
    logger.info("Text extractor: zipfile produced %d chars", len(result))
    return result


def extract_text_from_docx_via_docling(docx_path, limit_chars=30000):
    from docling.document_converter import DocumentConverter

    logger.info("Text extractor: using docling for %s", os.path.basename(docx_path))
    converter = DocumentConverter()
    result = converter.convert(docx_path)
    text = result.document.export_to_text()
    result_text = text[:limit_chars]
    logger.info("Text extractor: docling produced %d chars", len(result_text))
    return result_text
