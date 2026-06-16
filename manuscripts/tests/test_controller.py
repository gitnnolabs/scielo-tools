from datetime import date

import pytest

from journals.models import Issue, Journal
from manuscripts.choices import EventStatus, ProcessingAction
from manuscripts.controller import (
    enrich_article,
    event_complete,
    event_details_update,
    event_start,
    get_or_create_article,
)
from manuscripts.models.article import Article
from manuscripts.utils.helpers import checksum_bytes


@pytest.mark.django_db
def test_get_or_create_article_creates_new_article(processing, monkeypatch):
    metadata = {
        "title": "Created title",
        "doi": "10.1234/created",
        "pid": "S00001",
        "language": "pt",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "elocatid": "e123",
        "fpage": "1",
        "lpage": "10",
        "seq": "1",
        "artdate": "2021-05-20",
    }
    xml_content = b"<article><front /></article>"
    monkeypatch.setattr("manuscripts.controller.extract_article_metadata", lambda _xml: metadata)

    article, returned_metadata = get_or_create_article(
        processing=processing,
        xml_content=xml_content,
    )

    assert article.pk is not None
    assert article.title == "Created title"
    assert article.doi == "10.1234/created"
    assert article.pid == "S00001"
    assert article.language == "pt"
    assert article.license == metadata["license"]
    assert article.elocatid == "e123"
    assert article.fpage == "1"
    assert article.lpage == "10"
    assert article.seq == "1"
    assert article.artdate == date(2021, 5, 20)
    assert article.content_checksum == checksum_bytes(xml_content)
    assert processing.articles.filter(pk=article.pk).exists()
    assert returned_metadata == metadata


@pytest.mark.django_db
def test_get_or_create_article_without_xml_uses_processing_checksum_and_title(processing):
    article, metadata = get_or_create_article(processing=processing, title="Fallback title")

    assert article.title == "Fallback title"
    assert article.content_checksum == processing.input_checksum
    assert metadata == {}
    assert processing.articles.filter(pk=article.pk).exists()


@pytest.mark.django_db
def test_get_or_create_article_matches_existing_by_pid(processing, user, monkeypatch):
    existing = Article.objects.create(pid="S99999", title="Existing", creator=user)
    monkeypatch.setattr(
        "manuscripts.controller.extract_article_metadata",
        lambda _xml: {"pid": "S99999", "title": "Should not replace"},
    )

    article, _metadata = get_or_create_article(processing=processing, xml_content=b"<article />")

    assert article.pk == existing.pk
    assert article.title == "Existing"
    assert Article.objects.count() == 1


@pytest.mark.django_db
def test_get_or_create_article_matches_existing_by_checksum(processing, user, monkeypatch):
    xml_content = b"<article><body unique='checksum-match' /></article>"
    checksum = checksum_bytes(xml_content)
    existing = Article.objects.create(content_checksum=checksum, title="Checksum match", creator=user)
    monkeypatch.setattr(
        "manuscripts.controller.extract_article_metadata",
        lambda _xml: {"title": "Ignored title"},
    )

    article, _metadata = get_or_create_article(processing=processing, xml_content=xml_content)

    assert article.pk == existing.pk
    assert article.title == "Checksum match"
    assert Article.objects.count() == 1


@pytest.mark.django_db
def test_get_or_create_article_updates_empty_fields_on_existing_article(processing, user, monkeypatch):
    existing = Article.objects.create(
        doi="10.1234/update-me",
        title="",
        pid="",
        language="",
        license=None,
        elocatid="",
        fpage="",
        lpage="",
        seq="",
        artdate=None,
        creator=user,
    )
    monkeypatch.setattr(
        "manuscripts.controller.extract_article_metadata",
        lambda _xml: {
            "doi": "10.1234/update-me",
            "title": "Filled title",
            "pid": "S12345",
            "language": "en",
            "license": "https://example.org/license",
            "elocatid": "e42",
            "fpage": "3",
            "lpage": "7",
            "seq": "2",
            "artdate": "2022-01-15",
        },
    )

    article, _metadata = get_or_create_article(processing=processing, xml_content=b"<article />")

    article.refresh_from_db()
    assert article.pk == existing.pk
    assert article.title == "Filled title"
    assert article.pid == "S12345"
    assert article.language == "en"
    assert article.license == "https://example.org/license"
    assert article.elocatid == "e42"
    assert article.fpage == "3"
    assert article.lpage == "7"
    assert article.seq == "2"
    assert article.artdate == date(2022, 1, 15)


@pytest.mark.django_db
def test_get_or_create_article_does_not_overwrite_filled_fields(processing, user, monkeypatch):
    existing = Article.objects.create(
        doi="10.1234/keep",
        title="Keep title",
        pid="KEEP-PID",
        language="pt",
        license="https://example.org/existing",
        elocatid="keep-eloc",
        fpage="10",
        lpage="20",
        seq="9",
        artdate=date(2019, 6, 1),
        creator=user,
    )
    monkeypatch.setattr(
        "manuscripts.controller.extract_article_metadata",
        lambda _xml: {
            "doi": "10.1234/keep",
            "title": "New title",
            "pid": "NEW-PID",
            "language": "en",
            "license": "https://example.org/new",
            "elocatid": "new-eloc",
            "fpage": "1",
            "lpage": "2",
            "seq": "1",
            "artdate": "2024-01-01",
        },
    )

    article, _metadata = get_or_create_article(processing=processing, xml_content=b"<article />")

    article.refresh_from_db()
    assert article.pk == existing.pk
    assert article.title == "Keep title"
    assert article.pid == "KEEP-PID"
    assert article.language == "pt"
    assert article.license == "https://example.org/existing"
    assert article.elocatid == "keep-eloc"
    assert article.fpage == "10"
    assert article.lpage == "20"
    assert article.seq == "9"
    assert article.artdate == date(2019, 6, 1)


