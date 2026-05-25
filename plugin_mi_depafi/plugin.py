import pluggy
from django.db.models import Count
from django.template.loader import render_to_string

from recoco.apps.projects.models import Project

from .models import Realisation

hookimpl = pluggy.HookimplMarker("recoco")


class MiDepafiPlugin:
    urls_module = "plugin_mi_depafi.urls"

    @hookimpl
    def project_tab_entries(self):
        return ("plugin_mi_depafi:realisation-list", "Réalisations")

    @hookimpl
    def resource_sidebar_panels(self, resource, request):
        realisations = (
            Realisation.objects.filter(resource=resource, status=Realisation.PUBLISHED)
            .select_related("project__commune__department")
            .prefetch_related("photos")
            .annotate(like_count=Count("likes"))
            .order_by("-created_at")[:3]
        )
        count = Realisation.objects.filter(
            resource=resource, status=Realisation.PUBLISHED
        ).count()
        user_projects = []
        if request.user.is_authenticated:
            user_projects = list(
                Project.on_site.filter(members=request.user)
                .select_related("commune")
                .order_by("name")
            )
        return render_to_string(
            "plugin_mi_depafi/fragments/resource_sidebar_realisations.html",
            {
                "resource": resource,
                "realisations": realisations,
                "count": count,
                "user_projects": user_projects,
            },
            request=request,
        )
