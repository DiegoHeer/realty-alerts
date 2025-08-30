from django import forms
from django_celery_beat.models import PeriodicTask


class TogglePeriodicTaskForm(forms.ModelForm):
    class Meta:
        model = PeriodicTask
        fields = ["enabled"]
        widgets = {"enabled": forms.CheckboxInput}
