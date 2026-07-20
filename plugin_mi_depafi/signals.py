import waffle
from actstream import action
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.dispatch import Signal, receiver
from notifications.signals import notify

from recoco import verbs as recoco_verbs
from recoco.apps.conversations.models import Message
from recoco.utils import get_group_for_site

from . import verbs
from .models import RealisationNode

# Sent when a Realisation transitions to PUBLISHED.
# Provides: realisation (Realisation instance), published_by (User instance)
realisation_published = Signal()


@receiver(realisation_published)
def on_realisation_published(sender, realisation, published_by, **kwargs):
    if waffle.switch_is_active('MI_futur'):
        message = Message.objects.create(
            project=realisation.project,
            posted_by=published_by,
        )
        RealisationNode.objects.create(
            message=message,
            position=0,
            realisation=realisation,
        )


@receiver(realisation_published)
def log_realisation_published(sender, realisation, published_by, **kwargs):
    if waffle.switch_is_active('MI_futur'):
        action.send(
            published_by,
            verb=verbs.Realisation.PUBLISHED,
            action_object=realisation,
            target=realisation.project,
            public=False,
        )


@receiver(realisation_published)
def notify_staff_on_realisation_published(sender, realisation, published_by, **kwargs):
    site = Site.objects.get_current()
    staff_group = get_group_for_site("staff", site)
    staff_users = User.objects.filter(
        groups=staff_group, is_active=True, profile__sites=site
    )
    if staff_users.exists():
        notify.send(
            sender=published_by,
            recipient=list(staff_users),
            verb=verbs.Realisation.PUBLISHED,
            action_object=realisation,
            target=realisation.project,
            public=False,
        )


def notify_staff_on_project_validated(sender, site, moderator, project, **kwargs):
    # NOTE: recoco core already notifies regional advisors (verb=Project.AVAILABLE) on
    # project validation. If staff members are also advisors on this site, they will
    # receive both this notification and the advisor one; consider deduplicating.
    staff_group = get_group_for_site("staff", site)
    staff_users = User.objects.filter(
        groups=staff_group, is_active=True, profile__sites=site
    )
    if staff_users.exists():
        notify.send(
            sender=moderator,
            recipient=list(staff_users),
            verb=recoco_verbs.Project.VALIDATED_BY,
            action_object=project,
            target=project,
            public=False,
        )
