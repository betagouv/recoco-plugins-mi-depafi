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
        fields = ["resource", "site", "partners", "description"]
        widgets = {
            "resource": forms.Select(attrs={"class": "fr-select"}),
            "site": forms.TextInput(attrs={"class": "fr-input"}),
            "partners": forms.TextInput(attrs={"class": "fr-input"}),
        }
        labels = {
            "resource": "Nom de la réalisation",
            "site": "Site ou bâtiment concerné",
            "partners": "Partenaire(s)",
        }
        help_texts = {
            "resource": "Tapez le nom de la ressource puis sélectionnez-la dans la liste",
            "site": "Texte d’explication à rédiger",
            "partners": "Si vous renseignez plusieurs partenaires, veuillez séparer leur nom par une virgule.",
        }
