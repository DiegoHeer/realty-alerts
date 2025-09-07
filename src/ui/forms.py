import datetime
from django import forms
from django_celery_beat.models import PeriodicTask
from django.db.models import IntegerChoices

from ui.models import RealtyQuery


class TogglePeriodicTaskForm(forms.ModelForm):
    class Meta:
        model = PeriodicTask
        fields = ["enabled"]
        widgets = {"enabled": forms.CheckboxInput}


class Days(IntegerChoices):
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6


WORKDAYS = [Days.MONDAY, Days.TUESDAY, Days.WEDNESDAY, Days.THURSDAY, Days.FRIDAY]


def _get_hour_choices() -> tuple[tuple[str, int]]:
    return (
        (1, "1 hour"),
        (2, "2 hours"),
        (3, "3 hours"),
        (4, "4 hours"),
        (6, "6 hours"),
        (6, "8 hours"),
        (12, "12 hours"),
        (24, "24 hours"),
    )


# TODO: write test
class RealtyQueryForm(forms.ModelForm):
    day_interval = forms.MultipleChoiceField(initial=WORKDAYS, choices=Days, widget=forms.CheckboxSelectMultiple)
    hour_start = forms.TimeField(initial=datetime.time(9, 00))
    hour_end = forms.TimeField(initial=datetime.time(18, 00))
    hour_interval = forms.ChoiceField(initial=_get_hour_choices()[0], choices=_get_hour_choices())

    class Meta:
        fields = ["name", "ntfy_topic", "query_url"]
        model = RealtyQuery
