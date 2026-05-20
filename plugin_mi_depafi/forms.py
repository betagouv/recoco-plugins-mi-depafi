from django import forms
from markdownx.fields import MarkdownxFormField

from .models import Realisation


class RealisationForm(forms.ModelForm):
    description = MarkdownxFormField(
        required=False,
        label="Description de l'action",
    )

    class Meta:
        model = Realisation
        fields = ["resource", "partners", "description"]
        widgets = {
            "resource": forms.Select(attrs={"class": "fr-select"}),
            "partners": forms.TextInput(attrs={"class": "fr-input"}),
        }
        labels = {
            "resource": "Action réalisée",
            "partners": "Partenaires",
        }
