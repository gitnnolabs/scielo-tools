import pytest
from django.contrib.auth import get_user_model

from ia.forms import IAAdminModelForm
from ia.models import GeminiModel

pytestmark = pytest.mark.django_db


class GeminiAdminModelForm(IAAdminModelForm):
    formsets = {}

    class Meta:
        model = GeminiModel
        fields = ("api_key", "is_active")


def test_save_all_sets_creator_on_create():
    user = get_user_model().objects.create_user(
        username="creator-user",
        email="creator@example.com",
        password="secret",
    )
    form = GeminiAdminModelForm(data={"api_key": "key-a", "is_active": True})

    assert form.is_valid()
    instance = form.save_all(user)

    instance.refresh_from_db()
    assert instance.creator_id == user.id
    assert instance.updated_by_id is None


def test_save_all_sets_updated_by_on_update():
    User = get_user_model()
    creator = User.objects.create_user(
        username="first-user",
        email="first@example.com",
        password="secret",
    )
    updater = User.objects.create_user(
        username="updater-user",
        email="updater@example.com",
        password="secret",
    )
    instance = GeminiModel.objects.create(api_key="key-a", creator=creator)
    form = GeminiAdminModelForm(
        data={"api_key": "key-b", "is_active": False}, instance=instance
    )

    assert form.is_valid()
    saved = form.save_all(updater)

    saved.refresh_from_db()
    assert saved.creator_id == creator.id
    assert saved.updated_by_id == updater.id
    assert saved.api_key == "key-b"
