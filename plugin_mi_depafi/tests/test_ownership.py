import pytest
from django.contrib.sites.shortcuts import get_current_site
from model_bakery import baker

from recoco.apps.projects import utils as project_utils
from recoco.utils import assign_site_staff, login

from ..conftest import make_project_on_site
from ..models import Realisation
from .conftest import create_url, delete_url, make_resource, update_url

# ---------------------------------------------------------------------------
# Staff access to published realisations / draft author restriction
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_update_staff_can_access_published(request, client):
    """Site staff can open the update form for a published realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200
    assert response.context["realisation"] == realisation


@pytest.mark.django_db
def test_realisation_update_staff_can_save_published(request, client):
    """Site staff can POST changes to a published realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "partners": "Staff édité",
                "description": "",
                "status": "published",
            },
        )
    realisation.refresh_from_db()
    assert realisation.partners == "Staff édité"


@pytest.mark.django_db
def test_realisation_update_non_staff_member_cannot_access_published(request, client):
    """A regular project member cannot update a published realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_staff_can_access_published(request, client):
    """Site staff can access the delete confirmation for a published realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request, title="Action publiée")
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 200
    assert b"Action publi" in response.content


@pytest.mark.django_db
def test_realisation_delete_staff_can_delete_published(request, client):
    """Site staff can delete a published realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


@pytest.mark.django_db
def test_realisation_update_draft_requires_project_membership(request, client):
    """A logged-in user who is not a project member or staff cannot update a draft."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client):
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_draft_accessible_for_project_member(request, client):
    """A project member can update a draft realisation."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_update_draft_accessible_for_staff(request, client):
    """Site staff can update a draft realisation even without project membership."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client) as user:
        assign_site_staff(get_current_site(request), user)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Realisation ownership: only creator or staff can edit/delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_create_sets_created_by(request, client):
    """The user who creates a realisation is recorded as its creator."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
            },
        )
    realisation = Realisation.objects.get(project=project)
    assert realisation.created_by == user


@pytest.mark.django_db
def test_realisation_update_forbidden_for_non_owner_project_member(request, client):
    """A project member who did not create the realisation cannot edit it."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=creator,
        )
    with login(client, username="other") as other_member:
        project_utils.assign_collaborator(other_member, project)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_allowed_for_owner(request, client):
    """The creator of a realisation can edit it."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_update_allowed_for_staff_even_if_not_creator(request, client):
    """Staff can edit a realisation they did not create."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=creator,
        )
    with login(client, username="staff") as staff:
        assign_site_staff(get_current_site(request), staff)
        response = client.get(update_url(project, realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_delete_forbidden_for_non_owner_project_member(request, client):
    """A project member who did not create the realisation cannot delete it."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=creator,
        )
    with login(client, username="other") as other_member:
        project_utils.assign_collaborator(other_member, project)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_allowed_for_owner(request, client):
    """The creator of a realisation can delete it."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()


@pytest.mark.django_db
def test_realisation_delete_allowed_for_staff_even_if_not_creator(request, client):
    """Staff can delete a realisation they did not create."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client, username="creator") as creator:
        project_utils.assign_collaborator(creator, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=creator,
        )
    with login(client, username="staff") as staff:
        assign_site_staff(get_current_site(request), staff)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert not Realisation.objects.filter(pk=realisation.pk).exists()
