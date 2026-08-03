import logging

from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from recoco import utils, verbs as recoco_verbs
from recoco.apps.communication.api import send_email
from recoco.apps.communication.helpers import normalize_user_name
from recoco.apps.projects import models as project_models

from . import verbs as plugin_verbs

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

    unseen_realisation_counts_by_project = {}
    for notif in realisation_notifications:
        realisation = notif.action_object
        if realisation is None:
            continue
        unseen_realisation_counts_by_project[realisation.project_id] = (
            unseen_realisation_counts_by_project.get(realisation.project_id, 0) + 1
        )

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

        project_realisations_url = utils.build_absolute_url(
            reverse("plugin_mi_depafi:realisation-list", args=[project.id]),
            auto_login_user=user,
        )

        projects.append(
            {
                "name": project.name,
                "url": project_realisations_url,
                "realisation_count": unseen_realisation_counts_by_project.get(
                    project.id, 0
                ),
            }
        )

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
