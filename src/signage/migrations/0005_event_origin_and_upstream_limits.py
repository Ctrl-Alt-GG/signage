import django.core.validators
from django.db import migrations, models

import signage.models

MAX_UPSTREAM_SECONDS = 10


def mark_existing_event_as_edited(apps, schema_editor):
    """Until now the import filled in the event once and then left it alone, whatever an
    organizer had changed. An event that exists already keeps that: it counts as edited in
    the admin, so the next start does not replace anything an organizer set."""
    apps.get_model("signage", "Event").objects.update(origin="admin")


def cap_upstream_timeouts(apps, schema_editor):
    """Rows saved under the old limit of 30 seconds for each timeout."""
    Integration = apps.get_model("signage", "Integration")
    for row in Integration.objects.all():
        if row.connect_timeout + row.read_timeout > MAX_UPSTREAM_SECONDS:
            row.connect_timeout = min(row.connect_timeout, 2.0)
            row.read_timeout = min(row.read_timeout, MAX_UPSTREAM_SECONDS - row.connect_timeout)
            row.save(update_fields=["connect_timeout", "read_timeout"])


class Migration(migrations.Migration):
    dependencies = [
        ("signage", "0004_removed_seeds_and_validators"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="origin",
            field=models.CharField(
                choices=[("seed", "Seeded from YAML"), ("admin", "Edited in the admin")],
                default="seed",
                max_length=5,
            ),
        ),
        migrations.RunPython(mark_existing_event_as_edited, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="integration",
            name="auth_type",
            field=models.CharField(
                choices=[
                    ("none", "No authentication"),
                    ("basic", "HTTP Basic (username and password)"),
                    ("bearer", "Bearer token"),
                    ("header", "Custom header"),
                ],
                default="none",
                help_text=(
                    "Bracket needs none: a tournament with its Details page on is public. A "
                    "Bracket login token expires, after 12 hours by default."
                ),
                max_length=6,
            ),
        ),
        migrations.AlterField(
            model_name="integration",
            name="base_url",
            field=models.CharField(
                blank=True,
                help_text=(
                    "API root without a trailing slash: the system's public HTTPS address, for "
                    "example https://streams.ctrl-alt-gg.hu/api/v1. An address inside the Docker "
                    "network only works once the other system serves it there (see the README)."
                ),
                max_length=200,
                validators=[signage.models.validate_upstream_url],
            ),
        ),
        migrations.RunPython(cap_upstream_timeouts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="integration",
            name="connect_timeout",
            field=models.FloatField(
                default=2.0,
                validators=[
                    django.core.validators.MinValueValidator(0.1),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="integration",
            name="read_timeout",
            field=models.FloatField(
                default=4.0,
                validators=[
                    django.core.validators.MinValueValidator(0.1),
                    django.core.validators.MaxValueValidator(10),
                ],
            ),
        ),
    ]
