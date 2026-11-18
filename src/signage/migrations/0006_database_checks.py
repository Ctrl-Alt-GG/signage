"""The invariants that the forms and the import check, kept by the database as well, so that a
bulk update or a script can't store what no screen can show. Adding them checks the rows that
are there: a row that breaks one stops the migration, which names the constraint, instead of
being changed without a word. The days of phases and schedule rows are limited to what the
YAML allows, 0 to 7, and a new event ends a day after it starts until the import sets it."""

import django.core.validators
import django.db.models.expressions
from django.conf import settings
from django.db import migrations, models

import signage.models


class Migration(migrations.Migration):
    dependencies = [
        ("signage", "0005_event_origin_and_upstream_limits"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="ends_at",
            field=models.DateTimeField(default=signage.models.a_day_from_now),
        ),
        migrations.AlterField(
            model_name="phase",
            name="day_offset",
            field=models.SmallIntegerField(
                default=0,
                help_text="0 on the event's first day, 1 after midnight.",
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(7),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="scheduleentry",
            name="day_offset",
            field=models.SmallIntegerField(
                default=0,
                validators=[
                    django.core.validators.MinValueValidator(0),
                    django.core.validators.MaxValueValidator(7),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="announcement",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ends_at__isnull", True),
                    ("ends_at__gt", models.F("starts_at")),
                    _connector="OR",
                ),
                name="signage_announcement_ends_after_start",
                violation_error_message="The announcement must end after it starts.",
            ),
        ),
        migrations.AddConstraint(
            model_name="displaysettings",
            constraint=models.CheckConstraint(
                condition=models.Q(("stage_height__gte", 160), ("stage_width__gte", 160)),
                name="signage_display_stage_size",
                violation_error_message="The stage needs a size.",
            ),
        ),
        migrations.AddConstraint(
            model_name="displaysettings",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("safe_height__gte", 80),
                    (
                        "safe_height__lte",
                        django.db.models.expressions.CombinedExpression(
                            models.F("stage_height"), "-", models.F("safe_y")
                        ),
                    ),
                    ("safe_width__gte", 80),
                    (
                        "safe_width__lte",
                        django.db.models.expressions.CombinedExpression(
                            models.F("stage_width"), "-", models.F("safe_x")
                        ),
                    ),
                ),
                name="signage_display_safe_area_on_stage",
                violation_error_message="The safe area has to be on the stage.",
            ),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.CheckConstraint(
                condition=models.Q(("ends_at__gt", models.F("starts_at"))),
                name="signage_event_ends_after_start",
                violation_error_message="The event must end after it starts.",
            ),
        ),
        migrations.AddConstraint(
            model_name="integration",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("connect_timeout__gte", 0.1),
                    (
                        "connect_timeout__lte",
                        django.db.models.expressions.CombinedExpression(
                            models.Value(10), "-", models.F("read_timeout")
                        ),
                    ),
                    ("read_timeout__gte", 0.1),
                ),
                name="signage_integration_upstream_time",
                violation_error_message="Connecting and reading may take 10 seconds together at most.",
            ),
        ),
        migrations.AddConstraint(
            model_name="integration",
            constraint=models.CheckConstraint(
                condition=models.Q(("cache_seconds__gte", 1), ("cache_seconds__lte", 600)),
                name="signage_integration_cache_seconds",
                violation_error_message="Answers are kept for 1 to 600 seconds.",
            ),
        ),
        migrations.AddConstraint(
            model_name="phase",
            constraint=models.CheckConstraint(
                condition=models.Q(("day_offset__gte", 0), ("day_offset__lte", 7)),
                name="signage_phase_day_offset",
                violation_error_message="A day from 0 to 7.",
            ),
        ),
        migrations.AddConstraint(
            model_name="scheduleentry",
            constraint=models.CheckConstraint(
                condition=models.Q(("day_offset__gte", 0), ("day_offset__lte", 7)),
                name="signage_schedule_day_offset",
                violation_error_message="A day from 0 to 7.",
            ),
        ),
        migrations.AddConstraint(
            model_name="screen",
            constraint=models.CheckConstraint(
                condition=models.Q(("refresh_seconds__gte", 5), ("refresh_seconds__lte", 600)),
                name="signage_screen_refresh",
                violation_error_message="A screen asks for news every 5 to 600 seconds.",
            ),
        ),
        migrations.AddConstraint(
            model_name="slide",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("duration_seconds__gte", 5),
                    ("duration_seconds__lte", 120),
                    ("priority__gte", 0),
                    ("priority__lte", 100),
                ),
                name="signage_slide_timing",
                violation_error_message="A slide shows for 5 to 120 seconds, with a priority from 0 to 100.",
            ),
        ),
        migrations.AddConstraint(
            model_name="slide",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("valid_from__isnull", True),
                    ("valid_until__isnull", True),
                    ("valid_until__gt", models.F("valid_from")),
                    _connector="OR",
                ),
                name="signage_slide_valid_window",
                violation_error_message="A slide has to be valid until after it is valid from.",
            ),
        ),
        migrations.AddConstraint(
            model_name="slideitem",
            constraint=models.CheckConstraint(
                condition=models.Q(("column__gte", 1), ("column__lte", 2)),
                name="signage_slideitem_column",
                violation_error_message="Column 1 or 2.",
            ),
        ),
    ]
