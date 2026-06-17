from django.apps import AppConfig


class PluginMiDepafiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugin_mi_depafi"
    verbose_name = "Mi-depafi - Réalisations"

    def ready(self):
        from actstream import registry
        from recoco.apps.conversations.serializers import NodePolymorphicSerializer
        from watson import search as watson

        from . import signals  # noqa: F401 — registers signal receivers
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
