# P1 - Diogo - Banking

Banking contribution: MongoDB clients, accounts, employees and credit
applications, plus transaction movements in CSV. This is a data modelling
project; there is no banking application.

## Models and definitions

- `models/Models.drawio`: conceptual/logical diagrams.
- `logical.txt`, `physical.txt`: field definitions and storage contracts.
- `models/PhysicalModels.drawio`, physical SVGs: physical model diagrams.
- `queries/requirements.md`: BQ1/BQ2 definitions; joint queries remain pending.
- `queries/datalog.md`: both queries in the lessons' logical rule notation,
  with aggregation and zero-result handling explicitly identified for BQ2.
- `data-generation-plan.md`: generation strategy, quotas and assumptions.
- `report/report.tex`: report draft. The saved PDF is a compiled snapshot;
  rebuild it after reviewing or editing the report.

## Data generation

[dataGeneration/README.md](dataGeneration/README.md) documents the offline
generator, separate reference/scale profiles, deterministic seeds, transactional
checkpoints, automatic resume, atomic exports and independent validation.
Reference and scale datasets were generated and independently validated on
13 November 2026; all nine runtime tests passed. The scale profile contains
500 clients, 25 employees, 1,000 accounts, 750 applications and 8,000 CSV rows.
Measured results: [dataGeneration/generation-report.md](dataGeneration/generation-report.md).
The generator needs Python 3.11+ and its standard library. Docker and API keys
are not needed for file generation.

From the **MID-P1 repository root**, to reproduce or resume:

```powershell
python Diogo/dataGeneration/generate.py run --profile scale
python Diogo/dataGeneration/generate.py status --profile scale
```

Repeat the run command to resume matching committed work. Generated outputs
and checkpoints are ignored by Git; keep the whole local run folder to resume.

## MongoDB installation and visualisation

MongoDB 8.0.32 is running in the project container, with the full scale source
loaded into `dmi_p1_bank`. Counts, actual BSON types, exact source equality and
references were verified on 13 November 2026. Installation, repeatable loading,
verification and recovery: [database/README.md](database/README.md).

From the repository root, with Docker Desktop's Linux engine running:

```powershell
docker compose -f Diogo/compose.yaml up -d mongodb mongo-web
python -B Diogo/database/load.py
python -B Diogo/database/load.py --verify-only
```

Open **http://127.0.0.1:8081** and select `dmi_p1_bank` to browse collections.
In Compass, use `mongodb://127.0.0.1:27017/`. The CSV remains a separate file.
New clones must generate their source first; output files are ignored by Git.

## Earlier MongoDB prototype

`database/setup.js` and `queries/verify.js` still describe an older prototype:
5 clients, 6 accounts, 6 applications, nested fields and status history.
They are not used by the new `database/load.py` workflow, which implements the
latest four-collection model. The generator itself does not load MongoDB.

The included `compose.yaml` makes this contribution independent of the parent
workspace's lab scripts. It uses Compose project `mid-p1-diogo` and its own
named data volume. The original university lab's containers/volumes are separate.
MongoDB binds to localhost port 27017; optional mongo-express uses port 8081.

Do not run the legacy `run.py setup` against the current bank database: its
validators and fixtures belong to the earlier model. Use the documented
`database/load.py` workflow above. Legacy query/verification scripts still need
alignment before being used with scale IDs and counts. Expected prototype Q1:
C004 has L004 (18000 EUR, pending) and L005 (32000 EUR, declined).
Expected aggregates: approved 3 / 49000 EUR; declined 1 / 32000 EUR;
pending 2 / 30000 EUR. They are fixture-derived expectations, not measured results.

## Report

When opening `MID-P1` in VS Code with LaTeX Workshop, shared workspace settings
select `pdflatex` twice and rebuild on save. This recipe needs no Perl or
`latexmk`. Output is written beside `report.tex`; use LaTeX Workshop's PDF
viewer to see rebuilt content. Cleaning uses file patterns instead of `latexmk`.

```powershell
Set-Location Diogo/report
pdflatex -interaction=nonstopmode -halt-on-error report.tex
pdflatex -interaction=nonstopmode -halt-on-error report.tex
```

Pending: query execution/results, shared identifiers, colleague's contribution and joint
queries, stakeholder review and final report updates. The report contains older
design details and needs review against the current model specifications.

Course PDFs and lessons cited in the modelling documents remain outside this
Git repository. AI assistance and limitations are declared in the report;
students must review and verify the work before submission.
