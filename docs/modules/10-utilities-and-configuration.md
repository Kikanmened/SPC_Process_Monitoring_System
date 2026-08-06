# Module 10 — Utilities and Configuration

**Owning layers:** `config/`, `common/`, `observability/`
**Depends on:** nothing in this repository beyond `domain/`
**Depended on by:** all nine other modules
**Requirement coverage:** FR-CF01 – FR-CF05, FR-AU01 – FR-AU06, FR-D08 (unit registry), FR-RP02 (provenance); NFR-M04, NFR-SE03, NFR-SE04, NFR-SE05, NFR-SE07, NFR-CO01
**Delivered in:** Phase 7 (configuration, units, time, errors), Phase 11 (audit trail) · **Status:** Partial — Phase 7 plus audit/auth ports; full RBAC and SSO remain later

---

## Purpose

The foundation every other module stands on: typed configuration, the unit
registry, timezone-aware time, the error taxonomy, provenance capture,
structured logging, and — kept deliberately separate from logging — the audit
trail.

Two of these deserve their prominence. **Configuration is how process knowledge
changes without a code release**, which is the difference between a quality
engineer adjusting a rule set and a deployment. And **the audit trail is what
makes this a quality system component rather than a charting tool**; without it,
every number the platform produces is an assertion rather than evidence.

