import pytest
from django.conf import settings
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.shortcuts import resolve_url
from guardian.shortcuts import assign_perm
from model_bakery import baker

from recoco.apps.geomatics.models import Department
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation, RealisationLike
from .conftest import crm_list_url, csv_url, make_resource

# ---------------------------------------------------------------------------
# CRM access control (list + CSV export)
# ---------------------------------------------------------------------------

crm_urls = pytest.mark.parametrize("url_func", [crm_list_url, csv_url])


@crm_urls
@pytest.mark.django_db
def test_crm_view_redirects_unauthenticated_to_login(request, client, url_func):
    make_project_on_site(request)
    response = client.get(url_func())
    assert response.status_code == 302
    assert response.url.startswith(resolve_url(settings.LOGIN_URL))


@crm_urls
@pytest.mark.django_db
def test_crm_view_forbidden_for_non_crm_user(request, client, url_func):
    make_project_on_site(request)
    with login(client):
        response = client.get(url_func())
    assert response.status_code == 403


@crm_urls
@pytest.mark.django_db
def test_crm_view_forbidden_for_crm_user_of_other_site(request, client, url_func):
    make_project_on_site(request)
    other_site = baker.make(Site)
    with login(client) as user:
        assign_perm("use_crm", user, other_site)
        response = client.get(url_func())
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# CRM list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_crm_list_lists_realisations_for_crm_user(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    resource = make_resource(request, title="Action listée")
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    baker.make(RealisationLike, realisation=realisation, _quantity=2)

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(crm_list_url())

    assert response.status_code == 200
    assert [
        (r.resource.title, r.like_count) for r in response.context["realisations"]
    ] == [("Action listée", 2)]


# ---------------------------------------------------------------------------
# CRM CSV export
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_crm_csv_returns_csv_for_crm_user(request, client):
    make_project_on_site(request)
    site = get_current_site(request)
    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url())
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]


@pytest.mark.django_db
def test_crm_csv_contains_realisation_rows(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    dept = baker.make(Department, code="75")
    commune = baker.make(
        "geomatics.Commune", department=dept, name="Paris", postal="75001"
    )
    project.commune = commune
    project.save()

    category = baker.make("resources.Category", name="Energie")
    resource = make_resource(request, title="Mon action", category=category)
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url())

    content = response.content.decode("utf-8-sig")
    assert "Mon action" in content
    assert "Energie" in content
    assert "Paris" in content
    assert "Publié" in content


@pytest.mark.django_db
def test_crm_csv_filters_by_status(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    resource = make_resource(request, title="Published one")
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    resource2 = make_resource(request, title="Draft one")
    baker.make(
        Realisation, project=project, resource=resource2, status=Realisation.DRAFT
    )

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url() + "?status=published")

    content = response.content.decode("utf-8-sig")
    assert "Published one" in content
    assert "Draft one" not in content


@pytest.mark.django_db
def test_crm_csv_filters_by_search(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    resource = make_resource(request, title="Action vélo")
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    resource2 = make_resource(request, title="Action eau")
    baker.make(
        Realisation, project=project, resource=resource2, status=Realisation.PUBLISHED
    )

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url() + "?q=vélo")

    content = response.content.decode("utf-8-sig")
    assert "Action vélo" in content
    assert "Action eau" not in content


@pytest.mark.django_db
def test_crm_csv_is_empty_for_invalid_filter(request, client):
    project = make_project_on_site(request)
    site = get_current_site(request)
    resource = make_resource(request, title="Action visible")
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url() + "?departments=unknown")

    assert response.status_code == 200
    content = response.content.decode("utf-8-sig")
    assert content.startswith("Intitulé,")
    assert "Action visible" not in content
