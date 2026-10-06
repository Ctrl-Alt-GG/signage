"""Checks a contributor would otherwise run by hand, kept in the test suite so CI needs
a single command: Django system checks, migrations, content lint and generated files."""

import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

ROOT = Path(settings.BASE_DIR)

pytestmark = pytest.mark.django_db


def test_django_system_checks():
    call_command("check", fail_level="WARNING", databases=["default"])


def test_migrations_are_current():
    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=0)
    except SystemExit as error:
        pytest.fail(f"model changes without a migration (exit {error.code})")


def test_content_docs_are_in_sync():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "render_content.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_openapi_schema_is_committed(tmp_path):
    generated = tmp_path / "openapi.yaml"
    call_command("spectacular", "--file", str(generated), "--validate")
    committed = (ROOT / "docs" / "openapi.yaml").read_text(encoding="utf-8")
    assert generated.read_text(encoding="utf-8") == committed, (
        "docs/openapi.yaml is stale: run manage.py spectacular --file docs/openapi.yaml"
    )
