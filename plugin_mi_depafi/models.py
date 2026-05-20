from django.db import models
from django.urls import reverse
from markdownx.utils import markdownify


class Realisation(models.Model):
    """A Realisation is a Resource that has been realized in real life, by a given Project"""

    DRAFT = "draft"
    PUBLISHED = "published"

    STATUS_CHOICES = [
        (DRAFT, "Brouillon"),
        (PUBLISHED, "Publié"),
    ]

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="realisations",
        verbose_name="Projet",
    )
    resource = models.ForeignKey(
        "resources.Resource",
        on_delete=models.CASCADE,
        related_name="realisations",
        verbose_name="Action réalisée",
    )
    partners = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Partenaires",
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description de l'action",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        verbose_name="État",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réalisation"
        verbose_name_plural = "Réalisations"
        ordering = ["-created_at"]

    def get_absolute_url(self):
        return reverse("plugin_mi_depafi:realisation-detail", kwargs={"pk": self.pk})

    @property
    def description_rendered(self):
        # FIXME Security: does it need a sanity postprocessing?
        return markdownify(self.description)

    def __str__(self):
        return str(self.resource)


def _realisation_photo_upload_path(instance, filename):
    return f"plugins/mi_depafi/realisations/{instance.realisation_id}/photos/{filename}"


class RealisationPhoto(models.Model):
    realisation = models.ForeignKey(
        Realisation,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to=_realisation_photo_upload_path)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Photo"
        verbose_name_plural = "Photos"
        ordering = ["order", "pk"]
