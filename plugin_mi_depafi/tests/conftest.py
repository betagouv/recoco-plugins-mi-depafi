from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from model_bakery import baker

from recoco.apps.resources.models import Resource

from ..conftest import PLUGIN_NAME

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_resource(request, **kwargs):
    """Create a Resource assigned to the current site so it's usable in views."""
    return baker.make(Resource, sites=[get_current_site(request)], **kwargs)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def list_url(project):
    return reverse(f"{PLUGIN_NAME}:realisation-list", kwargs={"project_id": project.pk})


def create_url(project):
    return reverse(
        f"{PLUGIN_NAME}:realisation-create", kwargs={"project_id": project.pk}
    )


def detail_url(realisation):
    return reverse(f"{PLUGIN_NAME}:realisation-detail", kwargs={"pk": realisation.pk})


def update_url(project, realisation):
    return reverse(
        f"{PLUGIN_NAME}:realisation-update",
        kwargs={"project_id": project.pk, "pk": realisation.pk},
    )


def delete_url(project, realisation):
    return reverse(
        f"{PLUGIN_NAME}:realisation-delete",
        kwargs={"project_id": project.pk, "pk": realisation.pk},
    )


def like_toggle_url(realisation):
    return reverse(
        f"{PLUGIN_NAME}:realisation-like-toggle", kwargs={"pk": realisation.pk}
    )


def csv_url():
    return reverse(f"{PLUGIN_NAME}:crm-realisation-csv")
