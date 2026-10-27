import pytest
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.management import call_command
from model_bakery import baker
from multisite.models import Alias
from waffle.testutils import override_switch

from recoco.apps.home import models as home_models
from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects.models import Project

from .apps import PLUGIN_NAME
from .models import DepafiProject

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def enable_mi_futur_switch():
    with override_switch("MI_futur", active=True):
        yield


@pytest.fixture(autouse=True)
def enable_plugin():
    """Set thread-local enabled_plugins so PluginURLResolver allows reverse()."""
    set_enabled_plugins([PLUGIN_NAME])
    yield
    set_enabled_plugins([])


@pytest.fixture(autouse=True)
def multisite_alias(db):
    """Ensure the example.com site has a canonical multisite Alias."""
    site = Site.objects.filter(domain="example.com").first()
    if site:
        Alias.objects.get_or_create(site=site, domain="example.com", is_canonical=True)


@pytest.fixture
def current_site():
    return Site.objects.filter(domain="example.com").first()


def make_project_on_site(request):
    site = get_current_site(request)
    home_models.SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={"enabled_plugins": [PLUGIN_NAME]},
    )
    project = baker.make(Project)
    project.project_sites.create(site=site, status="READY", is_origin=True)
    return project


def set_project_perimeter(project, perimeter):
    """Store `perimeter` on the project's DepafiProject profile for the current site.

    The profile is normally auto-created by the plugin signal on Project
    creation; it is created here if missing (legacy projects).
    """
    profile, _ = DepafiProject.objects.get_or_create(
        project=project, site=Site.objects.get_current()
    )
    profile.perimeter = perimeter
    profile.save()
    return profile


@pytest.fixture(scope="session", autouse=True)
def migrate_plugin_tables(django_db_setup, django_db_blocker):
    """Create the plugin tables in the plugin_mi_depafi schema, like in production.

    The schema is on every connection's search_path, so tests need nothing else.
    migrate_plugins is safe to re-run, which keeps --reuse-db working.
    """
    with django_db_blocker.unblock():
        call_command("migrate_plugins", PLUGIN_NAME, verbosity=0)
