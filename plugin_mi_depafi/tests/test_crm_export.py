import pytest
from django.contrib.sites.shortcuts import get_current_site
from guardian.shortcuts import assign_perm
from model_bakery import baker

from recoco.apps.geomatics.models import Department
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation
from .conftest import csv_url, make_resource

# ---------------------------------------------------------------------------
# CRM CSV export
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_crm_csv_redirects_unauthenticated(request, client):
    make_project_on_site(request)
    response = client.get(csv_url())
    assert response.status_code == 302


@pytest.mark.django_db
def test_crm_csv_forbidden_for_non_crm_user(request, client):
    make_project_on_site(request)
    with login(client):
        response = client.get(csv_url())
    assert response.status_code == 403


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
