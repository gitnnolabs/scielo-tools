import pytest

from ai.utils.normalizers import stz_norm
from manuscripts.choices import InputType
from manuscripts.models.article import ArticleReference, ArticleStructureVersion, CitationOccurrence
from manuscripts.structure import create_structure_version, sync_references
from manuscripts.utils.helpers import checksum_bytes
from references.models import Reference, ReferenceStatus


def _ref_block(position, text, refid=None):
    value = {
        "label": "<p>",
        "paragraph": text,
        "authors": [],
    }
    if refid is not None:
        value["refid"] = refid
    return {"type": "ref_paragraph", "value": value}


def _paragraph_block(text):
    return {"type": "paragraph", "value": {"label": "<p>", "paragraph": text}}


def _make_structure(article, processing, body=None, back=None):
    return ArticleStructureVersion.objects.create(
        article=article,
        processing=processing,
        version=1,
        is_current=True,
        source_kind=InputType.XML,
        front=[],
        body=body or [],
        back=back or [],
        creator=processing.creator,
    )


@pytest.mark.django_db
def test_sync_references_creates_linked_and_orphan_citations(processing, article):
    back = [
        _ref_block(1, "Smith J. Linked reference. 2020.", refid="B1"),
        {"type": "paragraph", "value": {"label": "<p>", "paragraph": "Not a reference block."}},
    ]
    body = [
        _paragraph_block(
            'As shown in <xref ref-type="bibr" rid="B1"><bold>Smith, 2020</bold></xref>.'
        ),
        _paragraph_block(
            'Unknown cite <xref ref-type="bibr" rid="B99">Missing, 1999</xref>.'
        ),
    ]
    structure = _make_structure(article, processing, body=body, back=back)

    sync_references(structure)

    references = list(structure.references.order_by("position"))
    assert len(references) == 1
    assert references[0].ref_id == "B1"
    assert references[0].position == 1
    assert references[0].mixed_citation == "Smith J. Linked reference. 2020."

    citations = list(structure.citations.order_by("created"))
    assert len(citations) == 2

    linked = citations[0]
    assert linked.status == CitationOccurrence.Status.LINKED
    assert linked.text == "Smith, 2020"
    assert linked.location == {"section": "body", "block": 0}
    assert list(linked.references.all()) == [references[0]]

    orphan = citations[1]
    assert orphan.status == CitationOccurrence.Status.ORPHAN
    assert orphan.text == "Missing, 1999"
    assert orphan.location == {"section": "body", "block": 1}
    assert list(orphan.references.all()) == []


@pytest.mark.django_db
def test_sync_references_defaults_ref_id_from_position(processing, article):
    back = [
        {"type": "paragraph", "value": {"label": "<p>", "paragraph": "Ignored block."}},
        _ref_block(2, "Jones A. Default ref id. 2019."),
    ]
    structure = _make_structure(article, processing, back=back)

    sync_references(structure)

    reference = structure.references.get()
    assert reference.ref_id == "B2"
    assert reference.position == 2


@pytest.mark.django_db
def test_sync_references_creates_reference_and_schedules_get_reference(
    processing, article, monkeypatch
):
    delayed = []
    monkeypatch.setattr(
        "manuscripts.structure.get_reference.delay",
        lambda pk: delayed.append(pk),
    )
    monkeypatch.setattr(
        "manuscripts.structure.transaction.on_commit",
        lambda callback: callback(),
    )

    back = [_ref_block(1, "New reference text for async enrichment.")]
    structure = _make_structure(article, processing, back=back)

    sync_references(structure)

    global_reference = Reference.objects.get()
    assert global_reference.status == ReferenceStatus.CREATING
    assert delayed == [global_reference.pk]
    assert structure.references.get().reference == global_reference


@pytest.mark.django_db
def test_sync_references_reuses_existing_reference_by_checksum(processing, article, user, monkeypatch):
    text = "Reused reference text. 2018."
    existing = Reference.objects.create(
        mixed_citation=text,
        status=ReferenceStatus.READY,
        creator=user,
    )
    delayed = []
    monkeypatch.setattr(
        "manuscripts.structure.get_reference.delay",
        lambda pk: delayed.append(pk),
    )
    monkeypatch.setattr(
        "manuscripts.structure.transaction.on_commit",
        lambda callback: callback(),
    )

    back = [_ref_block(1, text, refid="B1")]
    structure = _make_structure(article, processing, back=back)

    sync_references(structure)

    assert Reference.objects.count() == 1
    assert delayed == []
    article_reference = structure.references.get()
    assert article_reference.reference == existing
    expected_checksum = checksum_bytes(stz_norm(text).encode("utf-8"))
    assert existing.checksum == expected_checksum


@pytest.mark.django_db
def test_sync_references_replaces_previous_references_and_citations(processing, article):
    initial_back = [_ref_block(1, "First version.", refid="B1")]
    structure = _make_structure(article, processing, back=initial_back)
    sync_references(structure)
    assert structure.references.count() == 1
    assert structure.citations.count() == 0

    structure.back = [_ref_block(1, "Second version.", refid="B1")]
    structure.save(update_fields=["back"])
    sync_references(structure)

    assert structure.references.count() == 1
    assert structure.references.get().mixed_citation == "Second version."
    assert structure.citations.count() == 0
    assert ArticleReference.objects.filter(structure=structure).count() == 1
    assert CitationOccurrence.objects.filter(structure=structure).count() == 0


@pytest.mark.django_db
def test_create_structure_version_increments_version_and_syncs_references(processing, article, monkeypatch):
    monkeypatch.setattr(
        "manuscripts.structure.get_reference.delay",
        lambda _pk: None,
    )
    monkeypatch.setattr(
        "manuscripts.structure.transaction.on_commit",
        lambda callback: callback(),
    )

    first = create_structure_version(
        article,
        processing,
        InputType.XML,
        front=[],
        body=[],
        back=[_ref_block(1, "Versioned reference.", refid="B1")],
        base_xml="<article />",
        warnings=["warn"],
        xref_status={"B1": "linked"},
    )
    second = create_structure_version(
        article,
        processing,
        InputType.DOCUMENT,
        front=[_paragraph_block("Front matter")],
        body=[],
        back=[],
    )

    first.refresh_from_db()
    second.refresh_from_db()

    assert first.version == 1
    assert second.version == 2
    assert first.is_current is False
    assert second.is_current is True
    assert first.base_xml == "<article />"
    assert first.roundtrip_warnings == ["warn"]
    assert first.xref_status == {"B1": "linked"}
    assert first.references.count() == 1
    assert second.references.count() == 0