The module also owns a distinction that looks pedantic and is not. Operational
logs help an engineer debug and may be rotated away. Audit records prove what
the system did and who instructed it, are append-only, and their loss is an
audit finding. Same mechanism, incompatible requirements, separate sinks
([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §3.6).

## Responsibilities

- Parse layered configuration — `base/` plus environment overlay — **once**, at
  the application boundary, into immutable typed Pydantic models (FR-CF01).
- Treat an unknown configuration key as an error, never a silently ignored typo.
  A misspelled rule name means the intended rule never runs and nothing reports
  it (FR-CF02, US-D3).
- Compute and expose the effective configuration revision hash that travels with
  every analytical output (FR-RP02, BO-4).
- Maintain the unit registry and the declared conversions, so no module infers a
  unit (FR-D08).
- Provide the injected `Clock` and timezone-aware time utilities. No module reads
  the wall clock directly, and a naive datetime cannot be constructed (SEMI E148,
  Ruff `DTZ`).
- Define the typed exception hierarchy rooted at `SPCPlatformError`, with
  exceptions carrying actionable context rather than a message string.
- Provide structured logging with correlation IDs across pipeline, application,
  and API, and redaction at the logging boundary — no measured values,
  credentials, or customer device names in operational logs (NFR-SE07).
- Provide the append-only audit trail covering every event in
  [QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md) §2.2, with actor,
  timestamp, before and after state, and reason (FR-AU01 – FR-AU03).
- Retain superseded artefacts and export audit records to durable retention on
  schedule (FR-AU04, FR-AU05), and expose them for query (FR-AU06).
- Carry effective dates on specification limits and retain historical values
  (FR-CF03).
- Provide role-based authorisation checks: engineers view and disposition,
  quality engineers approve baselines, administrators change configuration
  (NFR-SE04).

**Not this module's work:** deciding what is auditable. That is defined by the
quality plan; this module makes recording it reliable. Audit events are explicit
calls, never a side effect of logging.

## Public interfaces

```python
def load_settings(profile: Profile) -> Settings:
    """Parse base plus overlay into an immutable typed object. Unknown keys raise."""


class Clock(Protocol):
    def now(self) -> datetime: ...          # always timezone-aware


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> AuditRecordId: ...
    def query(self, criteria: AuditQuery) -> Sequence[AuditRecord]: ...


def capture_provenance(settings: Settings, data_revision: DataRevision) -> Provenance:
    """Data, code, and configuration revisions, together, for attachment to any output."""
```

`AuditEvent` requires actor, timestamp, action, before state, after state, and
reason. There is no constructor that omits any of them, because "record it if
available" produces exactly the incomplete records an auditor asks about.

| Exception | Raised when |
|---|---|
| `ConfigurationError` | Unknown key, missing required value, or failed validation at load |
| `UnknownUnitError` | A unit outside the registry, or an undeclared conversion |
| `NaiveDatetimeError` | A timezone-naive datetime reaches a boundary |
| `AuditWriteError` | The audit record cannot be written — never swallowed; the action fails |
| `UnauthorisedActionError` | The actor's role does not permit the action |

`SPCPlatformError` is the root of every exception in the codebase, so a caller
can distinguish a platform failure from a library failure.

## Dependencies

| Depends on | For |
|---|---|
| `domain/` | Identifier types and the value objects audit records reference |
| Pydantic v2, pydantic-settings | Typed configuration and validation at construction |
| structlog | Structured logging with correlation IDs |
| PyYAML | Configuration files, read only at the boundary |

This module imports no other module. Anything else would create the one cycle
the dependency graph cannot tolerate.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Base configuration | `configs/base/` | Committed, reviewed, versioned |
| Environment overlay | `configs/environments/` | Local, staging, production profiles |
| Secrets | Runtime environment or secret store | Never from a file or an image (NFR-SE03) |
| Unit definitions | `configs/base/units.yaml` | Declared conversions only |
| Logging configuration | `configs/logging/` | Sinks, levels, redaction rules |
| Retention policy | `configs/base/` | Audit export schedule and destination |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `Settings` | Application boundary | Immutable, typed, with a revision hash |
| `Provenance` | Every module's results | Data, code, and configuration revision |
| Structured log stream | `logs/app/`, `logs/pipeline/` | JSON with correlation IDs, redacted |
| Audit records | `logs/audit/`, retention store | Append-only, ALCOA+ conformant (QA plan §2.1) |
| Authorisation decisions | Application use cases | Permit or refuse, recorded when consequential |

## Files to create

```
src/spc_platform/config/__init__.py
src/spc_platform/config/settings.py               layered load, unknown keys raise
src/spc_platform/config/profiles.py
src/spc_platform/config/revision.py               effective configuration hash
src/spc_platform/common/__init__.py
src/spc_platform/common/errors.py                 SPCPlatformError hierarchy
src/spc_platform/common/units.py                  registry and declared conversions
src/spc_platform/common/time.py                   Clock protocol, timezone-aware helpers
src/spc_platform/common/provenance.py
src/spc_platform/common/types.py                  shared NewType identifiers, FloatArray
src/spc_platform/observability/__init__.py
src/spc_platform/observability/logging.py         structlog configuration, redaction
src/spc_platform/observability/correlation.py
src/spc_platform/observability/audit/__init__.py
src/spc_platform/observability/audit/events.py    the event taxonomy from QA plan 2.2
src/spc_platform/observability/audit/sink.py
src/spc_platform/observability/audit/export.py    scheduled export to retention
src/spc_platform/application/ports/audit_sink.py
src/spc_platform/application/ports/authorisation.py
src/spc_platform/infrastructure/audit/append_only_store.py
configs/base/units.yaml
configs/base/retention.yaml
configs/logging/logging.yaml
configs/environments/local.yaml
configs/environments/staging.yaml
configs/environments/production.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | An unknown configuration key raises rather than being ignored (US-D3). A missing required value raises at load, not at first use. Configuration objects are immutable. |
| `unit/` | Importing `spc_platform` opens no connection, reads no file, and configures no logging — no module-level side effects (NFR-M04). |
| `unit/` | A naive datetime cannot cross a boundary. An undeclared unit conversion raises. |
| `contract/` | Every audit event type carries actor, timestamp, before, after, and reason. The append-only store rejects updates and deletes, verified against the real store and the fake. |
| `unit/` | Redaction: no measured value, credential, or device name appears in an operational log record, tested against a record containing all three (NFR-SE07). |
| `integration/` | Audit export to retention storage, and query of exported records. |
| `e2e/` | A consequential action produces exactly one complete audit record; a failed audit write fails the action rather than proceeding silently. |

## Documentation required

- `docs/api/configuration.md` — every configuration key, its type, default,
  validation, and which module consumes it.
- `docs/quality/audit-trail.md` — the event taxonomy, the ALCOA+ mapping, the
  retention policy, and how an auditor queries it.
- `configs/README.md` and the per-directory READMEs, kept current with the
  schema — configuration documentation drifts faster than any other kind.
- `docs/runbooks/configuration-change.md` — how a rule set or specification
  change is reviewed, approved, and rolled back.

## Future extension points

- **Site SSO/LDAP authentication** behind the authorisation port (FR-CF05).
- **Additional deployment profiles** — configuration only, no code change.
- **Configuration diff and history view** — the revision hash already exists;
  rendering the diff is a Module 9 addition.
- **External audit retention targets** — a WORM store or a records management
  system, behind the same export port.
- **Metrics export** — the observability package is the natural home if
  operational monitoring is ever added (Phase 14).

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[08-change-control-simulation.md](08-change-control-simulation.md) ·
[QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md) ·
[SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md)
