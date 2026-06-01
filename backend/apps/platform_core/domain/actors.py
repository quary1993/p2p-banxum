from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ActorRef:
    actor_type: str
    actor_id: str

    @classmethod
    def system(cls) -> ActorRef:
        return cls(actor_type="system", actor_id="system")

    @property
    def is_internal(self) -> bool:
        return self.actor_type in {"admin", "superadmin", "system", "tech"}
