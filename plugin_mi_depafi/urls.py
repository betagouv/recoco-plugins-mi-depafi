from django.urls import path

from .views import (
    RealisationCreateView,
    RealisationDeleteView,
    RealisationDetailView,
    RealisationLikeToggleView,
    RealisationListView,
    RealisationUpdateView,
    RealisationsByResourceView,
)

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
    path(
        "project/<int:project_id>/realisations/<int:pk>/modifier/",
        RealisationUpdateView.as_view(),
        name="realisation-update",
    ),
    path(
        "project/<int:project_id>/realisations/<int:pk>/supprimer/",
        RealisationDeleteView.as_view(),
        name="realisation-delete",
    ),
    path(
        "realisations/<int:pk>/aimer/",
        RealisationLikeToggleView.as_view(),
        name="realisation-like-toggle",
    ),
    path(
        "realisations/<int:pk>/",
        RealisationDetailView.as_view(),
        name="realisation-detail",
    ),
    path(
        "resources/<int:resource_id>/realisations/",
        RealisationsByResourceView.as_view(),
        name="realisations-by-resource",
    ),
]
