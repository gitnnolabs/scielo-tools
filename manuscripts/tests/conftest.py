import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from manuscripts.choices import InputType, ProcessStatus
from manuscripts.models.article import Article
from manuscripts.models.processing import Processing


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        username="tester",
        password="test-pass-123",
        email="tester@example.org",
    )


@pytest.fixture
def staff_user(db):
    return get_user_model().objects.create_user(
        username="staff",
        password="test-pass-123",
        email="staff@example.org",
        is_staff=True,
    )


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def article(db, user):
    return Article.objects.create(
        title="Happy path article",
        doi="10.0000/happy.path",
        creator=user,
    )


@pytest.fixture
def processing(db, user, tmp_path):
    uploaded = SimpleUploadedFile("input.xml", b"<article></article>", content_type="application/xml")
    return Processing.objects.create(
        title="Happy path processing",
        creator=user,
        input_file=uploaded,
    )


@pytest.fixture
def xml_processing(processing):
    processing.detected_type = InputType.XML
    processing.status = ProcessStatus.AWAITING_REVIEW
    processing.save(update_fields=["detected_type", "status"])
    return processing
