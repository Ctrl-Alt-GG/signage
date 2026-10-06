from django.db import migrations

INTEGRATIONS = ("projectile", "bracket", "streams")


def seed(apps, schema_editor):
    Integration = apps.get_model("signage", "Integration")
    Screen = apps.get_model("signage", "Screen")
    for kind in INTEGRATIONS:
        Integration.objects.get_or_create(kind=kind)
    Screen.objects.get_or_create(slug="main", defaults={"name": "Main hall"})


def unseed(apps, schema_editor):
    apps.get_model("signage", "Integration").objects.filter(
        kind__in=INTEGRATIONS, base_url=""
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("signage", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
