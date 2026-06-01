# Q/A Workflow

Status: Draft.

## Purpose

Define how we will turn the draft module documents into detailed, implementation-ready requirements.

## Process

For each module:

1. Review the module purpose, scope, and assumptions.
2. Answer the module Q/A backlog.
3. Add decisions directly to the module file.
4. Mark unresolved items as open decisions with owners.
5. Update dependencies affected by those decisions.
6. Mark the module as Reviewed.
7. When all critical decisions are complete, mark the module Requirements-ready.

## Decision Record Format

Each module should include decision records in this shape:

```md
## Decisions

### DEC-001: Short decision title

Status: Proposed | Accepted | Rejected | Superseded.
Date: YYYY-MM-DD.
Owner: Name or role.

Decision:
Rationale:
Impacted modules:
Follow-ups:
```

## Q/A Session Format

For each module, we should work through:

- Business objective.
- Users and roles.
- Step-by-step workflows.
- Data required.
- Rules and limits.
- Approvals.
- Exceptions.
- Notifications.
- Reports.
- Compliance and audit evidence.
- Launch scope versus later scope.

## Completion Criteria

A module is requirements-ready when:

- Primary users and workflows are clear.
- Data objects and lifecycle states are defined.
- Business rules are explicit.
- Compliance controls are mapped.
- Admin operations are defined.
- Reports and audit events are listed.
- External integrations are identified.
- Open decisions are either resolved or explicitly deferred.

## Historical First Q/A Session

This initial Q/A session has been completed and recorded in [Operating Model and Compliance](01_operating_model_compliance.md). It remains here as a record of the starting workflow.

Initial questions:

1. What exact FINMA authorization, licence, SRO affiliation, or supervisory regime applies to Garanta Finanzgruppe AG?
2. Will Garanta Finanzgruppe AG hold client money, or will funds always be handled by a regulated partner?
3. Which jurisdictions are allowed for investors and borrowers at launch?
4. Which investor classes are allowed at launch?
5. What legal instrument will investors receive for their loan exposure?
