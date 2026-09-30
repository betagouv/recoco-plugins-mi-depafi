"""Cross-site isolation tests.

Each view filtering on the current site gets one test with a realisation
attached to a project of another tenant site: requested from site A, it
must return a 404 or an empty result.
"""

import pytest
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from guardian.shortcuts import assign_perm
from model_bakery import baker

from recoco.apps.projects import utils as project_utils
from recoco.apps.projects.models import Project
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation, RealisationLike
from .conftest import (
    create_url,
    detail_url,
    like_toggle_url,
    list_url,
    make_resource,
)


def make_project_on_site_other(site):
    """Create a project that only exists on the given (other) tenant site."""
    project = baker.make(Project)
    project.project_sites.create(site=site, status="READY", is_origin=True)
    return project


def make_other_site():
    return baker.make("sites.Site", name="other site", domain="other.site")


def by_resource_url(resource):
    return reverse("plugin_mi_depafi:realisations-by-resource", args=[resource.pk])


def map_api_url():
    return reverse("plugin-mi-depafi-realisations-map")


def csv_url():
    return reverse("plugin_mi_depafi:crm-realisation-csv")


# ---------------------------------------------------------------------------
# Realisation detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_detail_returns_404_for_other_site(request, client):
    other_site = make_other_site()
    project = make_project_on_site_other(other_site)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client):
        response = client.get(detail_url(realisation))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Realisation like toggle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_like_toggle_returns_404_for_other_site(request, client):
    other_site = make_other_site()
    project = make_project_on_site_other(other_site)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 404
    assert not RealisationLike.objects.filter(user=user).exists()


# ---------------------------------------------------------------------------
# Realisation create (project of another site is unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_create_returns_404_for_other_site_project(request, client):
    other_site = make_other_site()
    project = make_project_on_site_other(other_site)
    resource = make_resource(request)
    with login(client):
        response = client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
            },
        )
    assert response.status_code == 404
    assert not Realisation.objects.filter(project=project).exists()


# ---------------------------------------------------------------------------
# Realisation list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_list_hides_other_site_realisations(request, client):
    project = make_project_on_site(request)
    other_site = make_other_site()
    other_project = make_project_on_site_other(other_site)

    resource = make_resource(request)
    baker.make(Realisation, project=project, resource=resource)
    other = baker.make(
        Realisation,
        project=other_project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))

    assert response.status_code == 200
    published = list(response.context["published_realisations"])
    drafts = list(response.context["draft_realisations"])
    assert other not in published
    assert other not in drafts
    assert all(r.project == project for r in published + drafts)


# ---------------------------------------------------------------------------
# Realisations by resource
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisations_by_resource_hides_other_site_realisations(request, client):
    project = make_project_on_site(request)
    other_site = make_other_site()
    other_project = make_project_on_site_other(other_site)

    resource = make_resource(request)
    baker.make(
        Realisation,
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    other = baker.make(
        Realisation,
        project=other_project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )

    with login(client):
        response = client.get(by_resource_url(resource))

    assert response.status_code == 200
    assert other not in list(response.context["realisations"])
    assert all(r.project == project for r in response.context["realisations"])


@pytest.mark.django_db
def test_realisations_by_resource_returns_404_for_other_site_resource(request, client):
    other_site = make_other_site()
    resource = baker.make("resources.Resource", sites=[other_site])
    with login(client):
        response = client.get(by_resource_url(resource))
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Realisations map API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisations_map_api_requires_authentication(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    response = client.get(map_api_url())
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_realisations_map_api_hides_other_site_realisations(request, client):
    project = make_project_on_site(request)
    other_site = make_other_site()
    other_project = make_project_on_site_other(other_site)

    resource = make_resource(request)
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    other = baker.make(
        Realisation,
        project=other_project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )

    with login(client):
        response = client.get(map_api_url())

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert other.pk not in ids


# ---------------------------------------------------------------------------
# CRM CSV export
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_crm_csv_hides_other_site_realisations(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    other_site = make_other_site()
    other_project = make_project_on_site_other(other_site)

    resource = make_resource(request, title="Réalisation site A")
    other_resource = make_resource(request, title="Réalisation site B")
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    baker.make(
        Realisation,
        project=other_project,
        resource=other_resource,
        status=Realisation.PUBLISHED,
    )

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url())

    assert response.status_code == 200
    content = response.content.decode("utf-8-sig")
    assert "Réalisation site A" in content
    assert "Réalisation site B" not in content
