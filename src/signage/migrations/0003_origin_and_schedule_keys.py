"""Admin ownership for every seeded table and a stable key for schedule rows.

Existing schedule rows get the key that content/schedule.yaml used for the same slot when
this migration was written (matched by time, day and Hungarian title), so a later
`loadcontent` updates them instead of creating duplicates; rows without a match get a key
derived from the slot. The keys are written out below rather than read from the content
directory, which keeps changing: the same database always migrates the same way.
"""

from django.db import migrations, models
from django.utils.text import slugify

ORIGIN_CHOICES = [("seed", "Seeded from YAML"), ("admin", "Edited in the admin")]

# content/schedule.yaml as it was then: (time, day_offset, Hungarian title) to key.
SCHEDULE_KEYS = {
    ("15:30", 0, "Kezdés egy kis építkezéssel"): "minecraft-start",
    ("17:00", 0, "Szedd össze a csapatod"): "tf2",
    ("18:40", 0, "Vacsoraszünet"): "dinner-break",
    ("19:00", 0, "Négyfős túlélés"): "l4d2",
    ("20:00", 0, "Indul a CS2-verseny"): "cs2-tournament",
    ("20:00", 0, "Közös vasútépítés a verseny alatt"): "openttd",
    ("22:00", 0, "CS2-díjátadó"): "cs2-awards",
    ("22:15", 0, "Egy kis hülyülés a díjátadó után"): "garrys-mod",
    ("23:00", 0, "Pörgős meccsek éjfél előtt"): "xonotic",
    ("23:40", 0, "Éjféli szünet"): "midnight-break",
    ("00:00", 1, "Éjféli horror"): "scp",
    ("01:40", 1, "Rövid szünet"): "break-0140",
    ("02:00", 1, "Hajnali gyárépítés"): "satisfactory",
    ("03:40", 1, "Rövid szünet"): "break-0340",
    ("04:00", 1, "Régi kedvenc hajnalban"): "css",
    ("05:40", 1, "Reggeliszünet"): "breakfast-break",
    ("06:00", 1, "Egy utolsó verseny napfelkeltekor"): "supertuxkart",
}


def fill_schedule_keys(apps, schema_editor):
    ScheduleEntry = apps.get_model("signage", "ScheduleEntry")
    from_yaml = SCHEDULE_KEYS
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
        # Without an index until it is unique below, which creates the indexes. On PostgreSQL
        # both would create the same pattern index, and the second would fail.
        migrations.AddField(
            model_name="scheduleentry",
            name="key",
            field=models.SlugField(blank=True, db_index=False, default="", max_length=60),
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
