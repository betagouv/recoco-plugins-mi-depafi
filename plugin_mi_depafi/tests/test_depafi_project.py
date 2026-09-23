import pytest
from model_bakery import baker

from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects import utils as project_utils
from recoco.apps.projects.models import Project
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import DepafiProject
from .conftest import perimeter_update_url

# ---------------------------------------------------------------------------
# DepafiProject auto-creation on Project creation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_depafi_project_created_when_project_created():
    """A Project creation in a tenant with the plugin enabled creates its profile."""
    project = baker.make(Project)
    assert DepafiProject.objects.filter(pk=project.pk).exists()


@pytest.mark.django_db
def test_depafi_project_not_duplicated_on_project_update():
    """Re-saving the Project does not create additional profile rows."""
    project = baker.make(Project)
    project.save()
    project.save()
    assert DepafiProject.objects.count() == 1


@pytest.mark.django_db
def test_no_depafi_project_when_plugin_disabled():
    """No profile row is created when the plugin is not enabled (other tenants)."""
    set_enabled_plugins([])
    try:
        project = baker.make(Project)
    finally:
        set_enabled_plugins(["plugin_mi_depafi"])
    assert not DepafiProject.objects.filter(pk=project.pk).exists()


# ---------------------------------------------------------------------------
# Perimeter editing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_perimeter_update_form_accessible_to_project_member(request, client):
    """A project member can open the perimeter edit form."""
    project = make_project_on_site(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.get(perimeter_update_url(project))

    assert response.status_code == 200
    assert response.context["form"] is not None


@pytest.mark.django_db
def test_perimeter_update_saves_perimeter(request, client):
    """A project member can set the perimeter; it is persisted on the profile."""
    project = make_project_on_site(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            perimeter_update_url(project),
            {"perimeter": DepafiProject.Perimeter.SGAMI},
        )

    assert response.status_code == 302
    profile = DepafiProject.objects.get(pk=project.pk)
    assert profile.perimeter == DepafiProject.Perimeter.SGAMI


@pytest.mark.django_db
def test_perimeter_update_creates_missing_profile(request, client):
    """Saving works even if the profile row did not exist yet (legacy projects)."""
    project = make_project_on_site(request)
    DepafiProject.objects.filter(pk=project.pk).delete()

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        response = client.post(
            perimeter_update_url(project),
            {"perimeter": DepafiProject.Perimeter.OPERATEUR},
        )

    assert response.status_code == 302
    profile = DepafiProject.objects.get(pk=project.pk)
    assert profile.perimeter == DepafiProject.Perimeter.OPERATEUR


@pytest.mark.django_db
def test_perimeter_update_forbidden_without_permission(request, client):
    """A logged-in user without `projects.change_project` on the project gets a 403."""
    project = make_project_on_site(request)

    with login(client):
        response = client.post(
            perimeter_update_url(project),
            {"perimeter": DepafiProject.Perimeter.SGAMI},
        )

    assert response.status_code == 403
    profile = DepafiProject.objects.get(pk=project.pk)
    assert profile.perimeter == ""
