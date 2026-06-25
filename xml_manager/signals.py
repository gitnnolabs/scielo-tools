from django.db.models.signals import post_delete
from django.dispatch import receiver
from wagtail.documents.models import Document

from xml_manager.models import SPSPackageValidation


@receiver(post_delete, sender=SPSPackageValidation)
def delete_linked_wagtail_documents(sender, instance, **kwargs):
    doc_ids = []
    for doc_id in (
        instance.package_document_id,
        instance.validation_document_id,
        instance.exceptions_document_id,
    ):
        if doc_id and doc_id not in doc_ids:
            doc_ids.append(doc_id)
    if doc_ids:
        Document.objects.filter(pk__in=doc_ids).delete()
