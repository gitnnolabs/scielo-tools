import io
import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import PurePosixPath

from django.conf import settings
from django.utils.text import slugify

from ai.extract import extract_frontmatter
from docx_parser.parser import DocxParser
from labeling.fragments import plain_paragraph_text
from sps import utils as xml_utils
from sps.xref import is_marked, mark_references, validate_marks

from manuscripts.artifacts import (
    article_asset_url_map,
    article_assets_dir,
    current_xml,
    save_artifact,
    save_path_artifact,
)
from manuscripts.choices import ArtifactType, ProcessingAction
from manuscripts.controller import event_complete, event_details_update, event_start
from manuscripts.models.article import ArticleArtifact
from manuscripts.structure import create_structure_version
from manuscripts.utils.docx_utils import extract_docx_structure
from manuscripts.utils.xml_utils import extract_article_metadata, generate_structure_xml

logger = logging.getLogger(__name__)


def run_action(processing, action, task_id):
    logger.info("Iniciando ação de processamento: %s para o processamento ID=%s", action, processing.pk)
    started_action = time.monotonic()

    if action == ProcessingAction.SPS_PACKAGE_VALIDATION:
        return _run_sps_package_validation(processing, action, task_id, started_action)

    partial = False
    for article in processing.articles.all():
        logger.info("Executando ação %s no artigo ID=%s (%s)", action, article.pk, article)
        started_article_action = time.monotonic()
        event = event_start(processing, action, task_id, article)

        if action == ProcessingAction.CITATION_MARKUP:
            _run_citation_markup(processing, article, event)
        elif action == ProcessingAction.XML_GENERATION:
            _run_xml_generation(processing, article, event)
        elif action == ProcessingAction.XML_VALIDATION:
            partial = _run_xml_validation(processing, article, event) or partial
        elif action == ProcessingAction.SPS_PACKAGE_GENERATION:
            _run_sps_package_generation(processing, article, event)
        elif action == ProcessingAction.HTML_GENERATION:
            _run_html_generation(processing, article, event)
        elif action == ProcessingAction.PDF_GENERATION:
            _run_pdf_generation(processing, article, event)

        logger.info("Ação %s concluída no artigo ID=%s em %.2fs", action, article.pk, time.monotonic() - started_article_action)

    logger.info("Concluída ação de processamento: %s para o processamento ID=%s em %.2fs", action, processing.pk, time.monotonic() - started_action)
    return partial


def _run_sps_package_validation(processing, action, task_id, started_action):
    event = event_start(processing, action, task_id)
    logger.info("Executando validação do pacote SPS em %s...", processing.input_file.path)
    rows, exceptions = xml_utils.validate_zip(processing.input_file.path)
    save_artifact(processing, ArtifactType.VALIDATION_REPORT, "package.validation.json", json.dumps(rows, ensure_ascii=False).encode())
    save_artifact(processing, ArtifactType.VALIDATION_EXCEPTIONS, "package.exceptions.json", json.dumps(exceptions, ensure_ascii=False).encode())
    event_complete(event, "Pacote SPS validado.", {"issues": len(rows), "exceptions": len(exceptions)})
    elapsed = time.monotonic() - started_action
    logger.info("Ação SPS_PACKAGE_VALIDATION concluída em %.2fs. Problemas: %d, Exceções: %d", elapsed, len(rows), len(exceptions))
    return bool(rows or exceptions)


def _run_citation_markup(processing, article, event):
    source = ArticleArtifact.objects.filter(processing=processing, artifact_type=ArtifactType.SOURCE_DOCUMENT, is_current=True).first()
    logger.info("Abrindo arquivo DOCX do artigo: %s", source.file.path)
    document = DocxParser.open_docx(source.file.path)
    if not is_marked(document):
        document = mark_references(document)
    validation = validate_marks(document)
    buffer = io.BytesIO()
    document.save(buffer)
    save_artifact(processing, ArtifactType.MARKED_DOCUMENT, f"{slugify(str(article))}-marked.docx", buffer.getvalue(), article, validation)

    front, body, back, xref_status = extract_docx_structure(document, source.file.path)
    event_details_update(
        event,
        {"frontmatter_ai": {"status": "running", "provider": "pending", "message": "Extraindo metadados estruturais com IA."}},
    )
    front, article_updates, frontmatter_warnings, frontmatter_ai = extract_frontmatter(
        article, front, body, docx_path=source.file.path
    )
    event_details_update(event, {"frontmatter_ai": frontmatter_ai})
    if article_updates:
        for field, value in article_updates.items():
            setattr(article, field, value)
        article.save(update_fields=[*article_updates.keys(), "updated"])

    structure = create_structure_version(
        article, processing, processing.confirmed_type, front, body, back,
        warnings=frontmatter_warnings, xref_status=xref_status,
    )
    _ensure_article_title(article, front)

    event_complete(
        event,
        "Estrutura extraída e citações marcadas.",
        {
            **validation,
            "structure_version": structure.version,
            "body_blocks": len(body),
            "references": structure.references.count(),
            "citations": structure.citations.count(),
            "frontmatter_ai": frontmatter_ai,
            "frontmatter_ai_warnings": frontmatter_warnings,
        },
    )


