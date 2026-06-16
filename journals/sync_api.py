import logging
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q

from core.models import CoreSyncState
from core.utils.requester import fetch_data as fetch
from core.utils.sync_state import finalize_core_sync_state, track_max_from_item

from .models import Issue, Journal

logger = logging.getLogger(__name__)


def _iter_api_pages(url, resource_name):
    while url:
        logger.info(f"Syncing {resource_name} page: {url}")

        data = fetch(
            url, headers={"Accept": "application/json"}, json=True, timeout=(10, 60)
        )
        yield data.get("results", [])
        url = data.get("next")


def _build_journal_from_api_item(item):
    title = item.get("title") or ""
    short_title = item.get("short_title") or ""
    acronym = item.get("acronym") or ""
    
    official = item.get("official") or {}
    pissn = official.get("issn_print") or ""
    eissn = official.get("issn_electronic") or ""
    
    pubname = item.get("publisher", [])
    title_in_database = item.get("title_in_database", [])
    title_nlm = ""

    if title_in_database:
        for t in title_in_database:
            if t.get("name") == "MEDLINE":
                title_nlm = t.get("title") or ""

    if pubname:
        pubname = pubname[0].get("name") or ""
    else:
        pubname = ""

    scielo_journals = item.get("scielo_journal", [])
    issn_scielo = ""
    if scielo_journals:
        issn_scielo = scielo_journals[0].get("issn_scielo") or ""

    return Journal(
        title=title,
        short_title=short_title,
        acronym=acronym,
        pissn=pissn,
        eissn=eissn,
        publisher_name=pubname,
        title_nlm=title_nlm,
        issn=issn_scielo,
    )


def build_api_url_core(domain, endpoint, params):
    url = f"{domain}{endpoint}"
    query = urlencode(params)
    return f"{url}?{query}"


def sync_journals_from_api(
    collection_acron=None,
    issn_scielo=None,
    from_date_updated=None,
):
    sync_state = CoreSyncState.get_for_resource(resource="journal")
    if from_date_updated is None:
        from_date_updated = sync_state.get_from_date_updated(
            settings.CORE_ISSUE_FROM_DATE_CREATED
        )

    params = {"from_date_updated": from_date_updated}
    if collection_acron:
        params["collection"] = collection_acron
    if issn_scielo:
        params["issn"] = issn_scielo

    url = build_api_url_core(
        domain=settings.CORE_API_DOMAIN,
        endpoint=settings.CORE_JOURNAL_API_ENDPOINT,
        params=params,
    )
    synced_count = 0
    skipped_count = 0
    max_created = sync_state.last_updated_at

    for items in _iter_api_pages(url, "journals"):
        for item in items:
            journal = _build_journal_from_api_item(item)
            obj, _ = Journal.objects.update_or_create(
                title=journal.title,
                defaults={
                    "short_title": journal.short_title,
                    "title_nlm": journal.title_nlm,
                    "acronym": journal.acronym,
                    "issn": journal.issn,
                    "pissn": journal.pissn,
                    "eissn": journal.eissn,
                    "publisher_name": journal.publisher_name,
                },
            )
            logger.info(f"Journal {obj} completed")
            synced_count += 1
            max_created = track_max_from_item(max_created, item)

    finalize_core_sync_state(sync_state, max_created)
    logger.info(
        f"Journal sync finished. Synced={synced_count} skipped={skipped_count}"
    )


def _get_journal_from_issue_data(issue_data):
    journal_data = issue_data.get("journal") or {}
    issn_values = [
        journal_data.get("issn_print"),
        journal_data.get("issn_electronic"),
        journal_data.get("scielo_journal"),
    ]
    issn_values = [v for v in issn_values if v]

    if not issn_values:
        return None

    return (
        Journal.objects.filter(
            Q(pissn__in=issn_values)
            | Q(eissn__in=issn_values)
            | Q(issn__in=issn_values)
        )
        .order_by("id")
        .first()
    )


def build_issue_from_data(item):
    issue_data = {
        "number": item.get("number") or "",
        "volume": item.get("volume") or "",
        "season": item.get("season") or "",
        "year": item.get("year") or "",
        "month": item.get("month") or "",
        "supplement": item.get("supplement") or "",
    }
    return issue_data


def get_or_create_issue_from_api_data(issue_data):
    lookup = {
        "journal": issue_data["journal"],
        "number": issue_data["number"],
        "volume": issue_data["volume"],
        "season": issue_data["season"],
        "year": issue_data["year"],
        "month": issue_data["month"],
        "supplement": issue_data["supplement"],
    }
    queryset = Issue.objects.filter(**lookup).order_by("id")
    issue = queryset.first()
    if issue:
        duplicates_count = queryset.count()
        if duplicates_count > 1:
            logger.warning(
                "Issue sync found %s duplicated issues for journal_id=%s "
                "volume=%r number=%r supplement=%r year=%r month=%r season=%r. "
                "Using issue_id=%s.",
                duplicates_count,
                issue.journal_id,
                issue.volume,
                issue.number,
                issue.supplement,
                issue.year,
                issue.month,
                issue.season,
                issue.id,
            )
        return issue, False
    return Issue.objects.create(**issue_data), True


def _get_registered_issn_scielo_values(issn_scielo=None):
    queryset = Journal.objects.exclude(issn="")
    if issn_scielo:
        queryset = queryset.filter(issn=issn_scielo)
    return queryset.values_list("issn", flat=True).distinct()


def sync_issues_from_api(issn_scielo=None, from_date_updated=None):
    sync_state = CoreSyncState.get_for_resource(resource="issue")
    if from_date_updated is None:
        from_date_updated = sync_state.get_from_date_updated(
            settings.CORE_ISSUE_FROM_DATE_CREATED
        )

    registered_issns = _get_registered_issn_scielo_values(issn_scielo=issn_scielo)
    if not registered_issns:
        logger.warning(
            "Issue sync skipped: no registered journals found"
            + (f" for issn_scielo={issn_scielo}" if issn_scielo else "")
        )
        return

    synced_count = 0
    skipped_count = 0
    max_created = sync_state.last_updated_at

    for journal_issn in registered_issns:
        url = build_api_url_core(
            domain=settings.CORE_API_DOMAIN,
            endpoint=settings.CORE_ISSUE_API_ENDPOINT,
            params={
                "from_date_updated": from_date_updated,
                "issn": journal_issn,
            },
        )

        for items in _iter_api_pages(url, f"issues ({journal_issn})"):
            for item in items:
                journal = _get_journal_from_issue_data(item)
                if not journal:
                    skipped_count += 1
                    continue
                issue_data = build_issue_from_data(item)
                issue_data.update({"journal": journal})
                get_or_create_issue_from_api_data(issue_data)
                synced_count += 1
                max_created = track_max_from_item(max_created, item)

    finalize_core_sync_state(sync_state, max_created)
    logger.info(
        f"Issue sync finished. from_date_updated={from_date_updated} "
        f"synced={synced_count} skipped={skipped_count}"
    )
