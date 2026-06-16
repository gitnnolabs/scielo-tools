import pytest

from manuscripts.choices import ArtifactType, EventStatus, InputType, ProcessingAction
from manuscripts.models.article import (
    Article,
    ArticleArtifact,
    ArticleReference,
    ArticleStructureVersion,
    CitationOccurrence,
)
from manuscripts.models.processing import (
    ArticleInput,
    Processing,
    ProcessingEvent,
    SPSPackageImport,
    XMLImport,
)


@pytest.mark.django_db
def test_processing_article_count_reflects_related_articles(processing, article):
    assert processing.article_count == 0
    processing.articles.add(article)
    assert processing.article_count == 1


@pytest.mark.django_db
def test_processing_str_uses_title_when_available(processing):
    assert str(processing) == "Happy path processing"


@pytest.mark.django_db
def test_proxy_managers_filter_by_detected_or_confirmed_type(user):
    doc_processing = Processing.objects.create(
        title="doc",
        creator=user,
        confirmed_type=InputType.DOCUMENT,
        input_file="processings/input/doc.docx",
    )
    xml_processing = Processing.objects.create(
        title="xml",
        creator=user,
        detected_type=InputType.XML,
        input_file="processings/input/input.xml",
    )

    assert ArticleInput.objects.filter(pk=doc_processing.pk).exists()
    assert not ArticleInput.objects.filter(pk=xml_processing.pk).exists()
    assert XMLImport.objects.filter(pk=xml_processing.pk).exists()


@pytest.mark.django_db
def test_article_str_prefers_title(article):
    assert str(article) == "Happy path article"


@pytest.mark.django_db
def test_article_str_falls_back_to_doi(user):
    article = Article.objects.create(doi="10.0000/fallback", creator=user)
    assert str(article) == "10.0000/fallback"


@pytest.mark.django_db
def test_processing_event_str_uses_action_label(processing):
    event = ProcessingEvent.objects.create(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        status=EventStatus.PENDING,
    )

    assert "Validate XML" in str(event)


@pytest.mark.django_db
def test_article_artifact_str_includes_type_and_version(processing, article):
    artifact = ArticleArtifact.objects.create(
        processing=processing,
        article=article,
        artifact_type=ArtifactType.XML,
        version=2,
        file="processings/artifacts/sample.xml",
    )

    assert str(artifact) == "XML SPS v2"


@pytest.mark.django_db
def test_article_current_artifact_and_structure(processing, article):
    from manuscripts.artifacts import save_artifact
    from manuscripts.structure import create_structure_version

    assert article.current_artifact(ArtifactType.XML) is None
    assert article.current_structure is None

    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    artifact = save_artifact(
        processing,
        ArtifactType.XML,
        "article.xml",
        b"<article />",
        article=article,
        structure=structure,
    )

    assert article.current_artifact(ArtifactType.XML) == artifact
    assert article.current_structure == structure


@pytest.mark.django_db
def test_article_structure_version_str(processing, article):
    from manuscripts.structure import create_structure_version

    structure = create_structure_version(article, processing, InputType.XML, [], [], [])
    assert str(structure) == f"{article} - structure v1"


@pytest.mark.django_db
def test_article_reference_and_citation_str(processing, article, user):
    from manuscripts.structure import create_structure_version

    structure = create_structure_version(
        article,
        processing,
        InputType.XML,
        [],
        [],
        [{"type": "ref_paragraph", "value": {"refid": "B1", "paragraph": "Citation text"}}],
    )
    reference = structure.references.first()
    assert str(reference).startswith("B1:")

    citation = CitationOccurrence.objects.create(
        structure=structure,
        text="(Author, 2024)",
        status=CitationOccurrence.Status.ORPHAN,
        creator=user,
    )
    assert str(citation) == "(Author, 2024)"


@pytest.mark.django_db
def test_sps_package_import_manager_filters_ambiguous_zip(user):
    ambiguous = Processing.objects.create(
        title="ambiguous",
        creator=user,
        detected_type=InputType.AMBIGUOUS_ZIP,
        input_file="processings/input/ambiguous.zip",
    )

    assert SPSPackageImport.objects.filter(pk=ambiguous.pk).exists()


@pytest.mark.django_db
def test_processing_event_str_without_action(processing):
    event = ProcessingEvent.objects.create(
        processing=processing,
        status=EventStatus.PENDING,
    )

    assert "Input" in str(event)
