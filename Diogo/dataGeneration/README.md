# Data generation

Implemented, **not executed**. No exported dataset, checkpoint database, MongoDB
import or API call has been produced during implementation. Runtime behaviour
still needs verification when generation is authorised.

Requires Python 3.11+ and its standard library only. No SDK, API key, Docker,
MongoDB server, Faker or Python database package is needed to generate files.
AI assisted with implementation; the actual generator uses frozen catalogues,
configuration and seeded code.

## Scope and sizes

| Profile | Clients | Employees | Accounts | Applications | CSV data rows |
|---|---:|---:|---:|---:|---:|
| `scale` | 500 | 25 | 1,000 | 1,500 | 8,000 |
| `reference` | 5 | 2 | 6 | 6 | 10 |

The scale source has 3,025 MongoDB documents. Its CSV contains 6,000 ordinary
movements and 1,000 complete transfer pairs (2,000 rows). Counts, income bands,
purpose ranges, dates and sampling assumptions are in `config.json` and the
parent `data-generation-plan.md`.

Dependency order: clients -> employees -> accounts -> applications ->
transactions. Clients/employee identities exist before dependent records.
Each transfer is built and committed as one two-row unit.

## Commands for later execution

Run from the MID-P1 repository root. These commands are examples; they have **not** been
executed during implementation.

```powershell
# Start the scale profile, or resume its existing matching run.
python Diogo/dataGeneration/generate.py run --profile scale

# Build only through accounts, then stop before applications/transactions.
python Diogo/dataGeneration/generate.py run --profile scale --until accounts

# Continue the same run; completed records are reused.
python Diogo/dataGeneration/generate.py run --profile scale

# Inspect progress without generating records.
python Diogo/dataGeneration/generate.py status --profile scale

# Small hand-checkable dataset, isolated from the scale profile.
python Diogo/dataGeneration/generate.py run --profile reference
```

Output defaults to:

```text
Diogo/dataGeneration/outputs/<profile>/<fingerprint-prefix>/
```

The fingerprint covers configuration, catalogues, reference inputs, generator
source files and Python implementation/version. Editing any of those creates a
different default run identity. Status can inspect an older run using its
explicit `--output` path.

```powershell
# Explicit run directory. Repeat exactly to resume.
python Diogo/dataGeneration/generate.py run --profile scale --output Diogo/dataGeneration/outputs/my-run

# Intentional pause midway; the limit counts new units in this invocation.
python Diogo/dataGeneration/generate.py run --profile scale --output Diogo/dataGeneration/outputs/my-run --stop-after-units 700 --batch-size 25

# Resume without the intentional stop limit.
python Diogo/dataGeneration/generate.py run --profile scale --output Diogo/dataGeneration/outputs/my-run

# Inspect a specific run.
python Diogo/dataGeneration/generate.py status --output Diogo/dataGeneration/outputs/my-run

# Validate completed exports independently, without regenerating them.
python Diogo/dataGeneration/validate.py Diogo/dataGeneration/outputs/my-run
```

For a clean restart, choose a **new empty `--output` directory**. Existing runs
are preserved. There is deliberately no automatic drop/reset/delete operation.

## Failure and resume behaviour

- A local SQLite database tracks records and per-stage unit cursors. It is
  checkpoint state, not an additional submitted banking data source.
- Default batches contain up to 100 units. Record inserts and their cursor
  commit in one transaction with SQLite WAL and full synchronous writes.
- Ctrl+C, process termination or a failure before commit may discard that
  in-flight batch. A subsequent run regenerates those uncommitted units with
  identical per-unit seeds. Already committed units are not duplicated.
- One transfer pair is one unit. A commit cannot preserve only one leg.
- No RNG pickle/state blob is needed: seeds derive from fixed stage offsets
  and stable SHA-256 inputs. Batch size and pause positions do not affect
  the intended record values.
- An operating-system lock prevents two generators writing one run directory.
  A crash releases that lock; the lock file itself may remain and is harmless.
- Interrupted first-time initialisation can be resumed if its database is
  empty/recognisable. A malformed or structurally corrupt checkpoint causes a
  clear failure rather than an automatic reset.
- Export writes go to `*.part`, are flushed/fsynced, and are atomically renamed.
  Exports interrupted before completion can be rebuilt from committed records.
