import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def test_auth_user_model():
    assert settings.AUTH_USER_MODEL == "users.CustomUser"


def test_create_custom_user():
    User = get_user_model()
    user = User.objects.create_user(
        username="pytest-user",
        email="pytest@example.com",
        password="pytest-pass",
    )
    assert user.pk is not None
    assert user.username == "pytest-user"


def test_django_system_check():
    call_command("check", verbosity=0)
