import json
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from django.test import RequestFactory
from journals.models import Issue, Journal

from manuscripts.views.autocomplete import search


@pytest.fixture
def request_factory():
    return RequestFactory()


def _post_search(request_factory, staff_user, data):
    request = request_factory.post("/admin/autocomplete/search/", data)
    request.user = staff_user
    return search(request)


@pytest.fixture
def journal_with_issues(db):
    journal = Journal.objects.create(title="Test Journal")
    issue_one = Issue.objects.create(journal=journal, volume="1", number="1", year="2024")
    issue_two = Issue.objects.create(journal=journal, volume="2", number="3", year="2025")
    return journal, issue_one, issue_two


@pytest.mark.django_db
def test_search_delegates_to_default_search(request_factory, staff_user, monkeypatch):
    delegated = MagicMock(return_value=MagicMock(status_code=HTTPStatus.OK))
    monkeypatch.setattr("manuscripts.views.autocomplete.default_search", delegated)

    response = _post_search(
        request_factory,
        staff_user,
        {"type": "wagtailcore.Page", "query": "home"},
    )

    delegated.assert_called_once()
    assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db
def test_search_delegates_when_issue_filter_flag_missing(request_factory, staff_user, monkeypatch):
    delegated = MagicMock(return_value=MagicMock(status_code=HTTPStatus.OK))
    monkeypatch.setattr("manuscripts.views.autocomplete.default_search", delegated)

    _post_search(
        request_factory,
        staff_user,
        {"type": "journals.Issue", "journal_id": "1"},
    )

    delegated.assert_called_once()


@pytest.mark.django_db
def test_search_returns_empty_items_without_journal_id(request_factory, staff_user):
    response = _post_search(
        request_factory,
        staff_user,
        {"type": "journals.Issue", "article_issue_filter": "1"},
    )

    assert response.status_code == HTTPStatus.OK
    payload = json.loads(response.content)
    assert payload == {"items": []}


@pytest.mark.django_db
def test_search_filters_issues_by_journal_query_and_exclude(request_factory, staff_user, journal_with_issues):
    journal, issue_one, issue_two = journal_with_issues

    response = _post_search(
        request_factory,
        staff_user,
        {
            "type": "journals.Issue",
            "article_issue_filter": "1",
            "journal_id": str(journal.pk),
            "query": "2024",
            "exclude": str(issue_two.pk),
            "limit": "10",
        },
    )

    assert response.status_code == HTTPStatus.OK
    items = json.loads(response.content)["items"]
    assert len(items) == 1
    assert items[0]["pk"] == issue_one.pk


@pytest.mark.django_db
def test_search_returns_bad_request_for_invalid_model(request_factory, staff_user):
    response = _post_search(
        request_factory,
        staff_user,
        {
            "type": "not.a.RealModel",
            "article_issue_filter": "1",
            "journal_id": "1",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST


@pytest.mark.django_db
def test_search_returns_bad_request_for_invalid_limit(request_factory, staff_user, journal_with_issues):
    journal, _issue_one, _issue_two = journal_with_issues

    response = _post_search(
        request_factory,
        staff_user,
        {
            "type": "journals.Issue",
            "article_issue_filter": "1",
            "journal_id": str(journal.pk),
            "limit": "not-a-number",
        },
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
