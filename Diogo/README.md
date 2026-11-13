# P1 - Diogo - Banking

Banking contribution: MongoDB clients, accounts, employees and credit
applications, plus transaction movements in CSV. This is a data modelling
project; there is no banking application.

## Models and definitions

- `models/Models.drawio`: conceptual/logical diagrams.
- `logical.txt`, `physical.txt`: field definitions and storage contracts.
- `models/PhysicalModels.drawio`, physical SVGs: physical model diagrams.
- `queries/requirements.md`: BQ1/BQ2 definitions; joint queries remain pending.
- `data-generation-plan.md`: generation strategy, quotas and assumptions.
- `report/report.tex`: report draft. The saved PDF predates the relocation and
  latest documentation changes; rebuild it after reviewing the report.

## Data generation

[dataGeneration/README.md](dataGeneration/README.md) documents the offline
generator, separate reference/scale profiles, deterministic seeds, transactional
checkpoints, automatic resume, atomic exports and independent validation.
Generation and runtime tests have **not been run**; no dataset was generated.
The generator needs Python 3.11+ and its standard library. Docker and API keys
are not needed for file generation.

From the **MID-P1 repository root**, when generation is authorised:

```powershell
python Diogo/dataGeneration/generate.py run --profile scale
python Diogo/dataGeneration/generate.py status --profile scale
```

Repeat the run command to resume matching committed work. Generated outputs
and checkpoints are ignored by Git; keep the whole local run folder to resume.

## Existing MongoDB prototype

`database/setup.js` and `queries/verify.js` still describe an older prototype:
5 clients, 6 accounts, 6 applications, nested fields and status history.
They need alignment with the latest four-collection model before loading new
generator outputs. The generator does not invoke these scripts or load MongoDB.

The included `compose.yaml` makes this contribution independent of the parent
workspace's lab scripts. It uses Compose project `mid-p1-diogo` and its own
named data volume. The original university lab's containers/volumes are separate.
MongoDB binds to localhost port 27017; optional mongo-express uses port 8081.

For the **old reference prototype only**, from the repository root with Docker
Desktop's Linux engine running and these ports available:

```powershell
docker compose -f Diogo/compose.yaml up -d mongodb mongo-web
python Diogo/run.py setup
python Diogo/run.py queries
python Diogo/run.py verify
```

These commands were not executed during relocation. Expected prototype Q1:
C004 has L004 (18000 EUR, pending) and L005 (32000 EUR, declined).
Expected aggregates: approved 3 / 49000 EUR; declined 1 / 32000 EUR;
pending 2 / 30000 EUR. They are fixture-derived expectations, not measured results.

## Report

```powershell
Set-Location Diogo/report
pdflatex -interaction=nonstopmode -halt-on-error report.tex
pdflatex -interaction=nonstopmode -halt-on-error report.tex
```

Pending: data generation and validation, MongoDB schema alignment/loading,
query execution/results, shared identifiers, colleague's contribution and joint
queries, stakeholder review and final report updates. The report contains older
design details and needs review against the current model specifications.

Course PDFs and lessons cited in the modelling documents remain outside this
Git repository. AI assistance and limitations are declared in the report;
students must review and verify the work before submission.
