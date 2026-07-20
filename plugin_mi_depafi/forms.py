import nh3

from django import forms
from markdownx.fields import MarkdownxFormField
from recoco.apps.resources.models import Resource

from .models import Realisation


class RealisationForm(forms.ModelForm):
    description = MarkdownxFormField(
        required=False,
        label="Description de l'action",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resource"].queryset = Resource.on_site.all()

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
            "site": "Ex : Bâtiment sud",
            "partners": "Si vous renseignez plusieurs partenaires, veuillez séparer leur nom par une virgule.",
            "key_figures": "Partagez ici les éléments qui permettent de mesurer l’ampleur et l’impact du changement mis en place (ex. pour un plan vélo : 300 agents sensibilisés, Trajets à vélo passés de 3 à 15 /jour en moyenne etc.)",
        }

    def clean_description(self):
        desc = self.cleaned_data["description"]
        return nh3.clean(desc)
