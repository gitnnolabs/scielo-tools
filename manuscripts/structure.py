import re

from django.db import transaction

from ai.utils.normalizers import stz_norm
from references.data_utils import get_reference
from references.models import Reference, ReferenceStatus

from manuscripts.models.article import ArticleReference, ArticleStructureVersion, CitationOccurrence
from manuscripts.utils.helpers import (
    XREF_RE,
    checksum_bytes,
    json_safe,
    to_dict_list,
)


def create_structure_version(article, processing, source_kind, front, body, back, base_xml="", warnings=None, xref_status=None):
    front_raw = to_dict_list(front)
    body_raw = to_dict_list(body)
    back_raw = to_dict_list(back)
    with transaction.atomic():
        current = article.structure_versions.select_for_update().filter(is_current=True)
        version = (current.order_by("-version").values_list("version", flat=True).first() or 0) + 1
        current.update(is_current=False)
        structure = ArticleStructureVersion.objects.create(
            article=article,
            processing=processing,
            version=version,
            is_current=True,
            source_kind=source_kind,
            front=json_safe(front_raw),
            body=json_safe(body_raw),
            back=json_safe(back_raw),
            base_xml=base_xml,
            roundtrip_warnings=json_safe(warnings or []),
            xref_status=json_safe(xref_status or {}),
            creator=processing.creator,
        )
        sync_references(structure)
        return structure


def sync_references(structure):
    structure.references.all().delete()
    structure.citations.all().delete()
    by_id = {}
    back_raw = to_dict_list(structure.back)
    for position, block in enumerate(back_raw, 1):
        value = block.get("value", {})
        if block.get("type") != "ref_paragraph":
            continue
        text = value.get("paragraph") or ""
        ref_id = value.get("refid") or f"B{position}"
        normalized = stz_norm(text)
        checksum = checksum_bytes(normalized.encode("utf-8"))
        global_reference = Reference.objects.filter(checksum=checksum).first()
        created = False
        if not global_reference:
            global_reference = Reference.objects.create(
                mixed_citation=text,
                status=ReferenceStatus.CREATING,
                creator=structure.creator,
            )
            created = True
        local = ArticleReference.objects.create(
            structure=structure,
            reference=global_reference,
            position=position,
            ref_id=ref_id,
            mixed_citation=text,
            metadata=value,
            creator=structure.creator,
        )
        by_id[ref_id] = local
        if created:
            transaction.on_commit(lambda pk=global_reference.pk: get_reference.delay(pk))

    body_raw = to_dict_list(structure.body)
    for block_index, block in enumerate(body_raw):
        text = block.get("value", {}).get("paragraph") or ""
        for match in XREF_RE.finditer(text):
            refs = [by_id[rid] for rid in match.group(1).split() if rid in by_id]
            occurrence = CitationOccurrence.objects.create(
                structure=structure,
                text=re.sub("<[^>]+>", "", match.group(2)),
                location={"section": "body", "block": block_index},
                status=(
                    CitationOccurrence.Status.LINKED
                    if refs
                    else CitationOccurrence.Status.ORPHAN
                ),
                creator=structure.creator,
            )
            occurrence.references.set(refs)
