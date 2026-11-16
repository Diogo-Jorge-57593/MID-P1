"""Run banking Q1 in MongoDB and Q2 across live MongoDB and the validated CSV."""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "dataGeneration"))
from common import GenerationError, file_hash, identity, load_inputs, read_json
from validate import validate_outputs


def movement_totals(clients, accounts, movements, start, end):
    """Aggregate each movement once; preserve all clients and both transfer legs."""
    totals = {row["_id"]: {"IN": Decimal("0.00"), "OUT": Decimal("0.00")} for row in clients}
    owners = {row["_id"]: row["clientId"] for row in accounts}
    matched = 0
    for row in movements:
        day = datetime.strptime(row["bookingDate"], "%d/%m/%Y").date()
        if start <= day <= end:
            owner = owners[row["accountId"]]
            totals[owner][row["direction"]] += Decimal(row["amount"].replace(",", "."))
            matched += 1
    results = [{"clientId": client,
                "totalIncomingEUR": format(values["IN"], ".2f"),
                "totalOutgoingEUR": format(values["OUT"], ".2f")}
               for client, values in sorted(totals.items())]
    return results, matched


def read_mongodb(database, client):
    # JSON literals prevent database/client parameters from becoming JavaScript code.
    script = "const bank = db.getSiblingDB(" + json.dumps(database) + ");\n"
    script += "const client = " + json.dumps(client) + ";\n"
    script += """
const documents = {};
for (const name of ['clients', 'employees', 'accounts', 'applications']) {
    documents[name] = bank.getCollection(name).find({}).sort({_id: 1}).toArray();
}
const q1 = bank.applications.find(
    {clientId: client}, {_id: 1, requestedAmount: 1, status: 1}
).sort({_id: 1}).toArray();
print('__BANK_QUERIES__' + EJSON.stringify({
    serverVersion: db.version(), documents, q1
}, {relaxed: false}));
"""
    command = ["docker", "compose", "-f", str(PROJECT / "compose.yaml"),
               "exec", "-T", "mongodb", "mongosh", "--quiet", "--file", "/dev/stdin"]
    result = subprocess.run(command, input=script.encode("utf-8"), capture_output=True, timeout=120)
    output = result.stdout.decode("utf-8", errors="replace")
    if result.returncode:
        raise GenerationError("MongoDB query failed: " + output + result.stderr.decode("utf-8", errors="replace"))
    lines = [line.removeprefix("__BANK_QUERIES__") for line in output.splitlines()
             if line.startswith("__BANK_QUERIES__")]
    if len(lines) != 1:
        raise GenerationError("MongoDB did not return an unambiguous query result")
    return json.loads(lines[0])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Completed generated run directory")
    parser.add_argument("--profile", choices=("scale", "reference"), default="scale")
    parser.add_argument("--database", help="Defaults to the selected profile's database")
    parser.add_argument("--output", type=Path, default=PROJECT / "queries" / "results")
    args = parser.parse_args(argv)
    try:
        if args.source is None:
            config, catalogue, reference = load_inputs(PROJECT / "dataGeneration" / "config.json")
            fingerprint = identity(config, catalogue, reference, args.profile)["fingerprint"]
            source = PROJECT / "dataGeneration" / "outputs" / args.profile / fingerprint[:16]
        else:
            source = args.source.resolve()
        report, _ = validate_outputs(source, require_manifest=True)
        if not report["valid"]:
            raise GenerationError("Source validation failed: " + "; ".join(report["errors"][:5]))
        expected = read_json(source / "expected-query-results.json")
        if (expected["fingerprint"] != report["fingerprint"]
                or expected["sourceSha256"] != report["sourceSha256"]):
            raise GenerationError("Expected answers do not identify the validated source")
        params = expected["parameters"]
        database = args.database or ("dmi_p1_bank" if report["profile"] == "scale" else "dmi_p1_bank_reference")
        stored = read_mongodb(database, params["clientId"])
        for name, rows in stored["documents"].items():
            original = [json.loads(line) for line in (source / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()]
            if rows != sorted(original, key=lambda row: row["_id"]):
                raise GenerationError(f"Stored {name} differs from selected source; load the matching dataset first")
        q1 = [{"_id": row["_id"],
               "requestedAmountEUR": format(Decimal(row["requestedAmount"]["$numberDecimal"]), ".2f"),
               "status": row["status"]} for row in stored["q1"]]
        start, end = date.fromisoformat(params["periodStart"]), date.fromisoformat(params["periodEnd"])
        with (source / "transactions.csv").open(encoding="utf-8", newline="") as stream:
            q2, matched = movement_totals(stored["documents"]["clients"], stored["documents"]["accounts"],
                                         csv.DictReader(stream, delimiter=";", strict=True), start, end)
        if any(file_hash(source / name) != digest for name, digest in report["sourceSha256"].items()):
            raise GenerationError("Source files changed during query execution")
        if q1 != expected["results"]["BQ1"] or q2 != expected["results"]["BQ2"]:
            raise GenerationError("Actual query results differ from the saved expected answers")
        receipt = {"verified": True, "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "database": database, "serverVersion": stored["serverVersion"], "profile": report["profile"],
                   "datasetId": read_json(source / "manifest.json")["datasetId"],
                   "sourceFingerprint": report["fingerprint"], "sourceSha256": report["sourceSha256"],
                   "runnerSha256": file_hash(Path(__file__)), "parameters": params,
                   "results": {"Q1": q1, "Q2": q2},
                   "summary": {"q1Rows": len(q1), "q2Rows": len(q2), "periodMovements": matched,
                               "zeroActivityClients": sum(row["totalIncomingEUR"] == row["totalOutgoingEUR"] == "0.00" for row in q2),
                               "totalIncomingEUR": format(sum((Decimal(row["totalIncomingEUR"]) for row in q2), Decimal("0.00")), ".2f"),
                               "totalOutgoingEUR": format(sum((Decimal(row["totalOutgoingEUR"]) for row in q2), Decimal("0.00")), ".2f")}}
        output = args.output.resolve()
        if output == source or source in output.parents:
            raise GenerationError("Save query results outside the frozen generation run")
        output.mkdir(parents=True, exist_ok=True)
        # Profile-specific names keep reference and scale evidence separate.
        prefix = report["profile"]
        json_path = output / (prefix + "-results.json")
        temporary = json_path.with_suffix(".json.part")
        temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(json_path)
        csv_path = output / (prefix + "-q2.csv")
        temporary = csv_path.with_suffix(".csv.part")
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=["clientId", "totalIncomingEUR", "totalOutgoingEUR"], delimiter=";")
            writer.writeheader()
            writer.writerows(q2)
        temporary.replace(csv_path)
        print("Q1:", json.dumps(q1, ensure_ascii=False))
        print("Q2 first five:", json.dumps(q2[:5], ensure_ascii=False))
        print("Summary:", json.dumps(receipt["summary"]))
        print("PASS: actual Q1 and all Q2 rows match saved expected results.")
        print("Evidence:", json_path)
        print("Full Q2 table:", csv_path)
        return 0
    except (GenerationError, OSError, ValueError, KeyError, TypeError, ArithmeticError,
            csv.Error, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
