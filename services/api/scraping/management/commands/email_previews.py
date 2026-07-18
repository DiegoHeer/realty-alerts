"""Render every branded account email to a static HTML file for manual cross-client checks."""

from datetime import datetime
from pathlib import Path
from typing import Any

from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandParser
from django.template.loader import render_to_string
from django.utils import timezone, translation
from loguru import logger

from scraping.context_processors import email_branding

DEFAULT_OUT_DIR = "build/email-previews"
LANG_CHOICES = ("en", "nl", "pt")


def _base_context() -> dict[str, Any]:
    return {
        "current_site": Site.objects.get_current(),
        **email_branding(request=None),
    }


def _code_context() -> dict[str, Any]:
    return {**_base_context(), "code": "7F2K-9QD4"}


def _security_notice_context() -> dict[str, Any]:
    return {
        **_base_context(),
        "ip": "203.0.113.5",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "timestamp": timezone.make_aware(datetime(2026, 7, 18, 14, 32)),
    }


def _template_contexts() -> dict[str, dict[str, Any]]:
    """Map each email template prefix to a representative fake render context."""
    return {
        "email_confirmation_signup": _code_context(),
        "email_confirmation": _code_context(),
        "password_reset_code": _code_context(),
        "password_changed": _security_notice_context(),
        "email_changed": {
            **_security_notice_context(),
            "from_email": "old@example.com",
            "to_email": "new@example.com",
        },
        "email_deleted": {
            **_security_notice_context(),
            "deleted_email": "removed@example.com",
        },
        "email_confirm": _base_context(),
        "account_already_exists": {
            **_base_context(),
            "email": "someone@example.com",
            "password_reset_url": "https://huismusapp.com/reset/abc123",
        },
    }


class Command(BaseCommand):
    help = "Render each branded account email to build/email-previews/<prefix>.<lang>.html for manual review."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--out-dir",
            default=DEFAULT_OUT_DIR,
            help=f"Directory to write rendered previews to (default: {DEFAULT_OUT_DIR}).",
        )
        parser.add_argument(
            "--lang",
            default="en",
            choices=LANG_CHOICES,
            help="Language to render previews in (default: en).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        out_dir = Path(options["out_dir"])
        lang = options["lang"]
        out_dir.mkdir(parents=True, exist_ok=True)

        translation.activate(lang)
        try:
            for prefix, context in _template_contexts().items():
                html = render_to_string(f"account/email/{prefix}_message.html", context)
                out_path = out_dir / f"{prefix}.{lang}.html"
                out_path.write_text(html, encoding="utf-8")
                logger.info("Wrote email preview {path}", path=out_path)
        finally:
            translation.deactivate()

        self.stdout.write(self.style.SUCCESS(f"Wrote {len(_template_contexts())} email previews to {out_dir}"))
