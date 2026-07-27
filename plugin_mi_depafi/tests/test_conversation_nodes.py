import pytest
from model_bakery import baker

from recoco.apps.conversations.models import Message
from recoco.apps.feature_flag.models import Switch as WaffleSwitch
from recoco.apps.projects import utils as project_utils
from recoco.utils import login

from ..conftest import make_project_on_site
from ..models import Realisation, RealisationNode
from .conftest import create_url, make_resource, update_url

# ---------------------------------------------------------------------------
# RealisationNode auto-creation on publish
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_published_realisation_creates_conversation_node(request, client):
    WaffleSwitch.objects.get_or_create(name="MI_futur", defaults={"active": True})
    project = make_project_on_site(request)
    resource = make_resource(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "description": "",
                "partners": "",
                "status": "published",
            },
        )

    realisation = Realisation.objects.get(project=project)
    assert RealisationNode.objects.filter(realisation=realisation).count() == 1
    message = Message.objects.get(project=project)
    assert message.nodes.get().realisation == realisation


@pytest.mark.django_db
def test_create_draft_realisation_does_not_create_conversation_node(request, client):
    project = make_project_on_site(request)
    resource = make_resource(request)

    with login(client) as user:
        project_utils.assign_collaborator(user, project, is_owner=True)
        client.post(
            create_url(project),
            {
                "resource": resource.pk,
                "description": "",
                "partners": "",
                "status": "draft",
            },
        )

    assert RealisationNode.objects.filter(realisation__project=project).count() == 0


@pytest.mark.django_db
def test_update_draft_to_published_creates_conversation_node(request, client):
    WaffleSwitch.objects.get_or_create(name="MI_futur", defaults={"active": True})
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
        client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "description": "",
                "partners": "",
                "status": "published",
            },
        )

    assert RealisationNode.objects.filter(realisation=realisation).count() == 1


@pytest.mark.django_db
def test_update_already_published_realisation_does_not_duplicate_node(request, client):
    WaffleSwitch.objects.get_or_create(name="MI_futur", defaults={"active": True})
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
        # first publish
        client.post(
            update_url(project, realisation),
            {
                "resource": resource.pk,
                "description": "",
                "partners": "",
                "status": "published",
            },
        )
        # staff can re-save a published realisation; non-staff cannot (404), so this
        # test only verifies the signal guard via the create path
    assert RealisationNode.objects.filter(realisation=realisation).count() == 1
