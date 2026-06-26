import pluggy
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from recoco.apps.projects.models import Project

from .models import Realisation

hookimpl = pluggy.HookimplMarker("recoco")


class MiDepafiPlugin:
    urls_module = "plugin_mi_depafi.urls"
    rest_urls_module = "plugin_mi_depafi.rest_urls"
    vite_entries = {
        "realisationsMap": "js/realisationsMap.js",
        "realisationListCrm": "js/realisationListCrm.js",
        "realisationInviteOnTaskDone": "js/RealisationInviteOnTaskDone.js",
    }

    @hookimpl
    def project_tab_entries(self):
        return ("plugin_mi_depafi:realisation-list", "Réalisations")

    @hookimpl
    def crm_navigation_tabs(self, request):
        return {
            "label": "Réalisations",
            "url_name": "plugin_mi_depafi:crm-realisation-list",
            "tab_key": "plugin_mi_depafi",
            "index": 15,
        }

    @hookimpl
    def crm_project_list_annotations(self, request):
        return {"realisations_count": Count("realisations", distinct=True)}

    @hookimpl
    def crm_project_list_extra_serializer_fields(self, request):
        return ["realisations_count"]

    @hookimpl
    def crm_project_list_columns(self, request):
        return {
            "header": "Réalisations",
            "cell_html": '<td x-text="project.realisations_count ?? \'—\'" :class="project.realisations_count === 0 ? \'text-danger\' : \'\'"></td>',
            "col_class": "col--medium",
        }

    @hookimpl
    def conversation_message_node_html(self, request, project):
        return mark_safe(render_to_string(
            "plugin_mi_depafi/fragments/node_realisationnode.html",
            {},
            request=request,
        ))

    @hookimpl
    def conversation_extra_html(self, request, project):
        return mark_safe(render_to_string(
            "plugin_mi_depafi/fragments/realisation_invite_on_task_done.html",
            {},
            request=request,
        ))

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
        return mark_safe(render_to_string(
            "plugin_mi_depafi/fragments/resource_sidebar_realisations.html",
            {
                "resource": resource,
                "realisations": realisations,
                "count": count,
                "user_projects": user_projects,
            },
            request=request,
        ))
