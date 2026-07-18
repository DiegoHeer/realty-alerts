from django.conf import settings


def test_supported_languages_configured():
    codes = {code for code, _ in settings.LANGUAGES}
    assert codes == {"en", "nl", "pt"}


def test_locale_paths_configured():
    assert any(str(p).endswith("locale") for p in settings.LOCALE_PATHS)


def test_locale_middleware_installed():
    mw = settings.MIDDLEWARE
    assert "django.middleware.locale.LocaleMiddleware" in mw
    # Must sit after SessionMiddleware and before CommonMiddleware.
    assert (
        mw.index("django.contrib.sessions.middleware.SessionMiddleware")
        < mw.index("django.middleware.locale.LocaleMiddleware")
        < mw.index("django.middleware.common.CommonMiddleware")
    )
