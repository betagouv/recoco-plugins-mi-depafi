import django_filters
from django import forms
from django_filters import fields as filter_fields

from recoco.apps.geomatics import models as geomatics_models

from .models import DepafiProject, Realisation


class StripEmptyValuesMixin:
    """Ignore empty submitted values, so `?status=` means "no filtering"."""

    def clean(self, value):
        return super().clean([v for v in value or [] if v])


class StatusChoiceField(StripEmptyValuesMixin, forms.MultipleChoiceField):
    pass


class DepartmentChoiceField(
    StripEmptyValuesMixin, filter_fields.ModelMultipleChoiceField
):
    pass


class StatusFilter(django_filters.MultipleChoiceFilter):
    field_class = StatusChoiceField


class DepartmentFilter(django_filters.ModelMultipleChoiceFilter):
    field_class = DepartmentChoiceField


class RealisationFilter(django_filters.FilterSet):
    """Filter for the CRM list of realisations"""

    q = django_filters.CharFilter(
        label="Rechercher",
        field_name="resource__title",
        lookup_expr="icontains",
    )

    status = StatusFilter(
        label="Statut",
        field_name="status",
        choices=Realisation.STATUS_CHOICES,
    )

    departments = DepartmentFilter(
        label="Localisation",
        field_name="project__commune__department",
        to_field_name="code",
        queryset=geomatics_models.Department.objects.all(),
    )

    perimeter = django_filters.ChoiceFilter(
        label="Périmètre",
        field_name="project__depafi__perimeter",
        choices=DepafiProject.Perimeter.choices,
    )

    class Meta:
        model = Realisation
        fields = ["q", "status", "departments", "perimeter"]