- Each completed export has a checksum. Changed completed exports are rejected
  rather than silently overwritten. Missing exports can be reconstructed from
  an intact checkpoint; run identity and inputs must still match.
- `manifest.json` is written after source validation and report creation. Its
  `complete: true` plus successful independent validation identifies a complete
  dataset; the existence of a CSV alone does not.
- Resume requires the original configuration, catalogues, reference data,
  generator code and Python version. Restore those versions or use a new run
  directory after changes. Exact `source-*.py` snapshots are saved with the run:
  they can be copied into a separate folder under their original names,
  alongside the saved config/catalogues/reference inputs, to restore an older
  implementation. Then use the existing run's explicit `--output` path.
  Keep the entire stopped run folder, including its checkpoint, when moving
  or backing it up. SQLite runtime version is also part of the run identity.

Runtime has no model/API dependency, so an AI usage limit does not stop a
generator process that is already running. Checkpoints handle machine/process
interruptions and deliberate pauses. They do not resume unfinished AI coding
sessions or recover an independently deleted checkpoint.

## Outputs and storage representations

| File | Contents |
|---|---|
| `clients.jsonl`, `employees.jsonl`, `accounts.jsonl`, `applications.jsonl` | Canonical MongoDB Extended JSON records, one per line |
| `transactions.csv` | UTF-8 without BOM; eight columns; semicolon delimiter; CRLF; correct quoting |
| `identity.json`, `config.json`, `catalogues.json`, `reference.json` | Exact inputs/provenance for this run |
| `source-*.py` | Frozen implementation bytes for reproducibility and recovery |
| `scenario-plan.json` | Allocated owners, quotas, assignments and reserved cases |
| `quality-report.json` | Independent exported-file checks, errors and distributions |
| `expected-query-results.json` | Exact-decimal BQ1/BQ2 answers with source hashes and query parameters |
| `manifest.json` | Completed-run identity, counts and file hashes |
| `checkpoint.sqlite3`, possible `-wal`/`-shm`, `.writer.lock` | Internal resumable state; not MongoDB source data |

Inside checkpoint/reference input records, monetary fields use **integer
cents** and dates use ISO strings. During export, money becomes
`{"$numberDecimal":"15000.00"}`, dates use canonical `$date`/`$numberLong`,
and terms use `$numberInt`. CSV stores positive comma-decimal text and explicit
IN/OUT direction. Expected-result JSON uses decimal strings for exact amounts.

Identifiers accept at least three digits. Scale IDs have six digits, e.g.
`C000004`; reference fixtures retain `C004`. This widens the earlier three-digit
prototype. The old `database/setup.js` is not used or modified, and its old
validators cannot load the scale profile unchanged.

## Designed data quality

- Exactly one or more accounts per client; assigned references always select
  already-created entities. Current status only, with optional employee field.
- Controlled employment, account/status and purpose quotas; income bands and
  purpose-specific request/term ranges are explicit synthetic assumptions.
- Recurring salary/pension movements relate to annual income, with documented
  cent rounding and bounded variation. They are not actual net-pay estimates.
- Reserve clients without applications, employees without work, accounts with
  no movements and clients with zero September activity.
- Transfers preserve two distinct accounts, one IN/one OUT, equal money and
  currency; 300 same-client and 700 different-client pairs in the scale profile.
- Include period-boundary dates, cent values, accented text, quotes, semicolons
  and repeated descriptions. No invalid test records enter the main sources.
- Validation re-reads exported files independently of record construction and
  checks hand-specified reference answers. Future executable banking queries
  must be compared with these expected results.

These checks establish internal coherence and file fidelity, not real-world
accuracy, regulatory compliance, a full ledger, balances or creditworthiness.
No MongoDB schema, imports, server queries or external databases are executed
by this folder's generation workflow. Local SQLite is used only for checkpoints.
MongoDB loading remains a separate task.

## Future runtime verification

Recovery tests are supplied in `tests/test_recovery.py` but were **not run**.
They deliberately generate temporary reference/scale datasets, so execute them
only when generation is permitted:

```powershell
python -B -m unittest discover -s Diogo/dataGeneration/tests -v
```

They cover abrupt process death, transaction rollback, transfer-pair atomicity, interrupted exports,
changed-input rejection, missing-export recovery, clean/resumed hash equality
under different batch sizes, default scale quotas and independent rejection
of a CSV with a broken account reference.
