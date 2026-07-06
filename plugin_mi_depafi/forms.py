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
        fields = ["resource", "site", "date", "partners", "description", "key_figures"]
        widgets = {
            "resource": forms.Select(attrs={"class": "fr-select"}),
            "site": forms.TextInput(attrs={"class": "fr-input"}),
            "date": forms.DateInput(
                attrs={"class": "fr-input", "type": "date"},
                format="%Y-%m-%d",
            ),
            "partners": forms.TextInput(attrs={"class": "fr-input"}),
            "key_figures": forms.Textarea(attrs={"class": "fr-input", "rows": 4}),
        }
        labels = {
            "resource": "Nom de la réalisation",
            "site": "Site ou bâtiment concerné",
            "date": "Date de la réalisation",
            "partners": "Partenaire(s)",
            "key_figures": "Chiffres clés",
        }
        help_texts = {
            "resource": "Tapez le nom de la ressource puis sélectionnez-la dans la liste",
            "site": "Texte d’explication à rédiger",
            "partners": "Si vous renseignez plusieurs partenaires, veuillez séparer leur nom par une virgule.",
            "key_figures": "Texte d’explication à rédiger",
        }
