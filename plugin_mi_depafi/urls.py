from django.urls import path

from .views import RealisationCreateView, RealisationListView

app_name = "plugin_mi_depafi"

urlpatterns = [
    path(
        "project/<int:project_id>/realisations/",
        RealisationListView.as_view(),
        name="realisation-list",
    ),
    path(
        "project/<int:project_id>/realisations/creer/",
        RealisationCreateView.as_view(),
        name="realisation-create",
    ),
]
