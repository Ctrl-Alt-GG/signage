"""Admin ownership for every seeded table and a stable key for schedule rows.

Existing schedule rows get the key the current content/schedule.yaml uses for the same
slot (matched by time, day and Hungarian title), so a later `loadcontent` updates them
instead of creating duplicates; rows without a match get a key derived from the slot.
"""

from pathlib import Path

import yaml
from django.conf import settings
from django.db import migrations, models
from django.utils.text import slugify

ORIGIN_CHOICES = [("seed", "Seeded from YAML"), ("admin", "Edited in the admin")]


def _yaml_keys() -> dict[tuple[str, int, str], str]:
    path = Path(settings.SIGNAGE_CONTENT_DIR) / "schedule.yaml"
    if not path.exists():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    keys = {}
    for entry in document.get("entries", []):
        if entry.get("key"):
            slot = (entry["time"], int(entry.get("day_offset", 0)), entry["title"]["hu"])
            keys[slot] = entry["key"]
    return keys


def fill_schedule_keys(apps, schema_editor):
    ScheduleEntry = apps.get_model("signage", "ScheduleEntry")
    from_yaml = _yaml_keys()
    seen: set[str] = set()
    for entry in ScheduleEntry.objects.order_by("day_offset", "time", "order", "pk"):
        slot = (entry.time.strftime("%H:%M"), entry.day_offset, entry.title_hu)
        base = from_yaml.get(slot) or (
            slugify(f"d{entry.day_offset}-{entry.time:%H%M}-{entry.title_hu}")[:50]
            or f"entry-{entry.pk}"
        )
        key, suffix = base, 2
        while key in seen:
            key = f"{base}-{suffix}"
            suffix += 1
        seen.add(key)
        entry.key = key
        entry.save(update_fields=["key"])


class Migration(migrations.Migration):
    dependencies = [("signage", "0002_seed")]

    operations = [
        migrations.AddField(
            model_name="announcementtemplate",
            name="origin",
            field=models.CharField(choices=ORIGIN_CHOICES, default="seed", max_length=5),
        ),
        migrations.AddField(
            model_name="game",
            name="origin",
            field=models.CharField(choices=ORIGIN_CHOICES, default="seed", max_length=5),
        ),
        migrations.AddField(
            model_name="phase",
            name="origin",
            field=models.CharField(choices=ORIGIN_CHOICES, default="seed", max_length=5),
        ),
        migrations.AddField(
            model_name="scheduleentry",
            name="origin",
            field=models.CharField(choices=ORIGIN_CHOICES, default="seed", max_length=5),
        ),
        migrations.AddField(
            model_name="scheduleentry",
            name="key",
            field=models.SlugField(blank=True, default="", max_length=60),
            preserve_default=False,
        ),
        migrations.RunPython(fill_schedule_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="scheduleentry",
            name="key",
            field=models.SlugField(
                blank=True,
                help_text="Stable id the YAML import matches on. Left empty, one is generated.",
                max_length=60,
                unique=True,
            ),
        ),
    ]
