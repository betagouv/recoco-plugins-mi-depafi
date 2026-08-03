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
    # dry_run now flows all the way to send_email (so params/template resolution
    # are exercised for real) - only the actual Brevo HTTP call is skipped,
    # further down inside send_email itself.
    mock_send.assert_called_once()
    assert mock_send.call_args[1]["dry_run"] is True
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
    realisation_a = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    realisation_b = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    # A third, already-seen realisation on the same project: it must NOT be
    # counted, since its notification isn't part of this digest run.
    baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    publisher = baker.make(User)
    moderator = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    realisation_published.send(
        sender=Realisation, realisation=realisation_a, published_by=publisher
    )
    realisation_published.send(
        sender=Realisation, realisation=realisation_b, published_by=publisher
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


@pytest.mark.django_db
def test_send_new_realisations_digest_projects_populated_without_validated_by_notification(
    request,
):
    # notify_staff_on_project_validated is not wired to any signal in production
    # (see signals.py: "XXX Disabled ATM"), so Project.VALIDATED_BY notifications
    # are never created for real. The projects list must therefore be derived
    # from the realisation notifications themselves, not from that verb.
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

    captured = {}

    def fake_send_email(template_name, recipients, params, **kwargs):
        captured.update(params)

    with patch("plugin_mi_depafi.digests.send_email", side_effect=fake_send_email):
        result = send_new_realisations_digest(site, staff_member, dry_run=False)

    assert result == 1
    assert len(captured.get("projects", [])) == 1
    assert captured["projects"][0]["name"] == project.name
    assert captured["projects"][0]["realisation_count"] == 1
