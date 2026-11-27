from django.apps import AppConfig


class PluginMiDepafiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugin_mi_depafi"
    verbose_name = "Mi-depafi - Réalisations"

    def ready(self):
        from actstream import registry
        from watson import search as watson

        from recoco.apps.conversations.serializers import GenericRelatedField
        from recoco.apps.projects import signals as project_signals
        from recoco.utils import strip_accents
        from recoco.apps.plugins.search import PluginSearchAdapter

        from .models import Realisation
        from .serializers import ActivityRealisationSerializer

        from . import signals as plugin_signals  # noqa: F401 - registers signal receivers

        self._register_digest_email_template()

        project_signals.project_validated.connect(
            plugin_signals.notify_staff_on_project_validated
        )

        registry.register(Realisation)

        GenericRelatedField.model_serializer_mapping[Realisation] = (
            ActivityRealisationSerializer
        )

        class RealisationSearchAdapter(PluginSearchAdapter):
            fields = (
                "location",
                "description",
                "resource__title",
                "resource__category",
                "project__name",
                "project__commune__name",
                "project__commune__insee",
                "project__commune__postal",
                "project__commune__department__name",
                "project__commune__department__code",
                "project__commune__department__region__name",
            )

            def prepare_content(self, content):
                content = super().prepare_content(content)
                return strip_accents(content)

        watson.register(Realisation, adapter_cls=RealisationSearchAdapter)

    def _register_digest_email_template(self):
        """Add the digest template to EmailTemplate's choices so it appears in the admin.

        `EmailTemplate.name` is a core model field restricted to
        `communication.constants.TPL_CHOICES`. Plugins have no hook to extend it, so we
        patch the choices in place at startup.
        """
        from recoco.apps.communication import constants as communication_constants
        from recoco.apps.communication.models import EmailTemplate

        from .digests import TEMPLATE_NAME

        choice = (TEMPLATE_NAME, "MI - Résumé des nouvelles réalisations")
        if choice in communication_constants.TPL_CHOICES:
            return

        communication_constants.TPL_CHOICES += (choice,)
        EmailTemplate._meta.get_field(
            "name"
        ).choices = communication_constants.TPL_CHOICES


PLUGIN_NAME = PluginMiDepafiConfig.name
