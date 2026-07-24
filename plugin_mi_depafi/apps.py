from django.apps import AppConfig


class PluginMiDepafiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugin_mi_depafi"
    verbose_name = "Mi-depafi - Réalisations"

    def ready(self):
        from actstream import registry
        from recoco.apps.conversations.serializers import NodePolymorphicSerializer
        from watson import search as watson

        from recoco.apps.projects import signals as project_signals

        from . import signals as plugin_signals  # noqa: F401 - registers signal receivers

        self._register_digest_email_template()

        project_signals.project_validated.connect(
            plugin_signals.notify_staff_on_project_validated
        )
        from .models import Realisation, RealisationNode
        from .serializers import RealisationNodeSerializer

        registry.register(Realisation)

        NodePolymorphicSerializer.model_serializer_mapping[RealisationNode] = (
            RealisationNodeSerializer
        )

        class RealisationSearchAdapter(watson.SearchAdapter):
            def get_title(self, obj):
                return str(obj.resource)

            def get_description(self, obj):
                return obj.description

            def get_content(self, obj):
                return f"{obj.project.name} {obj.partners} {obj.resource.title}"

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
