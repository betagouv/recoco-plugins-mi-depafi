"""Cross-site isolation tests.

Each view filtering on the current site gets one test with a realisation
attached to a project of another tenant site: requested from site A, it
must return a 404 or an empty result.
"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse
from guardian.shortcuts import assign_perm
from model_bakery import baker
from rest_framework.exceptions import ValidationError

from recoco.apps.projects import utils as project_utils
from recoco.apps.projects.models import Project
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation, RealisationLike
from ..plugin import MiDepafiPlugin
from ..serializers import RealisationNodeSerializer
from .conftest import (
    create_url,
    detail_url,
    like_toggle_url,
    list_url,
    make_resource,
    update_url,
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
        Realisation,
        site=other_site,
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
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
        Realisation,
        site=other_site,
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
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
    baker.make(
        Realisation, site=Site.objects.get_current(), project=project, resource=resource
    )
    other = baker.make(
        Realisation,
        site=other_site,
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
        site=Site.objects.get_current(),
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    other = baker.make(
        Realisation,
        site=other_site,
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
        Realisation,
        site=Site.objects.get_current(),
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
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
        Realisation,
        site=Site.objects.get_current(),
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    other = baker.make(
        Realisation,
        site=other_site,
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
        Realisation,
        site=Site.objects.get_current(),
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    baker.make(
        Realisation,
        site=other_site,
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


# ---------------------------------------------------------------------------
# Project shared by two sites: each site only sees its own realisations
# ---------------------------------------------------------------------------


@pytest.fixture
def shared_project_realisations(request):
    """A project on the current site and on another one, with one published
    realisation created from each site."""
    site = get_current_site(request)
    other_site = make_other_site()
    project = make_project_on_site(request)
    project.project_sites.create(site=other_site, status="READY", is_origin=False)
    resource = baker.make("resources.Resource", sites=[site, other_site])

    own = baker.make(
        Realisation,
        site=site,
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    other = baker.make(
        Realisation,
        site=other_site,
        project=project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )
    return project, resource, own, other


@pytest.mark.django_db
def test_shared_project_list_hides_other_site_realisations(
    client, shared_project_realisations
):
    project, _, own, other = shared_project_realisations
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))

    assert list(response.context["realisations"]) == [own]


@pytest.mark.django_db
def test_shared_project_detail_returns_404_for_other_site_realisation(
    client, shared_project_realisations
):
    _, _, own, other = shared_project_realisations
    # Reverse before requesting: each request clears the enabled plugins
    own_url, other_url = detail_url(own), detail_url(other)
    with login(client):
        assert client.get(own_url).status_code == 200
        assert client.get(other_url).status_code == 404


@pytest.mark.django_db
def test_shared_project_update_returns_404_for_other_site_realisation(
    client, shared_project_realisations
):
    project, _, _, other = shared_project_realisations
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(update_url(project, other))

    assert response.status_code == 404


@pytest.mark.django_db
def test_shared_project_like_toggle_returns_404_for_other_site_realisation(
    client, shared_project_realisations
):
    _, _, _, other = shared_project_realisations
    with login(client) as user:
        response = client.post(like_toggle_url(other))

    assert response.status_code == 404
    assert not RealisationLike.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_shared_project_by_resource_hides_other_site_realisations(
    client, shared_project_realisations
):
    _, resource, own, _ = shared_project_realisations
    with login(client):
        response = client.get(by_resource_url(resource))

    assert list(response.context["realisations"]) == [own]


@pytest.mark.django_db
def test_shared_project_map_api_hides_other_site_realisations(
    client, shared_project_realisations
):
    _, _, own, _ = shared_project_realisations
    with login(client):
        response = client.get(map_api_url())

    assert [item["id"] for item in response.json()] == [own.pk]


@pytest.mark.django_db
def test_shared_project_crm_list_hides_other_site_realisations(
    request, client, shared_project_realisations
):
    _, _, own, _ = shared_project_realisations
    with login(client) as user:
        assign_perm("use_crm", user, get_current_site(request))
        response = client.get(reverse("plugin_mi_depafi:crm-realisation-list"))

    assert list(response.context["realisations"]) == [own]


@pytest.mark.django_db
def test_shared_project_resource_sidebar_counts_current_site_only(
    rf, shared_project_realisations
):
    _, resource, own, _ = shared_project_realisations
    req = rf.get("/")
    req.user = AnonymousUser()

    with patch("plugin_mi_depafi.plugin.render_to_string") as render:
        MiDepafiPlugin().resource_sidebar_panels(resource=resource, request=req)

    context = render.call_args.args[1]
    assert context["count"] == 1
    assert list(context["realisations"]) == [own]


@pytest.mark.django_db
def test_shared_project_crm_annotation_counts_current_site_only(
    request, shared_project_realisations
):
    project, _, _, _ = shared_project_realisations
    req = Mock(site=get_current_site(request))

    annotations = MiDepafiPlugin().crm_project_list_annotations(request=req)
    annotated = Project.objects.annotate(**annotations).get(pk=project.pk)

    assert annotated.realisations_count == 1


@pytest.mark.django_db
def test_node_serializer_rejects_other_site_realisation(shared_project_realisations):
    _, _, own, other = shared_project_realisations
    field = RealisationNodeSerializer().fields["realisation_id"]

    assert field.to_internal_value(own.pk) == own
    with pytest.raises(ValidationError):
        field.to_internal_value(other.pk)
