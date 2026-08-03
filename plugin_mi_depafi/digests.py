import logging

from django.urls import reverse

from recoco import utils
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

    projects_by_id = project_models.Project.objects.in_bulk(
        unseen_realisation_counts_by_project.keys()
    )

    projects = []
    for project_id, count in unseen_realisation_counts_by_project.items():
        project = projects_by_id.get(project_id)
        if project is None:
            continue

        project_realisations_url = utils.build_absolute_url(
            reverse("plugin_mi_depafi:realisation-list", args=[project.id]),
            auto_login_user=user,
        )

        projects.append(
            {
                "name": project.name,
                "url": project_realisations_url,
                "realisation_count": count,
            }
        )

    context = {
        "realisation_count": realisation_count,
        "projects": projects,
    }

    send_email(
        TEMPLATE_NAME,
        {"name": normalize_user_name(user), "email": user.email},
        params=context,
        dry_run=dry_run,
    )

    if dry_run:
        logger.info(
            f"[DRY RUN] Would have sent new realisations digest "
            f"({realisation_count} realisations, {len(projects)} projects) to <{user}>."
        )
    else:
        realisation_notifications.mark_as_sent()

    return realisation_count
