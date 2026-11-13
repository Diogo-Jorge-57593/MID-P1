# Synthetic banking data generation plan

Date: 13 November 2026. Status: strategy implemented in `dataGeneration/`;
generator and runtime tests have not been executed.

This document defines a reproducible process for the latest MongoDB and CSV
models. Generator implementation now follows this plan in `dataGeneration/`.
No large dataset is generated and no revised MongoDB schema is installed.
MongoDB loading/server verification remain separate work.

## 1. Method and target scale

Use a deterministic Python generator, with explicit configuration, fixed random
seeds, small frozen fictional-name/description catalogues and independent
validation. AI assists with designing and writing the process; ordinary code
produces records from documented rules.

| Entity / source | Target | How count is obtained |
|---|---:|---|
| Clients / MongoDB | 500 | Root population |
| Employees / MongoDB | 25 | Created independently before assignment |
| Accounts / MongoDB | 1,000 | 100 clients own one account, 300 own two, 100 own three |
| Credit applications / MongoDB | 1,500 | Assigned to a controlled subset of existing clients |
| **MongoDB documents** | **3,025** | Sum of four collections |
| Transactions / CSV | 8,000 | 6,000 ordinary movements plus 1,000 internal-transfer pairs |

Counts are exact design targets, not estimates of real bank activity. CSV has
8,000 data records plus one header. It is an illustrative movement sample,
not a complete ledger for 500 clients over the period.

All personal records are fictional. Income, lending and activity distributions
are modelling assumptions, not observed Portuguese banking statistics.

## 2. Identifier change needed before scaling

Current physical specification uses exactly three digits. That cannot identify
1,500 applications or 8,000 distinct movements without changing the format.

Implemented generator convention (physical specification updated):

- Allow three or more digits in physical validation patterns, preserving the
  existing small examples: `^C[0-9]{3,}$`, `^A[0-9]{3,}$`, `^E[0-9]{3,}$`,
  `^L[0-9]{3,}$`, `^T[0-9]{3,}$`, `^TR[0-9]{3,}$`.
- Generate the new large profile with six-digit, zero-padded numeric parts:
  `C000001`, `A000001`, `E000001`, `L000001`, `T000001`, `TR000001`.
- Generate all references from the allocated identifier registries. Never
  invent a foreign identifier separately.
- Keep identifier width consistent within each profile, preserving useful
  lexical ordering. An identifier is an identity, not an encoded business fact.

The physical specification now accepts the wider patterns. Legacy database
setup.js still requires alignment before loading; the generator does not run
or update that database script. Reference query parameters remain unchanged;
scale parameters are recorded in each generated manifest/result file.

## 3. Two dataset profiles

**Reference profile:** retain a small, deliberately designed dataset for
hand-checkable query results. Start with the existing five clients, six
accounts and six applications, align their fields to the latest model, add
employee assignments and use the ten-row CSV specimen. Existing reference
query tables remain tied to this profile.

**Scale profile:** generate the target counts above, with a larger range of
valid scenarios. It has its own expected results and manifest. Do not mix its
results with the small reference tables or silently load both profiles into
one database.

For scale-profile BQ1, reserve client `C000004` with exactly two applications:
18,000.00 EUR pending and 32,000.00 EUR declined. Allocate their application IDs
deterministically and record them in the manifest. Exclude this client from
later random application allocation. The question stays the same; its example
client parameter changes from `C004` to `C000004`.

## 4. Generation order and dependencies

```text
Configuration, version, seeds, frozen catalogues
    -> Clients                 Employees
         -> Accounts              |
         -> Credit applications <-+
              
Accounts -> ordinary movements + paired transfers
    -> validate all records and references
    -> export Extended JSON + CSV
    -> validate exported representations
    -> load into MongoDB and verify stored BSON types
    -> query results + data-quality report + manifest
```

No step selects a client, employee or account that has not already been
created. Export files are generation artefacts; MongoDB and CSV remain the
two project sources.

### Step A - Clients

1. Allocate exactly 500 unique IDs and fictional names.
2. Generate a unique synthetic email from the ID, such as
   `c000001@example.invalid`. Duplicate human names are allowed; IDs establish
   identity.
3. Allocate employment categories by exact quotas:

| Employment status | Count |
|---|---:|
| employed | 325 |
| self-employed | 50 |
| retired | 50 |
| student | 50 |
| unemployed | 25 |

4. Assign income from configurable, weighted integer-cent bands for each
   category. Proposed defaults below concentrate employed incomes in middle
   bands and permit zero/lower income for students and unemployed clients.
