import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, TemplateView, View
from django_filters.views import FilterMixin, FilterView

from recoco.apps.geomatics.models import Region
from recoco.apps.geomatics.serializers import RegionSerializer
from recoco.apps.projects.models import Project
from recoco.apps.projects.views.detail import ProjectDetailBaseView
from recoco.apps.resources.models import Resource
from recoco.utils import has_perm, has_perm_or_403

from .filters import RealisationFilter
from .forms import DepafiProjectPerimeterForm, RealisationForm
from .models import (
    DepafiProject,
    Realisation,
    RealisationDocument,
    RealisationLike,
    RealisationPhoto,
)
from .signals import realisation_deleted, realisation_published


class RealisationWriteMixin:
    """Permissions for realisation write views (create, update, delete).

    Realisations are project content (photos, documents): whoever may manage
    the project documents may manage its realisations. This covers
    collaborators of accepted projects, advisors/observers, and site staff
    through guardian's staff bypass (see recoco.apps.home.models).
    """

    def check_permissions(self):
        has_perm_or_403(self.request.user, "projects.manage_documents", self.object)

    def _get_realisation(self):
        return get_object_or_404(Realisation, pk=self.kwargs["pk"], project=self.object)


class DepafiProjectPerimeterUpdateView(ProjectDetailBaseView):
    """Edit the plugin-specific perimeter of a project (DepafiProject profile)."""

    template_name = "plugin_mi_depafi/depafi_project_perimeter_update.html"
    http_method_names = ["get", "head", "options", "post"]

    def _get_profile(self):
        # The profile row is normally auto-created with the project (see
        # signals.create_depafi_project_on_project_created); get_or_create
        # covers projects predating the plugin activation.
        profile, _ = DepafiProject.objects.get_or_create(project=self.object)
        return profile

    def check_permissions(self):
        # Site staff automatically get project permissions, so no special case.
        has_perm_or_403(self.request.user, "projects.change_project", self.object)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault(
            "form", DepafiProjectPerimeterForm(instance=self._get_profile())
        )
        context["page_title"] = "Modifier le périmètre"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        profile = self._get_profile()
        form = DepafiProjectPerimeterForm(request.POST, instance=profile)

        if form.is_valid():
            form.save()
            return redirect(reverse("projects-project-detail", args=[self.object.pk]))

        context = self.get_context_data(form=form)
        return self.render_to_response(context)


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
            .order_by("-created_at")
        )
        context["draft_realisations"] = base_qs.filter(status=Realisation.DRAFT)
        context["published_realisations"] = base_qs.filter(status=Realisation.PUBLISHED)
        context["realisations"] = base_qs
        return context


class RealisationCreateView(RealisationWriteMixin, ProjectDetailBaseView):
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
        self.check_permissions()
        form = RealisationForm(request.POST)

        if form.is_valid():
            realisation = form.save(commit=False)
            realisation.project = self.object
            realisation.created_by = request.user
            new_status = form.cleaned_data.get("status") or Realisation.DRAFT
            realisation.status = new_status
            realisation.save()

            for order, image in enumerate(request.FILES.getlist("photos")):
                RealisationPhoto.objects.create(
                    realisation=realisation, image=image, order=order
                )

            for order, document in enumerate(request.FILES.getlist("documents")):
                RealisationDocument.objects.create(
                    realisation=realisation, file=document, order=order
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


class RealisationUpdateView(RealisationWriteMixin, ProjectDetailBaseView):
    template_name = "plugin_mi_depafi/realisation_create_update.html"
    http_method_names = ["get", "head", "options", "post"]

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
            new_status = form.cleaned_data.get("status") or Realisation.DRAFT
            realisation.status = new_status
            realisation.save()

            delete_ids = request.POST.getlist("delete_photos")
            if delete_ids:
                RealisationPhoto.objects.filter(
                    realisation=realisation, pk__in=delete_ids
                ).delete()

            existing_count = realisation.photos.count()
            for order, image in enumerate(
                request.FILES.getlist("photos"), start=existing_count
            ):
                RealisationPhoto.objects.create(
                    realisation=realisation, image=image, order=order
                )

            delete_doc_ids = request.POST.getlist("delete_documents")
            if delete_doc_ids:
                RealisationDocument.objects.filter(
                    realisation=realisation, pk__in=delete_doc_ids
                ).delete()

            existing_doc_count = realisation.documents.count()
            for order, document in enumerate(
                request.FILES.getlist("documents"), start=existing_doc_count
            ):
                RealisationDocument.objects.create(
                    realisation=realisation, file=document, order=order
                )

            if (
                old_status != Realisation.PUBLISHED
                and new_status == Realisation.PUBLISHED
            ):
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


class RealisationDeleteView(RealisationWriteMixin, ProjectDetailBaseView):
    http_method_names = ["get", "post"]

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
        realisation = self._get_realisation()
        realisation_deleted.send(
            sender=Realisation,
            realisation=realisation,
            deleted_by=request.user,
        )
        realisation.delete()
        return redirect(
            reverse(
                "plugin_mi_depafi:realisation-list",
                kwargs={"project_id": self.object.pk},
            )
        )


class RealisationLikeToggleView(LoginRequiredMixin, View):
    def post(self, request, pk):
        realisation = get_object_or_404(
            Realisation,
            pk=pk,
            status=Realisation.PUBLISHED,
            project__project_sites__site=request.site,
        )
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
    model = Realisation
    template_name = "plugin_mi_depafi/realisation_detail.html"
    context_object_name = "realisation"

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("resource", "project")
            .prefetch_related("photos", "documents")
            .filter(project__project_sites__site=self.request.site)
            .distinct()
        )

    def get_object(self, queryset=None):
        # Published realisations are visible to any logged-in user, but drafts
        # are work-in-progress: only their creator and those who may edit them
        # (see RealisationWriteMixin) can read them.
        realisation = super().get_object(queryset)
        user = self.request.user
        if (
            realisation.status != Realisation.PUBLISHED
            and realisation.created_by_id != user.pk
            and not has_perm(user, "projects.manage_documents", realisation.project)
        ):
            raise Http404
        return realisation

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["photos_data"] = [
            {"id": photo.pk, "url": photo.image.url}
            for photo in self.object.photos.all()
        ]
        return context


