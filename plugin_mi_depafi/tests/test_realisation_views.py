import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from recoco.apps.projects import utils as project_utils
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation, RealisationLike, RealisationPhoto
from .conftest import (
    create_url,
    delete_url,
    detail_url,
    like_toggle_url,
    list_url,
    make_resource,
    update_url,
)

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

    resource = make_resource(request)
    own = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    baker.make(
        Realisation,
        project=other_project,
        resource=resource,
        status=Realisation.PUBLISHED,
    )

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(list_url(project))

    assert response.status_code == 200
    realisations = list(response.context["published_realisations"])
    assert realisations == [own]


@pytest.mark.django_db
def test_realisation_list_separates_drafts_from_published(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    draft = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    published = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )

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
    resource = make_resource(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "Ministère",
                "description": "Une description",
                "status": "draft",
            },
        )

    assert response.status_code == 302
    realisation = Realisation.objects.get(project=project)
    assert realisation.status == Realisation.DRAFT
    assert realisation.partners == "Ministère"


@pytest.mark.django_db
def test_realisation_create_saves_published(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "published",
            },
        )

    assert response.status_code == 302
    assert Realisation.objects.get(project=project).status == Realisation.PUBLISHED


@pytest.mark.django_db
def test_realisation_create_assigns_project(request, client):
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

    assert Realisation.objects.filter(project=project).count() == 1


@pytest.mark.django_db
def test_realisation_create_redirects_to_list_on_success(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
            },
        )

    assert response.status_code == 302
    assert response["Location"] == list_url(project)


@pytest.mark.django_db
def test_realisation_create_saves_photos(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    image = SimpleUploadedFile(
        "photo.jpg", b"\xff\xd8\xff" + b"\x00" * 10, content_type="image/jpeg"
    )

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
                "photos": [image],
            },
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
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    response = client.get(update_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_update_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client):
        response = client.get(update_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_update_form_accessible_for_project_member(request, client):
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
    assert response.context["realisation"] == realisation


@pytest.mark.django_db
def test_realisation_update_returns_404_for_published(request, client):
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
def test_realisation_update_saves_changes(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    new_resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        client.post(
            update_url(project, realisation),
            {
                "resource": new_resource.pk,
                "partners": "Nouveau partenaire",
                "description": "",
                "status": "draft",
            },
        )
    realisation.refresh_from_db()
    assert realisation.partners == "Nouveau partenaire"
    assert realisation.resource == new_resource


@pytest.mark.django_db
def test_realisation_update_can_publish_draft(request, client):
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
        client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "published",
            },
        )
    realisation.refresh_from_db()
    assert realisation.status == Realisation.PUBLISHED


@pytest.mark.django_db
def test_realisation_update_deletes_marked_photos(request, client):
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
        photo = baker.make(RealisationPhoto, realisation=realisation)
        client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
                "delete_photos": [photo.pk],
            },
        )
    assert not RealisationPhoto.objects.filter(pk=photo.pk).exists()


@pytest.mark.django_db
def test_realisation_update_redirects_to_list_on_success(request, client):
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
        response = client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "draft",
            },
        )
    assert response.status_code == 302
    assert response["Location"] == list_url(project)


# ---------------------------------------------------------------------------
# Realisation delete (GET = confirm fragment, POST = delete)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_delete_get_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    response = client.get(delete_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_delete_get_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client):
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_get_shows_confirm_fragment(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request, title="Mon action")
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 200
    assert b"Mon action" in response.content


@pytest.mark.django_db
def test_realisation_delete_get_returns_404_for_published(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(delete_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_post_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    response = client.post(delete_url(project, realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_delete_post_forbidden_for_unprivileged_user(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client):
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 403


@pytest.mark.django_db
def test_realisation_delete_post_removes_draft(request, client):
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
def test_realisation_delete_post_returns_404_for_published(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(delete_url(project, realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_delete_post_redirects_to_list(request, client):
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
    assert response["Location"] == list_url(project)


# ---------------------------------------------------------------------------
# Realisation like toggle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_like_toggle_redirects_unauthenticated(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    response = client.post(like_toggle_url(realisation))
    assert response.status_code == 302


@pytest.mark.django_db
def test_realisation_like_toggle_creates_like(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 200
    assert RealisationLike.objects.filter(realisation=realisation, user=user).exists()


@pytest.mark.django_db
def test_realisation_like_toggle_removes_existing_like(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    with login(client) as user:
        baker.make(RealisationLike, realisation=realisation, user=user)
        client.post(like_toggle_url(realisation))
    assert not RealisationLike.objects.filter(
        realisation=realisation, user=user
    ).exists()


@pytest.mark.django_db
def test_realisation_like_toggle_returns_404_for_draft(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.DRAFT
    )
    with login(client):
        response = client.post(like_toggle_url(realisation))
    assert response.status_code == 404


@pytest.mark.django_db
def test_realisation_like_toggle_returns_button_fragment(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
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
    resource = make_resource(request)
    realisation = baker.make(Realisation, project=project, resource=resource)
    response = client.get(detail_url(realisation))
    assert response.status_code == 302
    assert "/login" in response["Location"] or "/accounts" in response["Location"]


@pytest.mark.django_db
def test_realisation_detail_accessible_for_any_logged_in_user(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert response.status_code == 200


@pytest.mark.django_db
def test_realisation_detail_shows_resource_title(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request, title="Mon action vélo")
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"Mon action v\xc3\xa9lo" in response.content


@pytest.mark.django_db
def test_realisation_detail_shows_partners(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation,
        project=project,
        resource=resource,
        partners="Fondation Jean-Moulin",
    )
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"Fondation Jean-Moulin" in response.content


@pytest.mark.django_db
def test_realisation_detail_shows_project_name(request, client):
    project = make_project_on_site(request)
    project.name = "ATE Doubs"
    project.save()
    resource = make_resource(request)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert b"ATE Doubs" in response.content


@pytest.mark.django_db
def test_realisation_detail_context_has_realisation(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(Realisation, project=project, resource=resource)
    with login(client):
        response = client.get(detail_url(realisation))
    assert response.context["realisation"] == realisation
