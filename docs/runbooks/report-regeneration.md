# Runbook — regenerate a report

## When

An auditor or quality engineer asks for the same capability, SPC, MSA, or
excursion summary that was previously issued, or a recipient's copy must be
checked against the platform.

## Preconditions

- The stated `data_revision` is still retained.
- The stated `code_revision` is available in git (a `-dirty` revision cannot be
  regenerated from a clean checkout — refuse and say so).
- The stated `config_revision` can be reconstructed from committed config.

## Steps

1. Read the provenance header on the artefact (or the audit `report_generated`
   event).
2. Check out `code_revision` and confirm the working tree is clean.
3. Load configuration that hashes to `config_revision`.
4. Run:

   ```bash
   spc generate-report \
     --report-type capability_study \
     --parameter-id OXIDE_THK \
     --product-id DEV-A \
     --window-start 2025-07-01T00:00:00+00:00 \
     --window-end 2025-07-14T00:00:00+00:00 \
     --target html \
     --output /tmp/regen.html
   ```

5. Diff the HTML against the retained copy. They must match when the clock is
   fixed to the original `generated_at` (tests use `FixedClock` for this).

## Failure modes

| Symptom | Action |
|---|---|
| Data revision missing | Restore from retention; do not invent a substitute series |
| Code revision `-dirty` | State that the original was not reproducible from a commit |
| Capability refused (OOC) | Correct — do not force a report; the refusal is the record |
| PDF engine unavailable | Deliver HTML; install WeasyPrint system libraries for PDF |
