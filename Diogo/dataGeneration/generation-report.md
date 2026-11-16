# Generation report - 13 November 2026

Reference and scale profiles completed and passed independent exported-file
validation with **zero errors**. MongoDB loading and server queries were not
performed. These are fictional project data, with synthetic administrative
outcomes and sampled movements; account balances/underwriting are not modelled.

## Runs and reproduction

- Scale run: `outputs/scale/27ff7c5b1b33fa7c/`.
- Reference run: `outputs/reference/afdfc69e88aed2e5/`.
- Generator: `1.1.0`; base seed: `42`.
- Runtime: CPython 3.14.3; SQLite 3.50.4.
- Scale fingerprint: `27ff7c5b1b33fa7cff45ac9dfea4ead3bc649449d1d0d9d7ffce153663ace783`.

Commands executed from the MID-P1 repository root:

```powershell
python -B -m unittest discover -s Diogo/dataGeneration/tests -v
python -B Diogo/dataGeneration/generate.py run --profile reference
python -B Diogo/dataGeneration/generate.py run --profile scale --batch-size 250
python -B Diogo/dataGeneration/validate.py Diogo/dataGeneration/outputs/reference/afdfc69e88aed2e5
python -B Diogo/dataGeneration/validate.py Diogo/dataGeneration/outputs/scale/27ff7c5b1b33fa7c
```

Repeat the scale run command with unchanged inputs/code/runtime to resume or
verify its completed run. Every completed export is hashed; changed exports
are refused. Keep the entire local run folder for checkpoint recovery.

Generated run folders are ignored by Git. This report, generator, catalogues
and configuration document the reproducible source. The report does not
claim the exported datasets have been committed or pushed. To reproduce
identical source hashes, retain the pinned inputs, source bytes and runtime.
Repository `.gitattributes` pins generator Python/JSON files to LF, preventing
automatic checkout line-ending changes from altering Python source hashes.

## Measured scale counts

| Source | Records |
|---|---:|
| clients | 500 |
| employees | 25 |
| accounts | 1,000 |
| applications | 750 |
| transactions | 8,000 |

Total MongoDB-export documents: **2,275**. CSV has **8,000 data rows plus one
header**: 6,000 ordinary movements and 2,000 transfer legs.

## Names, amounts and application allocation

The catalogue has 80 first names and 80 surnames. Names are sampled
without replacement across clients and employees, using two distinct surnames.
Validation found **525 unique full names** across all 525 people.
Reusing a given name/surname is allowed; repeating an entire full name is not.

Example generated names:

- `C000001`: Clara Baptista Coelho.
- `C000002`: Filipa Fonseca Melo.
- `C000003`: Bruno Fernandes Cunha.
- `E000001`: Sérgio Branco Pereira.
- `E000002`: Jorge Macedo Campos.
- `E000003`: Manuel Barros Machado.

| Applications per client | Clients |
|---:|---:|
| 0 | 150 |
| 1 | 200 |
| 2 | 75 |
| 4 | 25 |
| 5 | 25 |
| 7 | 25 |

Application statuses: **410 approved, 190 declined, 150 pending**. Exactly
**75 pending applications omit employeeId**. All approved/declined requests
have an existing employee. One employee has zero assigned applications.

Every application amount is a multiple of **EUR 10**, within its purpose
range. A 60% sampling probability selects a configured common amount; the
remaining sampling branch chooses uniformly among allowed EUR 10 multiples.
Two fixed query cases retain EUR 18,000 pending and EUR 32,000 declined.
Observed: **455 amounts match their purpose-specific common lists**,
and **295 are other EUR 10 multiples**. A random draw can also hit a common value,
so list membership does not identify the sampling branch exactly.

Examples in EUR: 100000.00, 40000.00, 10000.00, 18000.00, 32000.00, 15000.00, 43870.00, 30000.00, 24810.00, 76300.00.

## Transactions and validation

- 1,000 transfer IDs, each with exactly two distinct-account legs, matching
  amount/currency/date and opposite IN/OUT directions.
- 300 same-client pairs; 700 different-client pairs.
- 6,000 ordinary rows have empty transferId.
- No movement predates its account opening; all currencies are EUR.
- Employment, account ownership/status, application purpose/status and
  application-count quotas match configuration.
- Required fields, unique IDs/emails, BSON Extended JSON types and exact
  decimal/date/CSV formatting passed exported-file checks.
- Actual clients with zero September movements: 121 (at least 25 reserved).
- Actual clients with no movements anywhere: 7 (at least 5 reserved).
- Boundary dates, accented text, embedded quotes and semicolons are present.
- Hand-calculated reference BQ1/BQ2 answers passed. Scale expected query
  answers and parameters are in each run's expected-query-results.json;
  executing the actual banking queries remains a separate step.

All **nine tests passed**, including hard process termination, rollback of
a failed transfer unit, partial-export recovery, missing-export rebuilding,
changed-input rejection, clean/resumed byte equality across batch sizes,
and independent rejection of broken references, duplicate names, invalid
assignment statuses and unequal transfer pairs.

The first attempt hit Windows permissions on system temporary folders.
Tests now use owned project-local scratch directories with inherited ACLs.
Runtime verification also found and corrected an employee-validation branch
that incorrectly treated employee rows as transaction rows before final runs.

## Scale source SHA-256

| File | SHA-256 |
|---|---|
| `accounts.jsonl` | `b121891f564cf2c724bae384817743b59c64ce1a723aa04ad1bd6726ee70847f` |
| `applications.jsonl` | `f6884ebcd6ec2faad07909392c1dbb276ed87dc561bce08bb7138f6b6afa5f65` |
| `clients.jsonl` | `b0876930afdf65005ee59c783066c0ee0892f88ba74b7fb03edfe7414ad98329` |
| `employees.jsonl` | `10eea48025775231c3ffd94c6fc8fdbb5abd3f29632838b90ee6c3db713fc7a4` |
| `transactions.csv` | `f731c34a0afe33b9efe0e8cd07de761573f7df5e2e52961169a430dc24b00694` |

Each run also retains input/source snapshots, scenario-plan.json,
quality-report.json, expected-query-results.json and manifest.json.
No report.tex edits, MongoDB schema changes, database imports, server startup,
API calls, Git commits or pushes were performed by this generation step.

## Subsequent MongoDB installation and viewing

After generation, the scale source was loaded into `dmi_p1_bank` on MongoDB
8.0.32 using `database/load.py`. All 2,275 stored documents match their source
exactly; Decimal128/Date/int types and all reference checks passed. A repeated
load inserted zero additional documents. Read-only stored verification passed.
The browser viewer returned HTTP 200 and displayed the first generated client.

Instructions: [database/README.md](../database/README.md). Operational receipt:
`outputs/scale/27ff7c5b1b33fa7c/mongodb-load-report.json`. This later receipt is
outside the frozen generation manifest; its original `mongoLoadingPerformed`
value describes the generation step itself.
