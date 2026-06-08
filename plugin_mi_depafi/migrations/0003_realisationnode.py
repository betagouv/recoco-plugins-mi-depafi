import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("conversations", "0001_initial"),
        ("plugin_mi_depafi", "0002_realisationlike"),
    ]

    operations = [
        migrations.CreateModel(
            name="RealisationNode",
            fields=[
                (
                    "node_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="conversations.node",
                    ),
                ),
                (
                    "realisation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="conversation_nodes",
                        to="plugin_mi_depafi.realisation",
                        verbose_name="Réalisation",
                    ),
                ),
            ],
            options={
                "verbose_name": "Nœud réalisation",
                "abstract": False,
                "base_manager_name": "objects",
            },
            bases=("conversations.node",),
        ),
    ]