class RealisationPickProjectView(LoginRequiredMixin, View):
    def get(self, request, resource_id):
        resource = get_object_or_404(Resource.on_site, pk=resource_id)
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


class RealisationBrowseView(LoginRequiredMixin, TemplateView):
    """Browse realisations as a table or a map."""

    template_name = "plugin_mi_depafi/realisation_browse.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        regions = Region.objects.prefetch_related("departments").order_by("name")
        ctx["regions"] = list(RegionSerializer(regions, many=True).data)
        return ctx


class CrmRealisationMixin(LoginRequiredMixin):
    """Site scoping, CRM permission check and filtering shared by the CRM views."""

    filterset_class = RealisationFilter

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        has_perm_or_403(request.user, "use_crm", request.site)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Realisation.objects.filter(project__project_sites__site=self.request.site)
            .select_related("resource__category", "project__commune")
            .annotate(like_count=Count("likes", distinct=True))
            .order_by("-created_at")
            .distinct()
        )


class CrmRealisationListView(CrmRealisationMixin, FilterView):
    """CRM-side list of all Realisations across the site."""

    template_name = "plugin_mi_depafi/crm_realisation_list.html"
    context_object_name = "realisations"
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        selected_departments = []
        if self.filterset.is_valid():
            departments = self.filterset.form.cleaned_data.get("departments") or []
            selected_departments = [department.code for department in departments]
        context["selected_departments"] = selected_departments
        return context


class CrmRealisationCsvView(CrmRealisationMixin, FilterMixin, View):
    def get(self, request, *args, **kwargs):
        filterset = self.get_filterset(self.get_filterset_class())
        if filterset.is_bound and not filterset.is_valid() and self.get_strict():
            qs = filterset.queryset.none()
        else:
            qs = filterset.qs

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="realisations.csv"'
        response.write("﻿")  # BOM for Excel

        writer = csv.writer(response)
        writer.writerow(
            ["Intitulé", "Catégorie", "Nom du site", "Localisation", "Date", "Statut"]
        )

        status_labels = dict(Realisation.STATUS_CHOICES)
        for r in qs:
            commune = r.project.commune
            localisation = f"{commune.name} ({commune.postal})" if commune else ""
            writer.writerow(
                [
                    r.resource.title,
                    r.resource.category.name if r.resource.category else "",
                    r.project.name,
                    localisation,
                    r.created_at.strftime("%d/%m/%Y"),
                    status_labels.get(r.status, r.status),
                ]
            )

        return response


class RealisationsByResourceView(LoginRequiredMixin, ListView):
    template_name = "plugin_mi_depafi/realisations_by_resource.html"
    context_object_name = "realisations"
    paginate_by = 20

    def get_queryset(self):
        self.resource = get_object_or_404(
            Resource.on_site, pk=self.kwargs["resource_id"]
        )

        return (
            Realisation.objects.filter(
                resource=self.resource,
                status=Realisation.PUBLISHED,
                project__project_sites__site=self.request.site,
            )
            .select_related("project__commune__department")
            .prefetch_related("photos")
            .annotate(like_count=Count("likes"))
            .order_by("-created_at")
            .distinct()
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["resource"] = self.resource
        return context