@pytest.mark.django_db
def test_enrich_article_updates_doi_title_and_dates(user):
    article = Article.objects.create(
        title="Old title",
        doi="10.1234/old",
        creator=user,
    )

    updates = enrich_article(
        {
            "doi": "10.1234/new",
            "titles": [{"text": "New title"}],
            "dates": [
                {"type": "published", "date": "2021-03-01"},
                {"type": "ahp", "date": "2020-12-15"},
                {"type": "published", "date": "invalid"},
            ],
        },
        article,
    )

    assert updates == {
        "doi": "10.1234/new",
        "title": "New title",
        "artdate": date(2021, 3, 1),
        "ahpdate": date(2020, 12, 15),
    }


@pytest.mark.django_db
def test_enrich_article_skips_unchanged_doi_title_and_dates(user):
    article = Article.objects.create(
        title="Same title",
        doi="10.1234/same",
        artdate=date(2021, 3, 1),
        ahpdate=date(2020, 12, 15),
        creator=user,
    )

    updates = enrich_article(
        {
            "doi": "10.1234/same",
            "titles": [{"text": "Same title"}],
            "dates": [
                {"type": "published", "date": "2021-03-01"},
                {"type": "ahp", "date": "2020-12-15"},
            ],
        },
        article,
    )

    assert updates == {}


@pytest.mark.django_db
def test_enrich_article_matches_journal_by_issn(user):
    journal = Journal.objects.create(title="ISSN Journal", issn="1234-5678")
    article = Article.objects.create(creator=user)

    updates = enrich_article({"journal": {"issn": "1234-5678"}}, article)

    assert updates == {"journal": journal}


@pytest.mark.django_db
def test_enrich_article_matches_journal_by_title_when_issn_missing(user):
    journal = Journal.objects.create(title="Revista Example", short_title="RE")
    article = Article.objects.create(creator=user)

    updates = enrich_article({"journal": {"title": "Revista Example"}}, article)

    assert updates == {"journal": journal}


@pytest.mark.django_db
def test_enrich_article_matches_journal_by_issn_without_dashes(user):
    journal = Journal.objects.create(title="Dashless ISSN", eissn="98765432")
    article = Article.objects.create(creator=user)

    updates = enrich_article({"journal": {"issn": "9876-5432"}}, article)

    assert updates == {"journal": journal}


@pytest.mark.django_db
def test_enrich_article_matches_issue_for_journal(user):
    journal = Journal.objects.create(title="Issue Journal", issn="1111-2222")
    issue = Issue.objects.create(
        journal=journal,
        volume="10",
        number="2",
        year="2023",
        supplement="S1",
    )
    article = Article.objects.create(creator=user)

    updates = enrich_article(
        {
            "journal": {"issn": "1111-2222"},
            "issue": {
                "volume": "10",
                "number": "2",
                "year": "2023",
                "supplement": "S1",
            },
        },
        article,
    )

    assert updates["journal"] == journal
    assert updates["issue"] == issue


@pytest.mark.django_db
def test_enrich_article_uses_existing_journal_and_skips_issue_when_already_set(user):
    journal = Journal.objects.create(title="Linked Journal")
    issue = Issue.objects.create(journal=journal, volume="1", number="1", year="2020")
    article = Article.objects.create(journal=journal, issue=issue, creator=user)

    updates = enrich_article(
        {
            "journal": {"title": "Other Journal"},
            "issue": {"volume": "99", "number": "99", "year": "2099"},
        },
        article,
    )

    assert updates == {}


@pytest.mark.django_db
def test_enrich_article_does_not_set_issue_when_no_match(user):
    journal = Journal.objects.create(title="No Issue Journal")
    article = Article.objects.create(creator=user)

    updates = enrich_article(
        {
            "journal": {"title": "No Issue Journal"},
            "issue": {"volume": "404", "number": "404", "year": "2099"},
        },
        article,
    )

    assert updates == {"journal": journal}


@pytest.mark.django_db
def test_event_details_update_merges_details(processing):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        task_id="task-merge",
    )
    event.details = {"step": 1, "keep": True}
    event.save(update_fields=["details"])

    event_details_update(event, {"step": 2, "extra": "value"})

    event.refresh_from_db()
    assert event.details == {"step": 2, "keep": True, "extra": "value"}


@pytest.mark.django_db
def test_event_details_update_handles_none_details_argument(processing):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        task_id="task-empty",
        article=None,
    )

    event_details_update(event, None)

    event.refresh_from_db()
    assert event.details == {}


@pytest.mark.django_db
def test_event_complete_sets_status_message_and_details(processing):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_VALIDATION,
        task_id="task-complete",
    )

    event_complete(event, message="finished", details={"count": 3}, status=EventStatus.FAILED)

    event.refresh_from_db()
    assert event.status == EventStatus.FAILED
    assert event.message == "finished"
    assert event.details == {"count": 3}
    assert event.completed_at is not None


@pytest.mark.django_db
def test_event_start_links_article(processing, article):
    event = event_start(
        processing=processing,
        action=ProcessingAction.XML_GENERATION,
        task_id="",
        article=article,
    )

    assert event.article == article
    assert event.task_id == ""
    assert event.status == EventStatus.RUNNING
