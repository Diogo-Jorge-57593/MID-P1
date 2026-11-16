# MongoDB installation, loading and viewing

MongoDB runs in the project's Docker container. Docker Desktop with its Linux
engine, Docker Compose and Python 3.11+ are prerequisites. Python uses only its
standard library; the container supplies MongoDB and mongosh.

## Start and load

Run from the **MID-P1 repository root**:

```powershell
# Start MongoDB and its browser viewer. First run downloads missing images.
docker compose -f Diogo/compose.yaml up -d mongodb mongo-web

# Generate/reuse the current full source if this clone has no output files.
python -B Diogo/dataGeneration/generate.py run --profile scale

# Validate the generated sources, create schemas/indexes, import, then verify.
python -B Diogo/database/load.py

# Read-only verification of the stored source.
python -B Diogo/database/load.py --verify-only

# Check running services.
docker compose -f Diogo/compose.yaml ps
```

The loader finds the current scale run using configuration/code/runtime identity.
For an existing run created with other pinned settings, provide its path:

```powershell
python -B Diogo/database/load.py --source Diogo/dataGeneration/outputs/scale/27ff7c5b1b33fa7c
```

Scale defaults to database `dmi_p1_bank`. A separately generated reference run
can be loaded with `--profile reference`, defaulting to `dmi_p1_bank_reference`.
Use `--database <name>` for another dedicated database. System databases are
rejected. Current measured scale counts: 500 clients, 25 employees, 1,000
accounts and 750 applications. CSV remains a separate file source.

## View documents

Open **http://127.0.0.1:8081** and select `dmi_p1_bank`, then `clients`,
`employees`, `accounts` or `applications`. Mongo-express provides a browser
view of the actual stored documents, collections and indexes.

Alternatively, in MongoDB Compass choose **Add New Connection**, paste:

```text
mongodb://127.0.0.1:27017/
```

Connect, expand `dmi_p1_bank`, open a collection and select its Documents tab.
For example, filter `applications` by `{ "clientId": "C000004" }` to inspect
the two documented BQ1 cases. Compass is optional; mongo-express is already
included. This local project connection uses no credentials.

## Safety, types and recovery

- Source validation, snapshot checks and manifest hashes run before database
  operations. Schema definitions are in `schema.js`; operation logic is in
  `import.js`, invoked through `load.py`.
- Full preflight rejects unrelated collections, incompatible validators/indexes,
  unexpected IDs and altered documents before making any changes.
- Data loads in dependency order: clients, employees, accounts, applications.
  Batches contain up to 100 records. A retry compares every existing document
  against its source and inserts only missing IDs. There is no drop, replacement
  or automatic migration of existing data.
- Extended JSON is deserialised to BSON. Actual stored Decimal128, Date and int
  types are checked, along with exact document equality, counts, references,
  minimum account ownership and pending-only unassigned applications.
- Collections use strict/error JSON Schema validation and the indexes defined
  by the physical model. The application validator requires an employee for
  approved/declined requests.
- The latest load receipt is saved as `mongodb-load-report.json` inside the
  source run, including database/server version, source and loader hashes,
  counts, BSON types and reference checks. It is operational evidence added
  after generation, outside the original source manifest's file list.
- Docker volume `mid-p1-diogo_mongodb-data` persists database contents outside
  the repository. Original `mdi-lab` containers/volumes are separate.

To stop these services while retaining data:

```powershell
docker compose -f Diogo/compose.yaml stop
```

`setup.js` is an earlier fixture prototype and is **not** used by this loader.
The old `run.py setup` and fixture-specific `queries/verify.js` workflow must
not be used as verification of the scale source. Query execution is separate
from this stored-source verification.

## Documentation

Verified on 13 November 2026 with MongoDB 8.0.32: all 2,275 stored documents,
counts, exact source equality, indexes, Decimal128/Date/int types and reference
checks passed. A repeated load inserted zero records. The separate read-only
verify command passed. The browser viewer returned HTTP 200 and displayed
generated client `C000001` (Clara Baptista Coelho).

- [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker Compose](https://docs.docker.com/compose/gettingstarted/)
- [Compass connection instructions](https://www.mongodb.com/docs/compass/connect/)
- [EJSON deserialisation](https://www.mongodb.com/docs/mongodb-shell/reference/ejson/deserialize/)
