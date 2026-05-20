import pytest
from django.contrib.sites.shortcuts import get_current_site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from recoco.apps.home import models as home_models
from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects import utils as project_utils
from recoco.apps.resources.models import Resource
from recoco.utils import login

from .models import Realisation, RealisationPhoto

PLUGIN_NAME = "plugin_mi_depafi"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def enable_plugin():
    """Set thread-local enabled_plugins so PluginURLResolver allows reverse()."""
    set_enabled_plugins([PLUGIN_NAME])
    yield
    set_enabled_plugins([])


@pytest.fixture(autouse=True)
def multisite_alias(db):
    """Ensure the example.com site has a canonical multisite Alias."""
    from django.contrib.sites.models import Site
    from multisite.models import Alias

    site = Site.objects.filter(domain="example.com").first()
    if site:
        Alias.objects.get_or_create(site=site, domain="example.com", is_canonical=True)


def make_project_on_site(request):
    from recoco.apps.projects.models import Project

    site = get_current_site(request)
    home_models.SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={"schema_name": "test_plugin_mi_depafi", "enabled_plugins": [PLUGIN_NAME]},
    )
    project = baker.make(Project)
    project.project_sites.create(site=site, status="READY", is_origin=True)
    return project


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def list_url(project):
    return reverse(f"{PLUGIN_NAME}:realisation-list", kwargs={"project_id": project.pk})


def create_url(project):
    return reverse(f"{PLUGIN_NAME}:realisation-create", kwargs={"project_id": project.pk})


def detail_url(realisation):
    return reverse(f"{PLUGIN_NAME}:realisation-detail", kwargs={"pk": realisation.pk})


# ---------------------------------------------------------------------------
# Realisation list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_list_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    response = client.get(list_url(project))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_list_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    with login(client):
        response = client.get(list_url(project))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_list_accessible_for_project_member(request, client):
    project = make_project_on_site(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_list_only_shows_project_realisations(request, client):
    project = make_project_on_site(request)
    other_project = make_project_on_site(request)

    resource = baker.make(Resource)
    own = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    baker.make(Realisation, project=other_project, resource=resource, status=Realisation.PUBLISHED)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))

    assert response.status_code == 200
    realisations = list(response.context["published_realisations"])
    assert realisations == [own]


@pytest.mark.django_db
def test_realisation_list_separates_drafts_from_published(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    draft = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    published = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))

    assert response.status_code == 200
    assert list(response.context["draft_realisations"]) == [draft]
    assert list(response.context["published_realisations"]) == [published]


# ---------------------------------------------------------------------------
# Realisation create – GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_create_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    response = client.get(create_url(project))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_create_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    with login(client):
        response = client.get(create_url(project))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_create_form_accessible_for_project_member(request, client):
    project = make_project_on_site(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(create_url(project))
    assert response.status_code == 200
    assert "form" in response.context


# ---------------------------------------------------------------------------
# Realisation create – POST
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_create_saves_draft(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "Ministère", "description": "Une description", "status": "draft"},
        )

    assert response.status_code == 302
    realisation = Realisation.objects.get(project=project)
    assert realisation.status == Realisation.DRAFT
    assert realisation.partners == "Ministère"


@pytest.mark.django_db
def test_realisation_create_saves_published(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "published"},
        )

    assert response.status_code == 302
    assert Realisation.objects.get(project=project).status == Realisation.PUBLISHED


@pytest.mark.django_db
def test_realisation_create_assigns_project(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft"},
        )

    assert Realisation.objects.filter(project=project).count() == 1


@pytest.mark.django_db
def test_realisation_create_redirects_to_list_on_success(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft"},
        )

    assert response.status_code == 302
    assert response["Location"] == list_url(project)


@pytest.mark.django_db
def test_realisation_create_saves_photos(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    image = SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff" + b"\x00" * 10, content_type="image/jpeg")

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft", "photos": [image]},
        )

    realisation = Realisation.objects.get(project=project)
    assert RealisationPhoto.objects.filter(realisation=realisation).count() == 1


@pytest.mark.django_db
def test_realisation_create_invalid_form_returns_200(request, client):
    project = make_project_on_site(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {"resource": "", "partners": "", "description": "", "status": "draft"},
        )

    assert response.status_code == 200
    assert response.context["form"].errors


# ---------------------------------------------------------------------------
# Realisation detail
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_detail_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource)
    response = client.get(detail_url(realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_detail_accessible_for_any_logged_in_user(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_detail_shows_resource_title(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource, title="Mon action vélo")
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"Mon action v\xc3\xa9lo" in response.content


@pytest.mark.django_db
def test_realisation_detail_shows_partners(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(
        Realisation, project=project, resource=resource, partners="Fondation Jean-Moulin"
    )
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"Fondation Jean-Moulin" in response.content


@pytest.mark.django_db
def test_realisation_detail_shows_project_name(request, client):
    project = make_project_on_site(request)
    project.name = "ATE Doubs"
    project.save()
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"ATE Doubs" in response.content


@pytest.mark.django_db
def test_realisation_detail_context_has_realisation(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert response.context["realisation"] == realisation