5. Store these exact bands/weights in configuration. They are invented
   scenarios, not affordability rules. Do not add age, expenses or liabilities
   unless the model is explicitly extended.

| Employment status | Annual income bands in EUR | Band-selection weights |
|---|---|---|
| employed | 15,000-24,999.99; 25,000-44,999.99; 45,000-90,000 | 25%, 55%, 20% |
| self-employed | 8,000-19,999.99; 20,000-59,999.99; 60,000-140,000 | 25%, 55%, 20% |
| retired | 6,000-11,999.99; 12,000-24,999.99; 25,000-45,000 | 30%, 55%, 15% |
| student | Exactly 0; 0.01-6,000; 6,000.01-18,000 | 35%, 45%, 20% |
| unemployed | Exactly 0; 0.01-9,000; 9,000.01-18,000 | 45%, 40%, 15% |

Select the band with integer weights, then sample uniformly in integer cents
within that band. Employment counts are exact quotas; income band counts are
seeded samples. Decimal points here describe numeric values, not CSV formatting.

### Step B - Employees

Create 25 unique employees with fictional names. Reserve one employee with no
assigned applications to exercise empty-workload behaviour. Distribute assigned
applications across the other 24, with controlled variation in workloads.

### Step C - Accounts

1. Allocate the exact one/two/three-account ownership quotas in section 1.
2. Give every client one current account. Additional accounts may be savings
   or current accounts under configurable weights.
3. Set currency to EUR. Generate opening dates from 1 January 2025 through
   31 August 2026, with midnight-UTC BSON encoding. The 180 recurring-income
   cases below have a designated active current account opened before 2026.
4. Allocate proposed status quotas: 900 active, 50 blocked, 50 closed.
5. Do not infer a closure/blocking timestamp from current status: those dates
   are not modelled. Valid older movements may exist for inactive accounts.

Account status is administrative sample data. There is no claim that the
dataset reconstructs a complete account lifecycle.

### Step D - Credit applications

1. Reserve 100 clients with no applications, including `C000005`. Allocate
   applications only to the remaining 400; every one of those receives at
   least one. Respect the exactly-two case for `C000004`.
2. Allocate the remaining applications with a weighted distribution that
   produces different numbers of applications per client.
3. Use exact status quotas: 825 approved, 375 declined, 300 pending. The two
   reserved BQ1 applications count toward these totals.
4. Leave 150 pending applications unassigned. Assign every other application
   to an existing employee; the reserved no-workload employee remains unused.
5. Draw positive requested amounts and terms from the purpose-specific defaults
   below. Vehicle loans have shorter sampled terms than home-improvement loans,
   without pretending to model underwriting.
6. Submission instants fall within 2026, no later than the fixed snapshot
   date. Sample pending requests within August-October and unassigned requests
   within 16-31 October; sample approved/declined requests within January-
   15 October. These are assumptions about the snapshot, not measured delays.
   Submission need not follow an account's opening date: this model requires
   a client relationship, not an account-specific application.

Approved/declined states are synthetic administrative outcomes. This generator
does not assess solvency, simulate disbursements, maintain status history or
infer a credit score. Purpose and term sampling ranges are scenario choices,
not new schema maximums.

| Purpose | Count | Requested amount range (EUR) | Sampled term choices (months) |
|---|---:|---|---|
| vehicle | 525 | 3,000-45,000 | 12, 24, 36, 48, 60, 72 |
| education | 225 | 1,000-30,000 | 12, 24, 36, 48, 60, 84 |
| home_improvement | 375 | 5,000-120,000 | 24, 36, 60, 84, 120, 180, 240 |
| personal_expense | 225 | 500-20,000 | 6, 12, 24, 36, 48 |
| debt_consolidation | 150 | 2,000-50,000 | 12, 24, 36, 48, 60, 84 |

The two reserved BQ1 cases use home improvement and debt consolidation,
respectively, and count toward those quotas. Sample an integer-cent principal
within its range and a term from the corresponding list; keep status allocation
separate from creditworthiness. Actual distribution is reported after generation.

### Step E - Transactions

Use a fixed observation period: **1 January-31 October 2026**. The snapshot date
is 31 October 2026. Never use the execution day's date to choose generated
records.

**Ordinary movements: 6,000 rows.**

- Use a documented mix of income/deposits, purchases, cash withdrawals and
  fees. Generate descriptions from frozen templates consistent with direction
  and account type.
- Reserve 150 employed and 30 retired clients for ten monthly income movements
  each: 1,800 rows. Exclude the September zero-activity clients. Their designated
  current accounts must be active and opened before the observation period.
  Book on day 25; base amount is annual income divided by 12, rounded half-up
  to cents, with a documented integer percentage variation between -3% and +3%.
  This is an illustrative relationship, not a net-pay or tax calculation.
