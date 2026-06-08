from django.dispatch import Signal, receiver

from recoco.apps.conversations.models import Message

# Sent when a Realisation transitions to PUBLISHED.
# Provides: realisation (Realisation instance), published_by (User instance)
realisation_published = Signal()


@receiver(realisation_published)
def on_realisation_published(sender, realisation, published_by, **kwargs):
    from .models import RealisationNode

    message = Message.objects.create(
        project=realisation.project,
        posted_by=published_by,
    )
    RealisationNode.objects.create(
        message=message,
        position=0,
        realisation=realisation,
    )