def _ensure_article_title(article, front):
    if article.title or not front:
        return
    title_val = ""
    for item in front:
        type_, value = _unwrap_item(item)
        if type_ in ("paragraph", "paragraph_with_language") and value.get("label") == "<article-title>":
            title_val = plain_paragraph_text(value.get("paragraph"))
            break
    if not title_val:
        first = front[0]
        _, first_value = _unwrap_item(first)
        title_val = plain_paragraph_text(first_value.get("paragraph", ""))
    if title_val:
        article.title = title_val
        article.save(update_fields=["title", "updated"])


def _unwrap_item(item):
    if hasattr(item, "block_type") and hasattr(item, "value"):
        return item.block_type, item.value
    if isinstance(item, dict):
        return item.get("type"), item.get("value") or {}
    return None, {}


def _run_xml_generation(processing, article, event):
    structure = article.current_structure
    if not structure:
        raise ValueError(f"Artigo {article} não possui estrutura para gerar XML.")
    save_artifact(
        processing, ArtifactType.XML, f"{slugify(str(article))}.xml",
        generate_structure_xml(structure), article, structure=structure,
    )
    event_complete(event, "XML gerado.")


def _run_xml_validation(processing, article, event):
    xml = current_xml(processing, article)
    validation_path, exceptions_path = xml_utils.validate_xml_document(
        xml.file.path, os.path.join(settings.MEDIA_ROOT, "processings", "validation"), {}
    )
    save_path_artifact(processing, ArtifactType.VALIDATION_REPORT, validation_path, article, structure=xml.structure)
    exceptions = save_path_artifact(processing, ArtifactType.VALIDATION_EXCEPTIONS, exceptions_path, article, structure=xml.structure)
    with open(validation_path, encoding="utf-8") as validation_file:
        has_report_rows = sum(1 for _line in validation_file) > 1
    with open(exceptions_path, encoding="utf-8") as exceptions_file:
        has_exceptions = bool(exceptions_file.read().strip())
    has_issues = has_report_rows or has_exceptions
    event_complete(event, "XML validado.", {"has_issues": has_issues})
    return has_issues


def _run_sps_package_generation(processing, article, event):
    xml = current_xml(processing, article)
    with xml.file.open("rb") as xml_source:
        referenced_assets = {
            PurePosixPath(value.split("?", 1)[0]).name
            for value in extract_article_metadata(xml_source.read()).get("assets", [])
        }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(xml.file.path, os.path.basename(xml.file.name))
        for asset in ArticleArtifact.objects.filter(processing=processing, article=article, artifact_type=ArtifactType.ASSET, is_current=True):
            if PurePosixPath(asset.original_path or asset.file.name).name not in referenced_assets:
                continue
            archive.write(asset.file.path, asset.original_path or os.path.basename(asset.file.name))
    save_artifact(
        processing, ArtifactType.SPS_PACKAGE, f"{slugify(str(article))}.zip",
        buffer.getvalue(), article, structure=xml.structure,
    )
    event_complete(event, "Pacote SPS gerado.")


def _run_html_generation(processing, article, event):
    xml = current_xml(processing, article)
    path, language = xml_utils.generate_html_for_xml_document(
        xml.file.path,
        os.path.join(settings.MEDIA_ROOT, "processings", "html"),
        settings.HTML_GENERATION_CONFIG,
        asset_url_map=article_asset_url_map(processing, article),
    )
    save_path_artifact(processing, ArtifactType.HTML, path, article, {"language": language}, structure=xml.structure)
    event_complete(event, "HTML gerado.")


def _run_pdf_generation(processing, article, event):
    xml = current_xml(processing, article)
    tmp_assets_dir = article_assets_dir(processing, article)
    try:
        pdf_params = {
            "assets_dir": tmp_assets_dir,
            "html_config": settings.HTML_GENERATION_CONFIG,
            "asset_url_map": article_asset_url_map(processing, article),
        }
        pdf_path, docx_path, language = xml_utils.generate_pdf_for_xml_document(
            xml.file.path, os.path.join(settings.MEDIA_ROOT, "processings", "pdf"), pdf_params,
        )
    finally:
        if tmp_assets_dir and os.path.isdir(tmp_assets_dir):
            shutil.rmtree(tmp_assets_dir, ignore_errors=True)
    save_path_artifact(processing, ArtifactType.PDF, pdf_path, article, {"language": language}, structure=xml.structure)
    if docx_path:
        save_path_artifact(processing, ArtifactType.INTERMEDIATE_DOCUMENT, docx_path, article, {"language": language}, structure=xml.structure)
    event_complete(event, "PDF gerado.")
