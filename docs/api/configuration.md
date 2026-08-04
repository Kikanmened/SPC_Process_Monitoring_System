# Configuration API

**Status:** Active — Phase 7
**Owner:** Module 10

Configuration is parsed once at the application boundary into immutable typed
models. No other module reads YAML or environment variables
([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §3.6).

## Loading settings

```python
from spc_platform.config import Profile, load_settings

settings = load_settings(Profile.LOCAL)
registry = settings.unit_registry()
revision = settings.config_revision
```

| Input | Path | Notes |
|---|---|---|
| Base platform settings | `configs/base/platform.yaml` | Name, timezone, SPC policy |
| Units | `configs/base/units.yaml` | Declared units and conversions only |
| Environment overlay | `configs/environments/{profile}.yaml` | Deep-merged; may be empty |

**Unknown keys raise** `ConfigurationError` (FR-CF02). Nested models use
`extra="forbid"`.

## Reference data

```python
from spc_platform.config import load_reference_data

reference = load_reference_data()  # defaults to data/reference/
```

| File | Contents |
|---|---|
| `parameters.yaml` | Parameter registry |
| `specification_limits.yaml` | Spec limits with effective dates |
| `tools.yaml` | Tools and chambers |
| `process_steps.yaml` | Route steps |
| `control_plans.yaml` | Control method, sample size, OCAP per characteristic |

## Preconditions and errors

| Error | When |
|---|---|
| `ConfigurationError` | Missing file, invalid YAML, unknown key, failed validation |
| `UnknownUnitError` | Unit or conversion not in the registry |

## Versioning

`settings.config_revision` is a SHA-256 of the effective payload. Every
analytical output must carry it alongside data and code revisions (FR-RP02).
