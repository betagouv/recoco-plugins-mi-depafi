from django.shortcuts import redirect
from django.urls import reverse

from recoco.apps.projects.views.detail import ProjectDetailBaseView

from .forms import RealisationForm
from .models import Realisation, RealisationPhoto


class RealisationListView(ProjectDetailBaseView):
    # FIXME needs permissions handling
    template_name = "plugin_mi_depafi/realisation_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["realisations"] = (
            Realisation.objects.filter(project=self.object).select_related("resource")
        )
        return context


class RealisationCreateView(ProjectDetailBaseView):
    # FIXME needs permissions handling
    template_name = "plugin_mi_depafi/realisation_create.html"
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