- Add 200 incoming deposits, 3,000 outgoing purchases, 500 outgoing withdrawals
  and 500 outgoing fees. Together with recurring income, these total 6,000.
- Default amount ranges: deposits 20-10,000 EUR; purchases 0.50-5,000 EUR;
  withdrawals 10-500 EUR in multiples of 10; fees 0.50-15 EUR. Sample money in
  cents; account/type eligibility and frozen descriptions determine context.
- Choose dates after the referenced account's opening date and within the
  observation period. If a planned recurring date predates opening, do not
  create that occurrence; allocate the remaining row budget to eligible cases.
- Ordinary rows have empty `transferId`.

**Internal transfers: 1,000 pairs, 2,000 rows.**

- Select two different existing accounts, both opened by the booking date.
- Sample a positive whole-cent amount from 1-20,000 EUR.
- Generate 300 pairs between accounts of the same client and 700 between
  accounts of different clients. Same-client transfers select clients with
  multiple eligible accounts.
- Generate the pair from one transfer object in memory: one shared ID, amount
  and currency, with one OUT and one IN row. Never generate the two legs
  independently and hope they match.
- Export each leg as a separate Transaction. Use the same booking date for
  the default generator; the source contract can still accept different dates.

**Coverage guarantees:**

- Reserve at least 25 clients with no movements during September, including
  `C000005`; retain their accounts so BQ2 must return zero totals.
- Reserve at least five clients with no movements in the entire source,
  including `C000005`, and at least 20 unused accounts overall. These cases
  are excluded from recurring income, random movements and transfer selection.
- Guarantee cases on 31 August, 1 September, 30 September and 1 October for
  the period-boundary checks.
- Include cent amounts, repeated descriptions, accented text, quoted
  semicolons and embedded double quotes.
- Generate all other movements only after these cases are allocated, so
  random sampling cannot accidentally destroy the guarantees.

Transfers must be represented exactly once as a pair. No exchange rates,
transfer fees folded into the pair, account balances or insufficient-funds
checks are implied. The model lacks opening balances and a complete ledger.

## 5. Reproducibility and physical export

- Use a fixed base seed, proposed value **42**, and independent random-number
  generators for clients, employees, accounts, applications and transactions.
  Derive stage seeds using documented fixed numeric offsets, not Python's
  process-randomised `hash()`.
- Freeze configuration, dictionaries/templates, generator version and runtime
  dependencies. A seed alone does not guarantee reproducibility across code
  or library changes.
- Work in integer cents for generated money; convert directly to Decimal128
  from decimal strings on MongoDB loading. CSV uses the agreed positive
  amount and explicit direction, with decimal commas and two decimal places.
- Export MongoDB fixtures as canonical Extended JSON lines, preserving
  Decimal128, BSON dates and integer types. Plain JSON numbers/date strings
  alone do not preserve the physical BSON schema.
- Export CSV with UTF-8 without BOM, semicolons, exact eight-column header,
  CRLF record terminators and proper quoting. Sort by parsed booking date,
  then transaction ID.
- Stable IDs, record order and serialisation make dataset files byte-for-byte
  reproducible with the same pinned code/configuration/environment. A manifest
  run timestamp may differ; keep it separate from dataset-content hashes.

Implemented output layout; output directories are created only on a future run:

```text
Diogo/
  dataGeneration/
    config.json
    generate.py
    builder.py
    checkpoint.py
    common.py
    validate.py
    catalogues.json
    reference.json
    README.md
    outputs/<profile>/<dataset-id>/
        clients.jsonl
        employees.jsonl
        accounts.jsonl
        applications.jsonl
        transactions.csv
        identity.json
        config.json
        catalogues.json
        reference.json
        source-*.py
        scenario-plan.json
        checkpoint.sqlite3
        manifest.json
        quality-report.json
        expected-query-results.json
```

The manifest records profile, seed/stage seeds, fixed dates, code/config
versions or hashes, dependency versions, row/document counts, distributions,
file SHA-256 hashes and example-query identifiers.

## 6. Independent validation and evidence

Separate the generator from its validator. Validation recomputes relationships
and totals from exported data rather than accepting the generator's assertions.

