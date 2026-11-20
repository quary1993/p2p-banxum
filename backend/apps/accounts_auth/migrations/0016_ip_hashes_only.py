# IP of Webby-Soft SRL. Audit S4-1 (Q06): authentication records keep only a keyed IP hash.
"""Each raw IP column gets a hash column, the stored addresses are hashed, and the raw columns
are removed. The hash is the one of ``platform_core.services.ip_privacy`` (account purpose), so
old and new rows compare with each other and with the sign-in history."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.db import migrations, models

# (model, raw column, hash column)
COLUMNS = (
    ("registrationtermsacceptance", "ip_address", "ip_hash"),
    ("emaillogintoken", "requested_ip", "requested_ip_hash"),
    ("emaillogintoken", "consumed_ip", "consumed_ip_hash"),
    ("phoneverificationchallenge", "requested_ip", "requested_ip_hash"),
    ("phoneverificationchallenge", "confirmed_ip", "confirmed_ip_hash"),
    ("sensitiveactioncode", "requested_ip", "requested_ip_hash"),
    ("sensitiveactioncode", "consumed_ip", "consumed_ip_hash"),
    ("loginchallenge", "requested_ip", "requested_ip_hash"),
    ("passwordresettoken", "requested_ip", "requested_ip_hash"),
)


def _keyed_hash(address: str) -> str:
    pepper = hashlib.sha256(f"{settings.SECRET_KEY}:accounts-sign-in-ip:v1".encode()).digest()
    return hmac.new(pepper, address.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_stored_addresses(apps: Any, schema_editor: Any) -> None:
    for model_name, raw, hashed in COLUMNS:
        model = apps.get_model("accounts_auth", model_name)
        rows = model.objects.exclude(**{f"{raw}__isnull": True}).values_list("pk", raw)
        for pk, address in rows.iterator():
            if address:
                model.objects.filter(pk=pk).update(**{hashed: _keyed_hash(str(address))})


class Migration(migrations.Migration):
    dependencies = [
        ("accounts_auth", "0015_declarations_and_roles_18_10"),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=model_name,
                name=hashed,
                field=models.CharField(blank=True, max_length=64),
            )
            for model_name, _raw, hashed in COLUMNS
        ],
        # The raw addresses cannot come back: there is no reverse data step.
        migrations.RunPython(hash_stored_addresses, migrations.RunPython.noop),
        *[
            migrations.RemoveField(model_name=model_name, name=raw)
            for model_name, raw, _h in COLUMNS
        ],
    ]
