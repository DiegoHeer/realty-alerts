from django import template
from django.utils import timezone, formats
from datetime import datetime

register = template.Library()


@register.filter
def time_or_date(value: datetime):
    """
    Return time (e.g. '14:05') if value is today, otherwise return formatted date.
    Uses Django's formats so it respects localization settings.
    """
    if not value or isinstance(value, datetime):
        return ""

    value_local = timezone.localtime(value)

    today_str = formats.date_format(timezone.localtime(timezone.now()))
    value_date_str = formats.date_format(value_local)

    if value_date_str == today_str:
        return formats.time_format(value_local)
    return value_date_str
