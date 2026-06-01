from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_no_pending_model_migrations() -> None:
    call_command("makemigrations", check=True, dry_run=True, stdout=StringIO())
