import nh3

from django import forms
from markdownx.fields import MarkdownxFormField
from recoco.apps.resources.models import Resource

from .models import DepafiProject, Realisation


class DepafiProjectPerimeterForm(forms.ModelForm):
    class Meta:
        model = DepafiProject
        fields = ["perimeter"]
        widgets = {
            "perimeter": forms.Select(attrs={"class": "fr-select"}),
        }
        labels = {
            "perimeter": "Périmètre",
        }
        help_texts = {
            "perimeter": "Périmètre auquel se rapporte le dossier",
        }


class RealisationForm(forms.ModelForm):
    description = MarkdownxFormField(
        required=False,
        label="Description de l'action",
        help_text="Comment vous l'avez mise en oeuvre, les éventuelles difficultés rencontrées et solutions trouvées, etc.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["resource"].queryset = Resource.on_site.all()
        self.fields["status"].initial = Realisation.DRAFT

    class Meta:
        model = Realisation
        fields = [
            "resource",
            "location",
            "date",
            "partners",
            "description",
            "key_figures",
            "status"
        ]
        widgets = {
            "resource": forms.Select(attrs={"class": "fr-select"}),
            "location": forms.TextInput(attrs={"class": "fr-input"}),
            "date": forms.DateInput(
                attrs={"class": "fr-input", "type": "date"},
                format="%Y-%m-%d",
            ),
            "partners": forms.TextInput(attrs={"class": "fr-input"}),
            "key_figures": forms.Textarea(attrs={"class": "fr-input", "rows": 4}),
        }
        labels = {
            "resource": "Action concernée",
            "location": "Site(s) ou bâtiment(s) concerné(s)",
            "date": "Date de la réalisation",
            "partners": "Partenaire(s)",
            "key_figures": "Chiffres clés",
        }
        help_texts = {
            "resource": "Tapez le nom de la ressource puis sélectionnez-la dans la liste",
            "location": "Ex : Bâtiment sud",
            "partners": "Si vous renseignez plusieurs partenaires, veuillez séparer leur nom par une virgule.",
            "key_figures": "Partagez ici les éléments qui permettent de mesurer l’ampleur et l’impact du changement mis en place (ex. pour un plan vélo : 300 agents sensibilisés, Trajets à vélo passés de 3 à 15 /jour en moyenne etc.)",
        }

    def clean_description(self):
        desc = self.cleaned_data["description"]
        return nh3.clean(desc)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("status") == Realisation.DRAFT:
            return cleaned_data

        for field in Realisation.MANDATORY_TO_PUBLISH:
            if not cleaned_data.get(field):
                self.add_error(field, self.fields[field].error_messages["required"])
