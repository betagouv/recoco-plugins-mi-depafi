from django.urls import path

from .rest_api import RealisationsForMapAPIView

urlpatterns = [
    path(
        "realisations/map/",
        RealisationsForMapAPIView.as_view(),
        name="plugin-mi-depafi-realisations-map",
    ),
]
