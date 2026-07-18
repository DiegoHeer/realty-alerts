from django.template import Context, Template
from django.utils import translation
from mjml import mjml2html


def test_mjml_python_compiles_basic_document():
    html = mjml2html(
        "<mjml><mj-body><mj-section><mj-column><mj-text>Hi</mj-text></mj-column></mj-section></mj-body></mjml>"
    )
    assert "<html" in html.lower()
    assert "Hi" in html


def _render(src: str, ctx: dict | None = None) -> str:
    return Template("{% load mjml %}" + src).render(Context(ctx or {}))


def test_mjml_tag_compiles_and_resolves_context():
    out = _render(
        "{% mjml %}<mjml><mj-body><mj-section><mj-column>"
        "<mj-text>{{ greeting }}</mj-text></mj-column></mj-section></mj-body></mjml>{% endmjml %}",
        {"greeting": "Hallo"},
    )
    assert "<html" in out.lower()
    assert "Hallo" in out


def test_mjml_tag_applies_trans_before_compile():
    with translation.override("nl"):
        out = _render(
            "{% load i18n %}{% mjml %}<mjml><mj-body><mj-section><mj-column>"
            "<mj-text>{% trans 'Verify your email' %}</mj-text>"
            "</mj-column></mj-section></mj-body></mjml>{% endmjml %}"
        )
    # The nl catalog now translates this msgid; asserts the tag resolves trans
    # nodes (using the active catalog) before compiling, not raw {% %} syntax.
    assert "{% trans" not in out
    assert "Verifieer je e-mailadres" in out
