import re
import uuid

from django.core.files.storage import default_storage
from django.db import migrations, transaction

# Legacy paths look like
# plugins/mi_depafi/realisations/{realisation_id}/photos/{filename}
# Randomized paths look like
# plugins/mi_depafi/realisations/{realisation_id}/{uuid}/photos/{filename}
LEGACY_PATH_RE = re.compile(r"^plugins/mi_depafi/realisations/\d+/(photos|documents)/")


def randomize_realisation_file_paths(apps, schema_editor):
    """Move existing realisation photos and documents to a path containing a
    random token, so their location can no longer be guessed from the
    sequential realisation id and the original filename alone (drafts are
    not served through a permission-checked view).
    """
    errors = []
    count_missing_files = 0
    count_success_files = 0
    count_already_moved = 0

    for model_name, field_name, kind in (
        ("RealisationPhoto", "image", "photos"),
        ("RealisationDocument", "file", "documents"),
    ):
        model = apps.get_model("plugin_mi_depafi", model_name)
        for obj in model.objects.exclude(**{f"{field_name}": ""}):
            old_path = getattr(obj, field_name).name
            if not old_path or not default_storage.exists(old_path):
                count_missing_files += 1
                continue

            if not LEGACY_PATH_RE.match(old_path):
                count_already_moved += 1
                continue

            filename = old_path.rsplit("/", 1)[-1]
            new_path = (
                f"plugins/mi_depafi/realisations/{obj.realisation_id}/"
                f"{uuid.uuid4().hex}/{kind}/{filename}"
            )

            try:
                with transaction.atomic():
                    with default_storage.open(old_path) as old_file:
                        default_storage.save(new_path, old_file)
                    getattr(obj, field_name).name = new_path
                    obj.save(update_fields=[field_name])
                default_storage.delete(old_path)
                count_success_files += 1
            except Exception as e:
                errors.append(e)

    print(f"\nmissing files: {count_missing_files}")
    print(f"already moved files: {count_already_moved}")
    print(f"successfully moved files: {count_success_files}")
    print(errors)


class Migration(migrations.Migration):
    atomic = False  # resiliency to data loss since migration moves files

    dependencies = [
        ("plugin_mi_depafi", "0010_depafiproject"),
    ]

    operations = [
        migrations.RunPython(
            randomize_realisation_file_paths,
            # Forward-only in practice: files already moved to their random
            # location still resolve with the randomized upload paths, so a
            # reverse is a no-op rather than a hard failure.
            reverse_code=migrations.RunPython.noop,
        ),
    ]
