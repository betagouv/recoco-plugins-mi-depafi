import pytest


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
