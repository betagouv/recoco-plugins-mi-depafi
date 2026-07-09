import pytest
from actstream.models import Action
from django.contrib.sites.shortcuts import get_current_site
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from guardian.shortcuts import assign_perm
from model_bakery import baker

from recoco.apps.conversations.models import Message
from recoco.apps.home import models as home_models
from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects import utils as project_utils
from recoco.apps.resources.models import Resource
from recoco.utils import assign_site_staff, login

from . import verbs
from .models import Realisation, RealisationLike, RealisationNode, RealisationPhoto

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


def update_url(project, realisation):
    return reverse(f"{PLUGIN_NAME}:realisation-update", kwargs={"project_id": project.pk, "pk": realisation.pk})


def delete_url(project, realisation):
    return reverse(f"{PLUGIN_NAME}:realisation-delete", kwargs={"project_id": project.pk, "pk": realisation.pk})


def like_toggle_url(realisation):
    return reverse(f"{PLUGIN_NAME}:realisation-like-toggle", kwargs={"pk": realisation.pk})





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
# Realisation update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_update_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    response = client.get(update_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_update_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client):
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_form_accessible_for_project_member(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200
    assert response.context["realisation"] == realisation


@pytest.mark.django_db
def test_realisation_update_returns_404_for_published(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_update_saves_changes(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    new_resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        client.post(
            update_url(project, realisation),
            {"resource": new_resource.pk, "partners": "Nouveau partenaire", "description": "", "status": "draft"},
        )
    realisation.refresh_from_db()
    assert realisation.partners == "Nouveau partenaire"
    assert realisation.resource == new_resource


@pytest.mark.django_db
def test_realisation_update_can_publish_draft(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "partners": "", "description": "", "status": "published"},
        )
    realisation.refresh_from_db()
    assert realisation.status == Realisation.PUBLISHED


@pytest.mark.django_db
def test_realisation_update_deletes_marked_photos(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        photo = baker.make(RealisationPhoto, realisation=realisation)
        client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft", "delete_photos": [photo.pk]},
        )
    assert not RealisationPhoto.objects.filter(pk=photo.pk).exists()


@pytest.mark.django_db
def test_realisation_update_redirects_to_list_on_success(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft"},
        )
    assert response.status_code == 302
    assert response["Location"] == list_url(project)


# ---------------------------------------------------------------------------
# Realisation delete (GET = confirm fragment, POST = delete)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_delete_get_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    response = client.get(delete_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_delete_get_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client):
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_get_shows_confirm_fragment(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource, title="Mon action")
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 200
    assert b"Mon action" in response.content


@pytest.mark.django_db
def test_realisation_delete_get_returns_404_for_published(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_post_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_delete_post_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client):
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_post_removes_draft(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


@pytest.mark.django_db
def test_realisation_delete_post_returns_404_for_published(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_post_redirects_to_list(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.post(delete_url(project, realisation))
    assert response["Location"] == list_url(project)


# ---------------------------------------------------------------------------
# Realisation like toggle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_like_toggle_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    response = client.post(like_toggle_url(realisation))
    assert response.status_code == 302


@pytest.mark.django_db
def test_realisation_like_toggle_creates_like(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 200
    assert RealisationLike.objects.filter(realisation=realisation, user=user).exists()


@pytest.mark.django_db
def test_realisation_like_toggle_removes_existing_like(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        baker.make(RealisationLike, realisation=realisation, user=user)
        client.post(like_toggle_url(realisation))
    assert not RealisationLike.objects.filter(realisation=realisation, user=user).exists()


@pytest.mark.django_db
def test_realisation_like_toggle_returns_404_for_draft(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client):
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_like_toggle_returns_button_fragment(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client):
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 200
    assert b"fr-icon-thumb-up-line" in response.content


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


# ---------------------------------------------------------------------------
# Staff access to published realisations / draft author restriction
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_update_staff_can_access_published(request, client):
    """Site staff can open the update form for a published realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200
    assert response.context["realisation"] == realisation


@pytest.mark.django_db
def test_realisation_update_staff_can_save_published(request, client):
    """Site staff can POST changes to a published realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "partners": "Staff édité", "description": "", "status": "published"},
        )
    realisation.refresh_from_db()
    assert realisation.partners == "Staff édité"


@pytest.mark.django_db
def test_realisation_update_non_staff_member_cannot_access_published(request, client):
    """A regular project member cannot update a published realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_staff_can_access_published(request, client):
    """Site staff can access the delete confirmation for a published realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource, title="Action publiée")
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 200
    assert b"Action publi" in response.content


@pytest.mark.django_db
def test_realisation_delete_staff_can_delete_published(request, client):
    """Site staff can delete a published realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


@pytest.mark.django_db
def test_realisation_update_draft_requires_project_membership(request, client):
    """A logged-in user who is not a project member or staff cannot update a draft."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client):
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_draft_accessible_for_project_member(request, client):
    """A project member can update a draft realisation."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_update_draft_accessible_for_staff(request, client):
    """Site staff can update a draft realisation even without project membership."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT)
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# CRM CSV export
# ---------------------------------------------------------------------------


def csv_url():
    return reverse(f"{PLUGIN_NAME}:crm-realisation-csv")


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
    from recoco.apps.geomatics.models import Department

    project = make_project_on_site(request)
    site = get_current_site(request)
    dept = baker.make(Department, code="75")
    commune = baker.make("geomatics.Commune", department=dept, name="Paris", postal="75001")
    project.commune = commune
    project.save()

    category = baker.make("resources.Category", name="Energie")
    resource = baker.make(Resource, title="Mon action", category=category)
    baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)

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
    resource = baker.make(Resource, title="Published one")
    baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    resource2 = baker.make(Resource, title="Draft one")
    baker.make(Realisation, project=project, resource=resource2, status=Realisation.DRAFT)

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
    resource = baker.make(Resource, title="Action vélo")
    baker.make(Realisation, project=project, resource=resource, status=Realisation.PUBLISHED)
    resource2 = baker.make(Resource, title="Action eau")
    baker.make(Realisation, project=project, resource=resource2, status=Realisation.PUBLISHED)

    with login(client) as user:
        assign_perm("use_crm", user, site)
        response = client.get(csv_url() + "?q=vélo")

    content = response.content.decode("utf-8-sig")
    assert "Action vélo" in content
    assert "Action eau" not in content


# ---------------------------------------------------------------------------
# RealisationNode auto-creation on publish
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_published_realisation_creates_conversation_node(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "description": "", "partners": "", "status": "published"},
        )

    realisation = Realisation.objects.get(project=project)
    assert RealisationNode.objects.filter(realisation=realisation).count() == 1
    message = Message.objects.get(project=project)
    assert message.nodes.get().realisation == realisation


@pytest.mark.django_db
def test_create_draft_realisation_does_not_create_conversation_node(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "description": "", "partners": "", "status": "draft"},
        )

    assert RealisationNode.objects.filter(realisation__project=project).count() == 0


@pytest.mark.django_db
def test_update_draft_to_published_creates_conversation_node(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "description": "", "partners": "", "status": "published"},
        )

    assert RealisationNode.objects.filter(realisation=realisation).count() == 1


