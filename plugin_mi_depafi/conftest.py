import pytest
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from model_bakery import baker
from multisite.models import Alias
from recoco.apps.home import models as home_models
from recoco.apps.plugins.resolvers import set_enabled_plugins
from recoco.apps.projects.models import Project

PLUGIN_NAME = "plugin_mi_depafi"


@pytest.fixture(autouse=True)
def enable_plugin():
    set_enabled_plugins([PLUGIN_NAME])
    yield
    set_enabled_plugins([])


@pytest.fixture(autouse=True)
def multisite_alias(db):
    site = Site.objects.filter(domain="example.com").first()
    if site:
        Alias.objects.get_or_create(site=site, domain="example.com", is_canonical=True)


def make_project_on_site(request):
    site = get_current_site(request)
    home_models.SiteConfiguration.objects.get_or_create(
        site=site,
        defaults={"schema_name": "test_plugin_mi_depafi", "enabled_plugins": [PLUGIN_NAME]},
    )
    project = baker.make(Project)
    project.project_sites.create(site=site, status="READY", is_origin=True)
    return project


@pytest.fixture(scope="session", autouse=True)
def migrate_plugin_tables(django_db_setup, django_db_blocker):
    """Create plugin_mi_depafi tables directly in the public schema for testing.

    We bypass the migration system entirely (which would normally route these
    to a tenant schema) and use Django's schema editor directly so the tables
    are created in the default public schema accessible to all test connections.
    """
    with django_db_blocker.unblock():
        from django.apps import apps
        from django.db import connection

        app_config = apps.get_app_config("plugin_mi_depafi")
        with connection.schema_editor() as editor:
            for model in app_config.get_models():
                try:
                    editor.create_model(model)
                except Exception:
                    pass  # Table may already exist from a previous reuse-db run
