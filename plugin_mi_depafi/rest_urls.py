from django.urls import path

from .rest_api import CrmRealisationListAPIView, RealisationsForMapAPIView

urlpatterns = [
    path(
        "realisations/map/",
        RealisationsForMapAPIView.as_view(),
        name="plugin-mi-depafi-realisations-map",
    ),
    path(
        "crm/realisations/",
        CrmRealisationListAPIView.as_view(),
        name="plugin-mi-depafi-crm-realisations",
    ),
]
