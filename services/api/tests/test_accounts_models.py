import pytest

from accounts.models import UserPreferences


@pytest.mark.django_db
def test_user_preferences_defaults(test_user):
    prefs = UserPreferences.objects.create(user=test_user)
    assert prefs.search == {}
    assert prefs.notifications == {}
    assert prefs.search_updated_at is None
    assert prefs.notifications_updated_at is None
    assert prefs.created_at is not None
