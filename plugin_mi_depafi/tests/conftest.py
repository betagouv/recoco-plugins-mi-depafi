from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from model_bakery import baker

from recoco.apps.resources.models import Resource

from ..apps import PLUGIN_NAME
from ..conftest import make_project_on_site, set_project_perimeter
from ..models import Realisation

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def make_resource(request, **kwargs):
    """Create a Resource assigned to the current site so it's usable in views."""
    return baker.make(Resource, sites=[get_current_site(request)], **kwargs)


def make_published_realisation(request, project=None, perimeter=None):
    """Create a published Realisation on the current site.

    A project is created on the site when none is given. When `perimeter`
    is given, it is stored on the project's DepafiProject profile.
    """
    project = project or make_project_on_site(request)
    if perimeter is not None:
        set_project_perimeter(project, perimeter)
    return baker.make(
        Realisation,
        project=project,
        resource=make_resource(request),
        status=Realisation.PUBLISHED,
    )


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def list_url(project):
    return reverse(f"{PLUGIN_NAME}:realisation-list", kwargs={"project_id": project.pk})


def perimeter_update_url(project):
    return reverse(
        f"{PLUGIN_NAME}:depafi-project-perimeter-update",
        kwargs={"project_id": project.pk},
    )


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


def map_api_url():
    return reverse("plugin-mi-depafi-realisations-map")
