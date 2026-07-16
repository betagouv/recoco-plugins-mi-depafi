import waffle
from actstream import action
from django.dispatch import Signal, receiver

from recoco.apps.conversations.models import Message

from . import verbs
from .models import RealisationNode

# Sent when a Realisation transitions to PUBLISHED.
# Provides: realisation (Realisation instance), published_by (User instance)
realisation_published = Signal()

# Sent when a Realisation is deleted.
# Provides: realisation (Realisation instance), deleted_by (User instance)
realisation_deleted = Signal()


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
            public=True,
        )


@receiver(realisation_deleted)
def log_realisation_deleted(sender, realisation, deleted_by, **kwargs):
    if waffle.switch_is_active('MI_futur'):
        action.send(
            deleted_by,
            verb=verbs.Realisation.DELETED,
            target=realisation.project,
            public=False,
        )