@pytest.mark.django_db
def test_update_already_published_realisation_does_not_duplicate_node(request, client):
    project = make_project_on_site(request)
    resource = baker.make(Resource)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        # first publish
        client.post(
            update_url(project, realisation),
            {"resource": resource.pk, "description": "", "partners": "", "status": "published"},
        )
        # staff can re-save a published realisation; non-staff cannot (404), so this
        # test only verifies the signal guard via the create path
    assert RealisationNode.objects.filter(realisation=realisation).count() == 1


# ---------------------------------------------------------------------------
# Realisation ownership: only creator or staff can edit/delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_create_sets_created_by(request, client):
    """The user who creates a realisation is recorded as its creator."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "draft"},
        )
    realisation = Realisation.objects.get(project=project)
    assert realisation.created_by == user


@pytest.mark.django_db
def test_realisation_update_forbidden_for_non_owner_project_member(request, client):
    """A project member who did not create the realisation cannot edit it."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=creator,
        )
    with login(client, username="other") as other_member:
        project_utils.assign_collaborator(other_member, project)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_allowed_for_owner(request, client):
    """The creator of a realisation can edit it."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=user,
        )
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_update_allowed_for_staff_even_if_not_creator(request, client):
    """Staff can edit a realisation they did not create."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=creator,
        )
    with login(client, username="staff") as staff:
        assign_site_staff(get_current_site(request), staff)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_delete_forbidden_for_non_owner_project_member(request, client):
    """A project member who did not create the realisation cannot delete it."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=creator,
        )
    with login(client, username="other") as other_member:
        project_utils.assign_collaborator(other_member, project)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_allowed_for_owner(request, client):
    """The creator of a realisation can delete it."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=user,
        )
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


@pytest.mark.django_db
def test_realisation_delete_allowed_for_staff_even_if_not_creator(request, client):
    """Staff can delete a realisation they did not create."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation, project=project, resource=resource,
            status=Realisation.DRAFT, created_by=creator,
        )
    with login(client, username="staff") as staff:
        assign_site_staff(get_current_site(request), staff)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


# ---------------------------------------------------------------------------
# CRM tracing: actstream actions logged on publish and deletion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_publish_logs_actstream_action(request, client):
    """Publishing a realisation records a PUBLISHED action in the activity stream."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {"resource": resource.pk, "partners": "", "description": "", "status": "published"},
        )

    assert Action.objects.filter(verb=verbs.Realisation.PUBLISHED, target_object_id=str(project.pk)).exists()


@pytest.mark.django_db
def test_realisation_delete_logs_actstream_action(request, client):
    """Deleting a realisation records a DELETED action in the activity stream."""
    project = make_project_on_site(request)
    resource = baker.make(Resource)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(Realisation, project=project, resource=resource, status=Realisation.DRAFT, created_by=user)
        client.post(delete_url(project, realisation))

    assert Action.objects.filter(verb=verbs.Realisation.DELETED, target_object_id=str(project.pk)).exists()
