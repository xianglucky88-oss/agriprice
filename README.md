# agriprice

A small offline data-processing service with a local HTTP fixture and SQLite storage. It is self-contained and does not require network access.

## Usage

```text
make run       # process the bundled source
make run_inc   # process using the incremental command-line mode
make test      # run the test suite
make mock      # start the local fixture service
```

The package exposes a Python entry point under `src/agriprice`. The fixture service supports the source formats used by the package, and the command-line entry point writes results to the local SQLite database. Re-running commands is safe for an existing database.

## Quote normalization

The same wholesale quote may be published per kilogram first and corrected to per ton later, and historical batches may arrive again together with already processed records. `agriprice.kernel.process` turns every raw quote into one canonical result so the same transaction always yields the same amount, no matter how often or in which order it is delivered.

Each processed record carries:

* `value_raw` / `unit_raw` — the original expression, for traceability.
* `value_norm` / `unit_norm` — the price per canonical unit (`ton`); `value_norm` is `null` when the input cannot be used.
* `scale_factor` — the multiplier applied to the raw value (`1.0` when the unit is missing or unknown).
* `quality` — `ok`, `zero`, `negative`, `extreme`, `missing`, or `invalid`, so unusable input stays distinct from genuine zero/negative/extreme quotes. Extreme values (|value_norm| >= 1e9) are kept as-is, never silently rescaled.
* `flags` — hints such as `scientific_notation` and `unit_assumed`.
* `rule` — the rule version that produced the result.

Stored rows are keyed by the source expression, not by the derived result. Re-running the same rules never rewrites a stored row; when the rule version changes, only rows whose outcome actually changes are rewritten. Full and incremental runs use the same identity-based dedup, so late or out-of-order corrections are still ingested, and a failed run never advances the collection watermark.
