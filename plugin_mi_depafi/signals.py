import waffle
from actstream import action
from django.dispatch import Signal, receiver

from recoco.apps.conversations.models import Message

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
