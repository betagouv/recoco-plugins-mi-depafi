import pytest
from model_bakery import baker

from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects.models import Project

from ..models import DepafiProject

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
