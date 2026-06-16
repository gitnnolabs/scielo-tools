import os
import zipfile
from pathlib import PurePosixPath

from manuscripts.artifacts import resolve_article_assets, save_artifact
from manuscripts.choices import ArtifactType, InputType
from manuscripts.controller import get_or_create_article
from manuscripts.structure import create_structure_version
from manuscripts.utils.xml_utils import parse_xml_structure
from manuscripts.utils.helpers import safe_archive_members


def ingest_xml(processing, name, content, original_path=""):
    article, metadata = get_or_create_article(processing, content)
    artifact = save_artifact(
        processing, ArtifactType.XML, name, content, article, {"referenced_assets": metadata["assets"]}, original_path
    )
    front, body, back, warnings = parse_xml_structure(content)
    structure = create_structure_version(
        article,
        processing,
        processing.confirmed_type or InputType.XML,
        front,
        body,
        back,
        base_xml=content.decode("utf-8"),
        warnings=warnings,
    )
    artifact.structure = structure
    artifact.save(update_fields=["structure", "updated"])
    return article, artifact


def ingest_zip(processing):
    xml_artifacts = []
    source_document = None
    with zipfile.ZipFile(processing.input_file.path) as archive:
        members = list(safe_archive_members(archive))
        documents = [item for item in members if PurePosixPath(item.filename).suffix.lower() == ".docx"]
        if processing.confirmed_type == InputType.SOURCE_PACKAGE and len(documents) != 1:
            raise ValueError("Pacote-fonte deve conter exatamente um documento suportado.")
        for info in members:
            content = archive.read(info)
            suffix = PurePosixPath(info.filename).suffix.lower()
            if suffix == ".xml":
                xml_artifacts.append(ingest_xml(processing, info.filename, content, info.filename))
            elif suffix == ".docx":
                source_document = save_artifact(
                    processing, ArtifactType.SOURCE_DOCUMENT, info.filename, content, original_path=info.filename
                )
            else:
                save_artifact(processing, ArtifactType.ASSET, info.filename, content, original_path=info.filename)
    for article, xml_artifact in xml_artifacts:
        resolve_article_assets(
            processing, article, xml_artifact.metadata.get("referenced_assets", [])
        )
    return source_document, xml_artifacts


def ingest_document(processing):
    if processing.confirmed_type == InputType.SOURCE_PACKAGE:
        source, _xmls = ingest_zip(processing)
        if not source:
            raise ValueError("Documento não encontrado no pacote-fonte.")
        return source
    with processing.input_file.open("rb") as source:
        return save_artifact(
            processing, ArtifactType.SOURCE_DOCUMENT, os.path.basename(processing.input_file.name), source.read()
        )
