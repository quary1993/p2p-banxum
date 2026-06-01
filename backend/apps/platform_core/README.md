# platform_core

Purpose: shared primitives, configuration, dates, money/rate utilities, audit/event/outbox records, file foundations, and platform health checks.

Owned tables/models:

- `Currency`
- `PlatformSetting`
- `PlatformSettingVersion`
- `AuditEvent`
- `DomainEvent`
- `OutboxMessage`
- `StoredFile`

Public services/selectors:

- `record_audit_event`
- `record_domain_event`
- `enqueue_outbox_message`
- `mark_outbox_processed`
- `mark_outbox_failed`
- `seed_launch_currencies`
- `seed_default_platform_settings`
- `set_platform_setting`
- `register_stored_file`
- `can_access_stored_file`
- `enabled_currencies`
- `get_platform_setting_value`

API endpoints:

- `GET /api/v1/health/`

Background jobs: outbox records are ready for later Celery workers.

Domain events emitted/consumed: `DomainEvent` stores schema-versioned events with optional idempotency keys.

Ledger impact: none.

Permission rules: health endpoint is public and exposes no sensitive data.

Important invariants:

- Platform brand and legal operator are configuration values, not hardcoded UI literals.
- Europe/Zurich is the default business timezone.
- Money uses integer minor units and `Decimal` rates.
- Audit events, domain events, and setting versions are append-only through model/service APIs.
- Stored files are not accessible until scan status is `clean`.

Common tests and fixtures:

- `backend/apps/platform_core/tests/test_health_api.py`
- `backend/apps/platform_core/tests/test_money.py`
- `backend/apps/platform_core/tests/test_settings.py`
- `backend/apps/platform_core/tests/test_audit_events.py`
- `backend/apps/platform_core/tests/test_outbox.py`
- `backend/apps/platform_core/tests/test_files.py`

Non-goals/out-of-scope behavior:

- Object storage adapters and malware scanner execution are later Phase 1 work.
