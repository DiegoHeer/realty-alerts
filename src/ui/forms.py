from django import forms
from ui.models import RealtyQuery


class ToggleQueryForm(forms.ModelForm):
    class Meta:
        model = RealtyQuery
        fields = ["enabled"]
        widgets = {"enabled": forms.CheckboxInput}
