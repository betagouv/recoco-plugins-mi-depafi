import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plugin_mi_depafi", "0009_realisationdocument"),
        ("projects", "0126_alter_document_the_file"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepafiProject",
            fields=[
                (
                    "project",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        related_name="depafi",
                        serialize=False,
                        to="projects.project",
                        verbose_name="Projet",
                    ),
                ),
                (
                    "lakaa_import_id",
                    models.CharField(
                        blank=True,
                        max_length=100,
                        null=True,
                        unique=True,
                        verbose_name="Identifiant d'import Lakaa",
                    ),
                ),
                (
                    "perimeter",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("gendarmerie_nationale", "Gendarmerie nationale"),
                            ("police_nationale", "Police nationale"),
                            ("securite_civile", "Sécurité Civile"),
                            ("sgami", "SGAMI"),
                            ("ate", "ATE"),
                            ("operateur", "Opérateur"),
                            ("administration_centrale", "Administration Centrale"),
                        ],
                        max_length=32,
                        verbose_name="Périmètre",
                    ),
                ),
            ],
            options={
                "verbose_name": "Dossier MI-DEPAFI",
            },
        ),
    ]
