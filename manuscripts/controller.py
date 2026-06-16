from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from ai.utils.normalizers import stz_text, stz_year
from journals.models import Issue, Journal

from manuscripts.choices import EventStatus
from manuscripts.models.article import Article
from manuscripts.models.processing import ProcessingEvent
from manuscripts.utils.helpers import checksum_bytes, json_safe
from manuscripts.utils.xml_utils import extract_article_metadata


def get_or_create_article(processing, xml_content=None, title=""):
    metadata = extract_article_metadata(xml_content) if xml_content else {}
    checksum = checksum_bytes(xml_content) if xml_content else processing.input_checksum
    article = None
    if metadata.get("doi"):
        article = Article.objects.filter(doi=metadata["doi"]).first()
    if not article and metadata.get("pid"):
        article = Article.objects.filter(pid=metadata["pid"]).first()
    if not article:
        article = Article.objects.filter(content_checksum=checksum).first()

    artdate_val = metadata.get("artdate")
    if isinstance(artdate_val, str):
        artdate_val = parse_date(artdate_val)

    if not article:
        article = Article.objects.create(
            title=metadata.get("title") or title or processing.title,
            doi=metadata.get("doi", ""),
            pid=metadata.get("pid", ""),
            content_checksum=checksum,
            creator=processing.creator,
            language=metadata.get("language", "en"),
            license=metadata.get("license"),
            elocatid=metadata.get("elocatid", ""),
            fpage=metadata.get("fpage", ""),
            lpage=metadata.get("lpage", ""),
            seq=metadata.get("seq", ""),
            artdate=artdate_val,
        )
    else:
        changed = False
        fields_to_update = {
            "title": metadata.get("title"),
            "doi": metadata.get("doi"),
            "pid": metadata.get("pid"),
            "language": metadata.get("language"),
            "license": metadata.get("license"),
            "elocatid": metadata.get("elocatid"),
            "fpage": metadata.get("fpage"),
            "lpage": metadata.get("lpage"),
            "seq": metadata.get("seq"),
            "artdate": artdate_val,
        }
        for field, value in fields_to_update.items():
            if value and not getattr(article, field):
                setattr(article, field, value)
                changed = True
        if changed:
            article.save()
    processing.articles.add(article)
    return article, metadata


def enrich_article(payload, article):
    updates = {}
    if payload.get("doi") and payload["doi"] != article.doi:
        updates["doi"] = payload["doi"]
    if payload.get("titles"):
        title = payload["titles"][0]["text"]
        if title and title != article.title:
            updates["title"] = title
    for item in payload.get("dates") or []:
        parsed = parse_date(item.get("date") or "")
        if not parsed:
            continue
        if item.get("type") == "published" and parsed != article.artdate:
            updates["artdate"] = parsed
        elif item.get("type") == "ahp" and parsed != article.ahpdate:
            updates["ahpdate"] = parsed

    journal_payload = payload.get("journal")
    matched_journal = article.journal
    if journal_payload and not matched_journal:
        j_title = journal_payload.get("title")
        j_issn = journal_payload.get("issn")
        journal_qs = Journal.objects.none()
        if j_issn:
            clean_issn = str(j_issn).replace("-", "").strip()
            journal_qs = Journal.objects.filter(
                Q(issn__icontains=clean_issn) | Q(pissn__icontains=clean_issn) | Q(eissn__icontains=clean_issn)
                | Q(issn__icontains=str(j_issn).strip()) | Q(pissn__icontains=str(j_issn).strip()) | Q(eissn__icontains=str(j_issn).strip())
            )
        if not journal_qs.exists() and j_title:
            journal_qs = Journal.objects.filter(
                Q(title__iexact=j_title) | Q(short_title__iexact=j_title) | Q(title_nlm__iexact=j_title)
            )
        matched_journal = journal_qs.first()
        if matched_journal:
            updates["journal"] = matched_journal

    if matched_journal and not article.issue:
        issue_payload = payload.get("issue")
        if issue_payload:
            vol = stz_text(issue_payload.get("volume"))
            num = stz_text(issue_payload.get("number"))
            yr = stz_year(issue_payload.get("year"))
            supp = stz_text(issue_payload.get("supplement"))
            issue_qs = Issue.objects.filter(journal=matched_journal)
            if yr:
                issue_qs = issue_qs.filter(year=yr)
            if vol:
                issue_qs = issue_qs.filter(volume=vol)
            if num:
                issue_qs = issue_qs.filter(number=num)
            if supp:
                issue_qs = issue_qs.filter(supplement=supp)
            matched_issue = issue_qs.first()
            if matched_issue:
                updates["issue"] = matched_issue

    return updates


def event_start(processing, action, task_id, article=None):
    processing.current_action = action
    processing.save(update_fields=["current_action", "updated"])
    return ProcessingEvent.objects.create(
        processing=processing, article=article, action=action, status=EventStatus.RUNNING,
        task_id=task_id or "", started_at=timezone.now(),
    )


def event_complete(event, message="", details=None, status=EventStatus.COMPLETED):
    event.status = status
    event.message = message
    event.details = json_safe(details or {})
    event.completed_at = timezone.now()
    event.save()


def event_details_update(event, details):
    event.details = json_safe({**(event.details or {}), **(details or {})})
    event.save(update_fields=["details", "updated"])
