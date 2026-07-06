import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView, View

from recoco.apps.geomatics.models import Region
from recoco.apps.geomatics.serializers import RegionSerializer
from recoco.apps.projects.models import Project
from recoco.apps.projects.views.detail import ProjectDetailBaseView
from recoco.apps.resources.models import Resource
from recoco.utils import has_perm_or_403, is_staff_for_site

from .forms import RealisationForm
from .models import Realisation, RealisationLike, RealisationPhoto
from .signals import realisation_published


class RealisationListView(ProjectDetailBaseView):
    # FIXME needs permissions handling
    template_name = "plugin_mi_depafi/realisation_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = (
            Realisation.objects.filter(project=self.object)
            .select_related("resource")
            .prefetch_related("photos")
            .annotate(
                like_count=Count("likes"),
                user_liked=Exists(
                    RealisationLike.objects.filter(
                        realisation=OuterRef("pk"),
                        user=self.request.user,
                    )
                ),
            )
        )
        context["draft_realisations"] = base_qs.filter(status=Realisation.DRAFT)
        context["published_realisations"] = base_qs.filter(status=Realisation.PUBLISHED)
        context["realisations"] = base_qs
        return context


class RealisationCreateView(ProjectDetailBaseView):
    # FIXME needs permissions handling
    template_name = "plugin_mi_depafi/realisation_create_update.html"
    http_method_names = ["get", "head", "options", "post"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        initial = {}
        if resource_id := self.request.GET.get("resource_id"):
            initial["resource"] = resource_id
        context.setdefault("form", RealisationForm(initial=initial))
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = RealisationForm(request.POST)

        if form.is_valid():
            realisation = form.save(commit=False)
            realisation.project = self.object
            realisation.created_by = request.user
            new_status = request.POST.get("status", Realisation.DRAFT)
            realisation.status = new_status
            realisation.save()

            for order, image in enumerate(request.FILES.getlist("photos")):
                RealisationPhoto.objects.create(
                    realisation=realisation, image=image, order=order
                )

            if new_status == Realisation.PUBLISHED:
                realisation_published.send(
                    sender=Realisation,
                    realisation=realisation,
                    published_by=request.user,
                )

            return redirect(
                reverse(
                    "plugin_mi_depafi:realisation-list",
                    kwargs={"project_id": self.object.pk},
                )
            )

        context = self.get_context_data(form=form)
        return self.render_to_response(context)


class RealisationUpdateView(ProjectDetailBaseView):
    template_name = "plugin_mi_depafi/realisation_create_update.html"
    http_method_names = ["get", "head", "options", "post"]

    def _get_realisation(self):
        filters = {"pk": self.kwargs["pk"], "project": self.object}
        if not is_staff_for_site(self.request.user, self.request.site):
            filters["status"] = Realisation.DRAFT
        realisation = get_object_or_404(Realisation, **filters)
        if not is_staff_for_site(self.request.user, self.request.site):
            if realisation.created_by_id != self.request.user.pk:
                raise PermissionDenied
        return realisation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        realisation = self._get_realisation()
        context.setdefault("form", RealisationForm(instance=realisation))
        context["realisation"] = realisation
        context["page_title"] = "Modifier la réalisation"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        realisation = self._get_realisation()
        form = RealisationForm(request.POST, instance=realisation)

        if form.is_valid():
            old_status = realisation.status
            realisation = form.save(commit=False)
            new_status = request.POST.get("status", Realisation.DRAFT)
            realisation.status = new_status
            realisation.save()

            delete_ids = request.POST.getlist("delete_photos")
            if delete_ids:
                RealisationPhoto.objects.filter(
                    realisation=realisation, pk__in=delete_ids
                ).delete()

            existing_count = realisation.photos.count()
            for order, image in enumerate(request.FILES.getlist("photos"), start=existing_count):
                RealisationPhoto.objects.create(
                    realisation=realisation, image=image, order=order
                )

            if old_status != Realisation.PUBLISHED and new_status == Realisation.PUBLISHED:
                realisation_published.send(
                    sender=Realisation,
                    realisation=realisation,
                    published_by=request.user,
                )

            return redirect(
                reverse(
                    "plugin_mi_depafi:realisation-list",
                    kwargs={"project_id": self.object.pk},
                )
            )

        context = self.get_context_data(form=form)
        return self.render_to_response(context)


class RealisationDeleteView(ProjectDetailBaseView):
    http_method_names = ["get", "post"]

    def _get_realisation(self):
        filters = {"pk": self.kwargs["pk"], "project": self.object}
        if not is_staff_for_site(self.request.user, self.request.site):
            filters["status"] = Realisation.DRAFT
        realisation = get_object_or_404(Realisation, **filters)
        if not is_staff_for_site(self.request.user, self.request.site):
            if realisation.created_by_id != self.request.user.pk:
                raise PermissionDenied
        return realisation

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        return render(
            request,
            "plugin_mi_depafi/fragments/realisation_delete_confirm.html",
            {"realisation": self._get_realisation()},
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        self._get_realisation().delete()
        return redirect(
            reverse(
                "plugin_mi_depafi:realisation-list",
                kwargs={"project_id": self.object.pk},
            )
        )


class RealisationLikeToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        realisation = get_object_or_404(Realisation, pk=pk, status=Realisation.PUBLISHED)
        like, created = RealisationLike.objects.get_or_create(
            realisation=realisation, user=request.user
        )
        if not created:
            like.delete()
            user_liked = False
        else:
            user_liked = True
        return render(
            request,
            "plugin_mi_depafi/fragments/realisation_like_button.html",
            {
                "realisation": realisation,
                "user_liked": user_liked,
                "like_count": realisation.likes.count(),
            },
        )


class RealisationDetailView(LoginRequiredMixin, DetailView):
    # FIXME needs permissions handling
    model = Realisation
    template_name = "plugin_mi_depafi/realisation_detail.html"
    context_object_name = "realisation"


class RealisationPickProjectView(LoginRequiredMixin, View):
    def get(self, request, resource_id):
        resource = get_object_or_404(Resource, pk=resource_id)
        projects = (
            Project.on_site.filter(members=request.user)
            .select_related("commune")
            .order_by("name")
        )
        return render(
            request,
            "plugin_mi_depafi/fragments/realisation_project_picker.html",
            {"resource": resource, "projects": projects},
        )


class RealisationMapView(TemplateView):
    template_name = "plugin_mi_depafi/realisation_map.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        regions = Region.objects.prefetch_related("departments").order_by("name")
        ctx["regions"] = list(RegionSerializer(regions, many=True).data)
        return ctx


class CrmRealisationListView(LoginRequiredMixin, View):
    """CRM-side list of all Realisations across the site."""

    template_name = "plugin_mi_depafi/crm_realisation_list.html"

    def get(self, request):
        has_perm_or_403(request.user, "use_crm", request.site)
        return render(request, self.template_name)


class CrmRealisationCsvView(LoginRequiredMixin, View):
    def get(self, request):
        has_perm_or_403(request.user, "use_crm", request.site)

        qs = (
            Realisation.objects.filter(project__project_sites__site=request.site)
            .select_related("resource__category", "project__commune")
            .order_by("-created_at")
            .distinct()
        )

        if q := request.GET.get("q", "").strip():
            qs = qs.filter(resource__title__icontains=q)

        if statuses := request.GET.getlist("status"):
            qs = qs.filter(status__in=statuses)

        if departments := request.GET.getlist("departments"):
            qs = qs.filter(project__commune__department__code__in=departments)

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="realisations.csv"'
        response.write("﻿")  # BOM for Excel

        writer = csv.writer(response)
        writer.writerow(["Intitulé", "Catégorie", "Nom du site", "Localisation", "Date", "Statut"])

        status_labels = dict(Realisation.STATUS_CHOICES)
        for r in qs:
            commune = r.project.commune
            localisation = f"{commune.name} ({commune.postal})" if commune else ""
            writer.writerow([
                r.resource.title,
                r.resource.category.name if r.resource.category else "",
                r.project.name,
                localisation,
                r.created_at.strftime("%d/%m/%Y"),
                status_labels.get(r.status, r.status),
            ])

        return response



class RealisationsByResourceView(LoginRequiredMixin, ListView):
    template_name = "plugin_mi_depafi/realisations_by_resource.html"
    context_object_name = "realisations"
    paginate_by = 20

    def get_queryset(self):
        self.resource = get_object_or_404(Resource, pk=self.kwargs["resource_id"])
        return (
            Realisation.objects.filter(resource=self.resource, status=Realisation.PUBLISHED)
            .select_related("project__commune__department")
            .prefetch_related("photos")
            .annotate(like_count=Count("likes"))
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resource"] = self.resource
        return context
