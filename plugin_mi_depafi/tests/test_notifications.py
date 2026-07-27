import pytest
from actstream.models import Action
from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from model_bakery import baker
from notifications.models import Notification

from recoco import verbs as recoco_verbs
from recoco.apps.projects import utils as project_utils
from recoco.utils import assign_site_staff, login

from .. import verbs as plugin_verbs
from ..conftest import make_project_on_site
from ..models import Realisation
from ..signals import notify_staff_on_project_validated, realisation_published
from .conftest import create_url, delete_url, make_resource

# ---------------------------------------------------------------------------
# CRM tracing: actstream actions logged on publish and deletion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_realisation_publish_logs_actstream_action(request, client):
    """Publishing a realisation records a PUBLISHED action in the activity stream."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "partners": "",
                "description": "",
                "status": "published",
            },
        )

    assert Action.objects.filter(
        verb=plugin_verbs.Realisation.PUBLISHED, target_object_id=str(project.pk)
    ).exists()


@pytest.mark.django_db
def test_realisation_delete_logs_actstream_action(request, client):
    """Deleting a realisation records a DELETED action in the activity stream."""
    project = make_project_on_site(request)
    resource = make_resource(request)
    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        realisation = baker.make(
            Realisation,
            project=project,
            resource=resource,
            status=Realisation.DRAFT,
            created_by=user,
        )
        client.post(delete_url(project, realisation))

    assert Action.objects.filter(
        verb=plugin_verbs.Realisation.DELETED, target_object_id=str(project.pk)
    ).exists()


@pytest.mark.django_db
def test_notify_staff_on_realisation_published(request):
    site = get_current_site(request)
    project = make_project_on_site(request)
    resource = make_resource(request)
    realisation = baker.make(
        Realisation, project=project, resource=resource, status=Realisation.PUBLISHED
    )
    publisher = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)
    non_staff = baker.make(User)

    realisation_published.send(
        sender=Realisation, realisation=realisation, published_by=publisher
    )

    assert Notification.objects.filter(
        recipient=staff_member, verb=plugin_verbs.Realisation.PUBLISHED
    ).exists()
    assert not Notification.objects.filter(
        recipient=non_staff, verb=plugin_verbs.Realisation.PUBLISHED
    ).exists()


@pytest.mark.django_db
def test_notify_staff_on_project_validated(request):
    site = get_current_site(request)
    project = make_project_on_site(request)
    moderator = baker.make(User)
    staff_member = baker.make(User)
    assign_site_staff(site, staff_member)

    notify_staff_on_project_validated(
        sender=None, site=site, moderator=moderator, project=project
    )

    assert Notification.objects.filter(
        recipient=staff_member,
        verb=recoco_verbs.Project.VALIDATED_BY,
        action_object_object_id=project.pk,
    ).exists()
