from django.db import migrations, models
import django.db.models.deletion
import plugin_mi_depafi.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("projects", "0001_initial_squashed_0005_delete_resource"),
        ("resources", "0001_initial_squashed_0006_alter_resource_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="Realisation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("partners", models.CharField(blank=True, max_length=500, verbose_name="Partenaires")),
                ("description", models.TextField(blank=True, verbose_name="Description de l'action")),
                ("status", models.CharField(choices=[("draft", "Brouillon"), ("published", "Publié")], default="draft", max_length=20, verbose_name="État")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="realisations",
                        to="projects.project",
                        verbose_name="Projet",
                    ),
                ),
                (
                    "resource",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="realisations",
                        to="resources.resource",
                        verbose_name="Action réalisée",
                    ),
                ),
            ],
            options={
                "verbose_name": "Réalisation",
                "verbose_name_plural": "Réalisations",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="RealisationPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to=plugin_mi_depafi.models._realisation_photo_upload_path)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                (
                    "realisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="photos",
                        to="plugin_mi_depafi.realisation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Photo",
                "verbose_name_plural": "Photos",
                "ordering": ["order", "pk"],
            },
        ),
    ]
