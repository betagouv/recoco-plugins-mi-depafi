from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, ListView, View

from recoco.apps.projects.views.detail import ProjectDetailBaseView
from recoco.apps.resources.models import Resource

from .forms import RealisationForm
from .models import Realisation, RealisationLike, RealisationPhoto


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
        context.setdefault("form", RealisationForm())
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = RealisationForm(request.POST)

        if form.is_valid():
            realisation = form.save(commit=False)
            realisation.project = self.object
            realisation.status = request.POST.get("status", Realisation.DRAFT)
            realisation.save()

            for order, image in enumerate(request.FILES.getlist("photos")):
                RealisationPhoto.objects.create(
                    realisation=realisation, image=image, order=order
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

    def _get_draft(self):
        return get_object_or_404(
            Realisation,
            pk=self.kwargs["pk"],
            project=self.object,
            status=Realisation.DRAFT,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        realisation = self._get_draft()
        context.setdefault("form", RealisationForm(instance=realisation))
        context["realisation"] = realisation
        context["page_title"] = "Modifier la réalisation"
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        realisation = self._get_draft()
        form = RealisationForm(request.POST, instance=realisation)

        if form.is_valid():
            realisation = form.save(commit=False)
            realisation.status = request.POST.get("status", Realisation.DRAFT)
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

    def _get_draft(self):
        return get_object_or_404(
            Realisation,
            pk=self.kwargs["pk"],
            project=self.object,
            status=Realisation.DRAFT,
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        return render(
            request,
            "plugin_mi_depafi/fragments/realisation_delete_confirm.html",
            {"realisation": self._get_draft()},
        )

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.check_permissions()
        self._get_draft().delete()
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
