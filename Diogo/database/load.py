"""Load validated banking exports into the project Docker MongoDB; never overwrite data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT / "dataGeneration"))
from common import GenerationError, file_hash, identity, load_inputs, read_json
from validate import validate_outputs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Completed run; defaults to current profile/config/code/runtime identity")
    parser.add_argument("--profile", choices=("scale", "reference"), default="scale", help="Profile used to locate a default --source")
    parser.add_argument("--database", help="Default: dmi_p1_bank (scale), dmi_p1_bank_reference (reference)")
    parser.add_argument("--verify-only", action="store_true", help="Read-only stored-source verification")
    args = parser.parse_args(argv)
    try:
        if args.source is None:
            config, catalogue, reference = load_inputs(PROJECT / "dataGeneration" / "config.json")
            run_identity = identity(config, catalogue, reference, args.profile)
            source = PROJECT / "dataGeneration" / "outputs" / args.profile / run_identity["fingerprint"][:16]
        else:
            source = args.source.resolve()
        if not (source / "manifest.json").is_file():
            raise GenerationError(f"No completed generated source at {source}; run generate.py first or provide --source")
        report, _ = validate_outputs(source, require_manifest=True)
        if not report["valid"]:
            raise GenerationError("Source validation failed: " + "; ".join(report["errors"][:5]))
        database = args.database or ("dmi_p1_bank" if report["profile"] == "scale" else "dmi_p1_bank_reference")
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,62}", database) is None or database in {"admin", "config", "local"}:
            raise GenerationError("Use a dedicated banking database name; system databases are forbidden")
        manifest = read_json(source / "manifest.json")
        request = {"database": database, "fingerprint": report["fingerprint"], "verifyOnly": args.verify_only,
                   "documents": {name: [json.loads(line) for line in (source / (name + ".jsonl")).read_text(encoding="utf-8").splitlines()]
                                 for name in ("clients", "employees", "accounts", "applications")}}
        script = (HERE / "schema.js").read_text(encoding="utf-8")
        script += "\nconst request = " + json.dumps(request, ensure_ascii=True, allow_nan=False) + ";\n"
        script += (HERE / "import.js").read_text(encoding="utf-8")
        command = ["docker", "compose", "-f", str(PROJECT / "compose.yaml"), "exec", "-T", "mongodb",
                   "mongosh", "--quiet", "--file", "/dev/stdin"]
        print(f"Validated {report['profile']} source. Target: {database}; verify-only: {args.verify_only}", flush=True)
        result = subprocess.run(command, input=script.encode("utf-8"), capture_output=True, timeout=180)
        output, errors = result.stdout.decode("utf-8", errors="replace"), result.stderr.decode("utf-8", errors="replace")
        if result.returncode:
            raise GenerationError("MongoDB operation failed; committed batches remain safe to retry.\n" + output + errors)
        lines = [line[len("__BANK_RESULT__"):] for line in output.splitlines() if line.startswith("__BANK_RESULT__")]
        if len(lines) != 1:
            raise GenerationError("No unambiguous MongoDB verification result: " + output + errors)
        stored = json.loads(lines[0])
        stored.update({"checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "sourceSha256": report["sourceSha256"], "datasetId": manifest["datasetId"],
                       "connectionUri": "mongodb://127.0.0.1:27017/" + database,
                       "loaderSha256": {name: file_hash(HERE / name) for name in ("load.py", "schema.js", "import.js")},
                       "csvImported": False})
        print(json.dumps(stored, ensure_ascii=False, indent=2))
        if not args.verify_only:
            receipt = source / "mongodb-load-report.json"
            temporary = receipt.with_name(receipt.name + ".part")
            temporary.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(receipt)
            print(f"Load report: {receipt}")
        print("Verified. CSV remains the separate file-based source.")
        return 0
    except (GenerationError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
