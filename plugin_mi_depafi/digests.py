import logging

from django.contrib.contenttypes.models import ContentType

from recoco import verbs as recoco_verbs
from recoco.apps.communication.api import send_email
from recoco.apps.communication.helpers import normalize_user_name
from recoco.apps.projects import models as project_models

from . import verbs as plugin_verbs
from .models import Realisation

logger = logging.getLogger("main")

TEMPLATE_NAME = "mi_depafi_new_realisations_digest"


def send_new_realisations_digest(site, user, dry_run=False):
    realisation_notifications = (
        user.notifications(manager="on_site")
        .unsent()
        .filter(verb=plugin_verbs.Realisation.PUBLISHED)
    )
    if not realisation_notifications.exists():
        return 0

    realisation_count = realisation_notifications.count()

    project_ct = ContentType.objects.get_for_model(project_models.Project)
    project_notifications = (
        user.notifications(manager="on_site")
        .unsent()
        .filter(
            verb=recoco_verbs.Project.VALIDATED_BY,
            action_object_content_type=project_ct,
        )
    )

    projects = []
    seen_project_ids = set()
    for notif in project_notifications:
        project = notif.action_object
        if project is None or project.id in seen_project_ids:
            continue
        seen_project_ids.add(project.id)
        projects.append({
            "name": project.name,
            "realisation_count": Realisation.objects.filter(
                project=project, status=Realisation.PUBLISHED
            ).count(),
        })

    context = {
        "realisation_count": realisation_count,
        "projects": projects,
    }

    if not dry_run:
        send_email(
            TEMPLATE_NAME,
            {"name": normalize_user_name(user), "email": user.email},
            params=context,
        )
        realisation_notifications.mark_as_sent()
        project_notifications.mark_as_sent()
    else:
        logger.info(
            f"[DRY RUN] Would have sent new realisations digest "
            f"({realisation_count} realisations, {len(projects)} projects) to <{user}>."
        )

    return realisation_count
