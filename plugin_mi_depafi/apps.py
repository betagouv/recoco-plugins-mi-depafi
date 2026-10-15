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
            fields = (
                "project__name",
                "project_tags_as_list",
                "project__commune__name",
                "project__commune__department__name",
                "project__commune__department__code",
                "project__commune__department__region__name",
                "project__commune__department__region__code",
                "project__commune__insee",
                "project__commune__postal",
                "project__owner__profile__organization__name",
                "resource__title",
                "resource__subtitle",
                "resource__summary",
                "resource__content",
                "resource__tags",
                "resource__category__name",
                "partners",
                "description",
            )

            def project_tags_as_list(self, obj):
                return list(obj.project.tags.names())

            def get_title(self, obj):
                return str(obj.resource)

            def get_description(self, obj):
                return obj.description

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