| Quality dimension | Required check |
|---|---|
| Completeness | All required fields exist; only employee assignment/transfer ID may be absent as defined |
| Uniqueness | Unique entity/movement IDs; synthetic email uniqueness is a generation choice |
| Domains and types | Allowed statuses, positive integer terms, exact BSON types after loading |
| References | Account/application clients and assigned employees exist; every CSV account exists |
| Cardinalities | Each client has at least one account; designed zero-application/zero-workload cases retained |
| Money | Finite whole-cent values; income non-negative; requests/movements positive; EUR only |
| Temporal consistency | Account opening convention; movements do not predate account opening; fixed observation bounds |
| Transfers | Exactly two legs per non-empty transfer ID; distinct accounts, opposite directions, equal amount/currency |
| Coverage | Required edge cases and exact category/status/row quotas are present |
| Export fidelity | Re-read the actual CSV/Extended JSON; verify quoting, Unicode, dates and decimal precision |
| Query correctness | Compare implemented results to separate small hand-checkable fixtures and independent scale totals |
| Reproducibility | Two temporary generations under pinned settings yield the same dataset-file hashes |

Quality report records counts, distributions, zero-activity cases, validation
failures and passed checks. Generation/export acceptance requires zero
violations of the declared constraints. Checks demonstrate internal coherence,
not factual accuracy or statistical representativeness.

Invalid examples belong in a separate validation-test set, not the clean main
sources. Include broken references, duplicate IDs, invalid dates, malformed
amounts and incomplete transfer pairs there.

Do not compute expected results using only the same query function under test.
Use hand-calculated reference results plus a separately implemented aggregation
over the generated records, and record which dataset hash each result belongs to.

## 7. Loading and existing project changes

Generation can run offline. MongoDB is needed only for schema installation,
loading and stored-source/query verification.

Before loading:

1. Align `database/setup.js` and its verification with the latest four-collection
   schema, current-status-only model and widened identifier patterns.
2. Inspect the target database. Never drop data or silently overwrite an
   existing source/profile. Keep the small reference profile separate from
   the scale profile; refuse a conflicting load until a specific migration
   or separate versioned database is chosen.
3. Load clients and employees first, then accounts and applications. Run
   post-load cross-collection and BSON-type checks.
4. Point BQ2 to the matching CSV and record the database/profile/file hashes
   with its results. The source pair must belong to the same generation run.

Update report and README with the actual process, commands and measured
results. Update small/large query parameters and expected results explicitly;
the old six-application verification cannot validate a 1,500-application source.

Coordinate a shared identity registry with the venture-capital colleague before
finalising cross-subtopic fixtures. If their sources include individual
investors, a selected subset of bank clients can share explicit party IDs or a
documented mapping. The exact link awaits their schema; do not invent company
clients or treat matching names as identity. Exporting stable bank client IDs
lets both students construct related examples rather than unrelated populations.

## 8. AI contribution and automation options

Recommended use of AI:

1. Help specify scenario distributions and review business-rule consistency.
2. Implement the seeded generator and exports from this specification.
3. Review the implementation and design independent validation cases.
4. Explain the process and report actual evidence for student review.

Bulk record production remains deterministic code. Re-prompting a model for
every customer or transaction adds variation and makes a seed insufficient
to reproduce the source. If AI contributes names/templates, freeze those
catalogues and record their provenance before generating the dataset.

AI-use declaration should identify the tool, purpose, extent, student changes
and verification actually performed. Automated agents still work from task
instructions; moving them into a script replaces repeated chat interaction
with a repeatable, versioned task definition.

Current official options checked on 13 November 2026:

| Option | Fit for this project |
|---|---|
| Codex CLI `codex exec` | Run a coding/review task from a terminal or pipeline; existing local CLI is installed |
| Codex SDK | Python/TypeScript control of local Codex sessions; useful if scripting several coding/review stages |
| Agents API | OpenAI-managed Codex harness, with agent sessions and tools; API usage is billed; more infrastructure than this local generator needs |

The local CLI/SDK is a practical match for files and MongoDB running on this
machine. A hosted API sandbox does not automatically have access to this
workspace or its localhost MongoDB; that needs an explicit file/environment
integration.

Example **future review invocation**, not executed by this task:

```powershell
codex exec --sandbox read-only "Read Diogo/data-generation-plan.md. Review dependency order, reproducibility and validation. Do not generate data or modify files."
```

Run that review command from the MID-P1 Git repository root. For later
implementation, use a bounded workspace-write task after the plan is accepted.
A single coding agent plus a separate review stage is enough initially;
multiple data-producing agents must not allocate IDs or references independently.

Official OpenAI documentation:

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk): local agent control, Python and TypeScript libraries.
- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): CLI automation, permissions, saved authentication and JSONL events.
- [Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview): managed Codex harness, execution environments and API billing.

No API call, agent launch, SDK installation or data-generation run is made by
this planning/implementation work. See `dataGeneration/README.md` for future
run/resume/status commands and the unexecuted runtime-recovery tests.
