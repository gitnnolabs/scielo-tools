import os
import zipfile
from pathlib import PurePosixPath

from lxml import etree

from manuscripts.artifacts import save_artifact
from manuscripts.choices import ArtifactType, InputType, ProcessingAction, ProcessStatus
from manuscripts.utils.helpers import checksum_bytes, safe_archive_members
from manuscripts.utils.xml_utils import extract_article_metadata

DOCUMENT_EXTENSIONS = {".docx"}
XML_EXTENSIONS = {".xml"}
ASSET_EXTENSIONS = {
    ".avif", ".csv", ".eps", ".gif", ".jpeg", ".jpg", ".mml", ".png",
    ".svg", ".tif", ".tiff", ".webp",
}

ACTION_DEPENDENCIES = {
    ProcessingAction.XML_GENERATION: [ProcessingAction.CITATION_MARKUP],
    ProcessingAction.XML_VALIDATION: [],
    ProcessingAction.SPS_PACKAGE_VALIDATION: [],
    ProcessingAction.SPS_PACKAGE_GENERATION: [ProcessingAction.XML_VALIDATION],
    ProcessingAction.HTML_GENERATION: [ProcessingAction.XML_VALIDATION],
    ProcessingAction.PDF_GENERATION: [ProcessingAction.XML_VALIDATION],
}

ACTION_ARTIFACT_TYPES = {
    ProcessingAction.CITATION_MARKUP: [ArtifactType.MARKED_DOCUMENT],
    ProcessingAction.XML_GENERATION: [ArtifactType.XML],
    ProcessingAction.XML_VALIDATION: [
        ArtifactType.VALIDATION_REPORT,
        ArtifactType.VALIDATION_EXCEPTIONS,
    ],
    ProcessingAction.SPS_PACKAGE_VALIDATION: [
        ArtifactType.VALIDATION_REPORT,
        ArtifactType.VALIDATION_EXCEPTIONS,
    ],
    ProcessingAction.SPS_PACKAGE_GENERATION: [ArtifactType.SPS_PACKAGE],
    ProcessingAction.HTML_GENERATION: [ArtifactType.HTML],
    ProcessingAction.PDF_GENERATION: [
        ArtifactType.PDF,
        ArtifactType.INTERMEDIATE_DOCUMENT,
    ],
}


def inspect_input(path):
    extension = os.path.splitext(path)[1].lower()
    if extension in DOCUMENT_EXTENSIONS:
        detected = InputType.DOCUMENT
        contents = [{"path": os.path.basename(path), "kind": "document"}]
    elif extension in XML_EXTENSIONS:
        detected = InputType.XML
        contents = [{"path": os.path.basename(path), "kind": "xml"}]
    elif extension == ".zip":
        detected, contents = inspect_zip(path)
    else:
        detected, contents = InputType.UNKNOWN, []
    return {
        "detected_type": detected,
        "contents": contents,
        "suggested_actions": suggested_actions(detected),
    }


def inspect_zip(path):
    contents = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            suffix = PurePosixPath(info.filename).suffix.lower()
            if suffix in DOCUMENT_EXTENSIONS:
                kind = "document"
            elif suffix in XML_EXTENSIONS:
                kind = "xml"
            elif suffix in ASSET_EXTENSIONS:
                kind = "asset"
            else:
                kind = "other"
            contents.append({"path": info.filename, "kind": kind, "size": info.file_size})
    documents = [item for item in contents if item["kind"] == "document"]
    xmls = [item for item in contents if item["kind"] == "xml"]
    if len(documents) == 1 and not xmls:
        detected = InputType.SOURCE_PACKAGE
    elif xmls and not documents:
        detected = InputType.SPS_PACKAGE
    else:
        detected = InputType.AMBIGUOUS_ZIP
    return detected, contents


def suggested_actions(input_type):
    if input_type in (InputType.DOCUMENT, InputType.SOURCE_PACKAGE):
        return [
            ProcessingAction.CITATION_MARKUP,
            ProcessingAction.XML_GENERATION,
            ProcessingAction.XML_VALIDATION,
            ProcessingAction.SPS_PACKAGE_GENERATION,
            ProcessingAction.HTML_GENERATION,
            ProcessingAction.PDF_GENERATION,
        ]
    if input_type == InputType.XML:
        return [
            ProcessingAction.XML_VALIDATION,
            ProcessingAction.SPS_PACKAGE_GENERATION,
            ProcessingAction.HTML_GENERATION,
            ProcessingAction.PDF_GENERATION,
        ]
    if input_type == InputType.SPS_PACKAGE:
        return [ProcessingAction.SPS_PACKAGE_VALIDATION, ProcessingAction.XML_VALIDATION]
    return []


def resolve_actions(requested, input_type):
    requested = list(dict.fromkeys(requested))
    applicable = set(suggested_actions(input_type))
    if input_type == InputType.SPS_PACKAGE:
        applicable.update({ProcessingAction.HTML_GENERATION, ProcessingAction.PDF_GENERATION})
    selected = set(action for action in requested if action in applicable)
    changed = True
    while changed:
        changed = False
        for action in list(selected):
            for dependency in ACTION_DEPENDENCIES.get(action, []):
                if dependency in applicable and dependency not in selected:
                    selected.add(dependency)
                    changed = True
    order = [value for value, _label in ProcessingAction.choices]
    return [action for action in order if action in selected]


def inspect_processing(processing):
    with processing.input_file.open("rb") as source:
        content = source.read()
    result = inspect_input(processing.input_file.path)
    candidates = []
    try:
        if result["detected_type"] == InputType.XML:
            candidates.append(extract_article_metadata(content))
        elif result["detected_type"] == InputType.SPS_PACKAGE:
            with zipfile.ZipFile(processing.input_file.path) as archive:
                for member in safe_archive_members(archive):
                    if PurePosixPath(member.filename).suffix.lower() == ".xml":
                        candidates.append(
                            {
                                "path": member.filename,
                                **extract_article_metadata(archive.read(member)),
                            }
                        )
    except (ValueError, etree.XMLSyntaxError, zipfile.BadZipFile) as exc:
        result["inspection_warning"] = str(exc)
    result["article_candidates"] = candidates
    processing.input_checksum = checksum_bytes(content)
    processing.detected_type = result["detected_type"]
    processing.inspection = result
    processing.requested_actions = result["suggested_actions"]
    processing.status = ProcessStatus.AWAITING_REVIEW
    processing.save()
    save_artifact(processing, ArtifactType.INPUT, os.path.basename(processing.input_file.name), content)
    return processing
