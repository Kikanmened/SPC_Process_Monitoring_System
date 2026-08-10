# Report provenance

Every generated report and audit package carries the three revisions required
by FR-RP02 / BO-4 so a recipient can regenerate or independently verify the
artefact.

## Header fields

| Field | Meaning |
|---|---|
| `data_revision` | Content-addressed measurement revision the numbers came from |
| `code_revision` | Git short hash (or `local-dev` / `-dirty`) of the analytics path |
| `config_revision` | Hash of the effective configuration payload |
| `generated_at` / `recorded_at` | Timezone-aware instants from the injected clock |
| Parameters | Report-specific inputs (parameter, product, excursion id, …) |

The HTML template marks the block with `data-provenance="required"`. Contract
tests fail if any of these markers are absent.

## How to verify

1. Note the three revisions and parameters from the header.
2. Check out the stated `code_revision` and load the stated `config_revision`.
3. Ensure the measurement store still holds `data_revision`.
4. Re-run `generate_report` (or `spc generate-report`) with the same parameters
   and a fixed clock matching `generated_at` when byte identity is required.
5. Compare HTML bytes (FR-RP03). PDF is a derived render of the same HTML when
   WeasyPrint system libraries are available.

## Audit packages

`assemble_audit_package` produces a zip containing `manifest.json`, the data
extract, limits in force, chart series, dispositions, and embedded HTML
reports. The package's SHA-256 digest is returned to the caller and audited so
a recipient can detect tampering without trusting the transport.
