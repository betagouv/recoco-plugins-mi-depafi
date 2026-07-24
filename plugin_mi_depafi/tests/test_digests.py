from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from model_bakery import baker
from notifications.models import Notification

from recoco.utils import assign_site_staff

from .. import verbs as plugin_verbs
from ..conftest import make_project_on_site
from ..digests import send_new_realisations_digest
from ..models import Realisation
from ..signals import notify_staff_on_project_validated, realisation_published
from .conftest import make_resource

# ---------------------------------------------------------------------------
# Digests: send_new_realisations_digest
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_send_new_realisations_digest_returns_zero_with_no_notifications(request):
    site = get_current_site(request)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    result = send_new_realisations_digest(site, staff_member, dry_run=False)

    assert result == 0


@pytest.mark.django_db
def test_send_new_realisations_digest_sends_email_and_marks_sent(request):
    site = get_current_site(request)
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    publisher = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    realisation_published.send(
        sender=Realisation, realisation=realisation, published_by=publisher
    )

    with patch("plugin_mi_depafi.digests.send_email") as mock_send:
        result = send_new_realisations_digest(site, staff_member, dry_run=False)

    assert result == 1
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args[0][0] == "mi_depafi_new_realisations_digest"
    assert call_args[1]["params"]["realisation_count"] == 1
    assert not Notification.objects.filter(
        recipient=staff_member,
        verb=plugin_verbs.Realisation.PUBLISHED,
        emailed=False,
    ).exists()


@pytest.mark.django_db
def test_send_new_realisations_digest_dry_run_does_not_send_or_mark(request):
    site = get_current_site(request)
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    publisher = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    realisation_published.send(
        sender=Realisation, realisation=realisation, published_by=publisher
    )

    with patch("plugin_mi_depafi.digests.send_email") as mock_send:
        result = send_new_realisations_digest(site, staff_member, dry_run=True)

    assert result == 1
    mock_send.assert_not_called()
    assert Notification.objects.filter(
        recipient=staff_member,
        verb=plugin_verbs.Realisation.PUBLISHED,
        emailed=False,
    ).exists()


@pytest.mark.django_db
def test_send_new_realisations_digest_projects_context_includes_realisation_count(
    request,
):
    site = get_current_site(request)
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    publisher = baker.make(User)
    moderator = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    realisation_published.send(
        sender=Realisation, realisation=realisation, published_by=publisher
    )
    notify_staff_on_project_validated(
        sender=None, site=site, moderator=moderator, project=project
    )

    captured = {}

    def fake_send_email(template_name, recipients, params, **kwargs):
        captured.update(params)

    with patch("plugin_mi_depafi.digests.send_email", side_effect=fake_send_email):
        send_new_realisations_digest(site, staff_member, dry_run=False)

    assert len(captured.get("projects", [])) == 1
    assert captured["projects"][0]["name"] == project.name
    assert captured["projects"][0]["realisation_count"] == 2
