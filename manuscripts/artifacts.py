import ipaddress
import os
import shutil
import socket
import tempfile
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.core.files.base import ContentFile
from django.utils import timezone

from .choices import ArtifactType, EventStatus
from .models.article import ArticleArtifact
from .models.processing import ProcessingEvent
from .utils.helpers import checksum_bytes, json_safe, safe_archive_members


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Redirecionamentos não são permitidos para assets externos.")


def is_safe_external_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            return False
    return True


def save_artifact(processing, artifact_type, name, content, article=None, metadata=None, original_path="", source_url="", structure=None):
    if artifact_type == ArtifactType.ASSET and not original_path:
        original_path = os.path.basename(name)
    current = ArticleArtifact.objects.filter(
        processing=processing, article=article, artifact_type=artifact_type, is_current=True
    )
    if artifact_type == ArtifactType.ASSET:
        current = current.filter(original_path=original_path)
    version = (current.order_by("-version").values_list("version", flat=True).first() or 0) + 1
    current.update(is_current=False)
    artifact = ArticleArtifact.objects.create(
        processing=processing,
        article=article,
        artifact_type=artifact_type,
        version=version,
        metadata=json_safe(metadata or {}),
        original_path=original_path,
        source_url=source_url,
        structure=structure,
        checksum=checksum_bytes(content),
        file_size_bytes=len(content),
    )
    artifact.file.save(os.path.basename(name), ContentFile(content), save=True)
    return artifact


def save_path_artifact(processing, artifact_type, path, article=None, metadata=None, structure=None):
    with open(path, "rb") as source:
        return save_artifact(
            processing,
            artifact_type,
            os.path.basename(path),
            source.read(),
            article,
            metadata,
            structure=structure,
        )


def current_xml(processing, article):
    artifact = ArticleArtifact.objects.filter(
        processing=processing, article=article, artifact_type=ArtifactType.XML, is_current=True
    ).first()
    if not artifact:
        raise ValueError(f"Artigo {article} não possui XML neste processamento.")
    return artifact


def article_asset_url_map(processing, article):
    return {
        PurePosixPath(artifact.original_path or artifact.file.name).name: artifact.file.url
        for artifact in ArticleArtifact.objects.filter(
            processing=processing,
            article=article,
            artifact_type=ArtifactType.ASSET,
            is_current=True,
        )
    }


def article_assets_dir(processing, article):
    assets = list(
        ArticleArtifact.objects.filter(
            processing=processing,
            article=article,
            artifact_type=ArtifactType.ASSET,
            is_current=True,
        )
    )
    if not assets:
        return None

    tmp_dir = tempfile.mkdtemp(prefix="scielo_tools_pdf_assets_")
    for artifact in assets:
        original_name = PurePosixPath(artifact.original_path or artifact.file.name).name
        target = os.path.join(tmp_dir, original_name)
        src = artifact.file.path
        if not os.path.exists(target):
            try:
                os.symlink(src, target)
            except OSError:
                shutil.copy2(src, target)
    return tmp_dir


def resolve_article_assets(processing, article, references):
    local_assets = ArticleArtifact.objects.filter(
        processing=processing, artifact_type=ArtifactType.ASSET
    )
    for reference in references:
        parsed_name = PurePosixPath(reference.split("?", 1)[0]).name
        local = next(
            (
                asset
                for asset in local_assets
                if PurePosixPath(asset.original_path).name == parsed_name
            ),
            None,
        )
        if local:
            if local.article_id and local.article_id != article.pk:
                with local.file.open("rb") as source:
                    save_artifact(
                        processing,
                        ArtifactType.ASSET,
                        local.original_path or os.path.basename(local.file.name),
                        source.read(),
                        article,
                        original_path=local.original_path,
                        source_url=local.source_url,
                    )
            else:
                local.article = article
                local.save(update_fields=["article", "updated"])
            continue
        if not is_safe_external_url(reference):
            ProcessingEvent.objects.create(
                processing=processing,
                article=article,
                status=EventStatus.FAILED,
                message=f"Asset ausente ou URL externa bloqueada: {reference}",
                details={"severity": "warning", "asset": reference},
                completed_at=timezone.now(),
            )
            continue
        try:
            request = Request(reference, headers={"User-Agent": "SciELO Tools/1.0"})
            with build_opener(NoRedirectHandler).open(request, timeout=10) as response:
                content = response.read(25 * 1024 * 1024 + 1)
            if len(content) > 25 * 1024 * 1024:
                continue
            save_artifact(
                processing,
                ArtifactType.ASSET,
                parsed_name or "asset",
                content,
                article,
                source_url=reference,
            )
        except Exception as exc:
            ProcessingEvent.objects.create(
                processing=processing,
                article=article,
                status=EventStatus.FAILED,
                message=f"Não foi possível baixar o asset: {reference}",
                details={"severity": "warning", "asset": reference, "error": str(exc)},
                completed_at=timezone.now(),
            )
            continue


def extract_docx_assets(processing, source_artifact, article):
    try:
        with zipfile.ZipFile(source_artifact.file.path) as archive:
            for member in safe_archive_members(archive):
                path = PurePosixPath(member.filename)
                if path.parts[:2] != ("word", "media"):
                    continue
                save_artifact(
                    processing,
                    ArtifactType.ASSET,
                    path.name,
                    archive.read(member),
                    article,
                    original_path=path.name,
                )
    except zipfile.BadZipFile:
        return
