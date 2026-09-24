import pytest

from recoco.utils import login

from ..models import DepafiProject
from .conftest import make_published_realisation, map_api_url

# ---------------------------------------------------------------------------
# Perimeter filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_map_api_without_perimeter_returns_all_realisations(request, client):
    sgami = make_published_realisation(request, perimeter=DepafiProject.Perimeter.SGAMI)
    no_perimeter = make_published_realisation(request)

    with login(client):
        response = client.get(map_api_url())

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert sgami.pk in ids
    assert no_perimeter.pk in ids


@pytest.mark.django_db
def test_map_api_filters_by_perimeter(request, client):
    sgami = make_published_realisation(request, perimeter=DepafiProject.Perimeter.SGAMI)
    other_perimeter = make_published_realisation(
        request, perimeter=DepafiProject.Perimeter.POLICE_NATIONALE
    )
    no_perimeter = make_published_realisation(request)

    with login(client):
        response = client.get(
            map_api_url(), {"perimeter": DepafiProject.Perimeter.SGAMI}
        )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert sgami.pk in ids
    assert other_perimeter.pk not in ids
    assert no_perimeter.pk not in ids
