import django_filters
from django import forms
from django.contrib.sites.models import Site
from django_filters import fields as filter_fields

from recoco.apps.geomatics import models as geomatics_models
from recoco.apps.resources.models import Category

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


def site_categories(request=None):
    """Resource categories of the current site, built per request."""
    return Category.on_site.order_by("name")


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
        choices=DepafiProject.Perimeter.choices,
        method="filter_perimeter",
        # The select template renders its own "all perimeters" option.
        empty_label=None,
    )

    category = django_filters.ModelChoiceFilter(
        label="Catégorie",
        field_name="resource__category",
        queryset=site_categories,
        # The select template renders its own "all categories" option.
        empty_label=None,
    )

    class Meta:
        model = Realisation
        fields = ["q", "status", "departments", "perimeter", "category"]

    def filter_perimeter(self, queryset, name, value):
        # A project has one profile per site: match the perimeter of the
        # current site's profile only (single filter() call, single join).
        return queryset.filter(
            project__depafi_profiles__site=Site.objects.get_current(),
            project__depafi_profiles__perimeter=value,
        )
