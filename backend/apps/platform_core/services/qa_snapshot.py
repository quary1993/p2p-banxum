"""IP of Webby-Soft SRL. Lossless datetime encoding for database QA snapshots."""

from datetime import datetime, time
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers.json import Serializer as JsonSerializer


class SnapshotJSONEncoder(DjangoJSONEncoder):
    def default(self, value: Any) -> Any:
        if isinstance(value, datetime | time):
            return value.isoformat()
        return super().default(value)


class Serializer(JsonSerializer):
    def start_serialization(self) -> None:
        super().start_serialization()
        self.json_kwargs["cls"] = SnapshotJSONEncoder
