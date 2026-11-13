"""Offline synthetic-source generator. Only the explicit 'run' command writes data."""
from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import io
from pathlib import Path
import sqlite3
import sys

from builder import Builder, make_plan, stage_sizes
from checkpoint import Store, check_output_directory, read_status, writer_lock
from common import (CODE_FILES, CSV_FIELDS, GenerationError, HERE, STAGES, VERSION, canonical,
                    identity, load_inputs, money, pretty, to_extended)
from validate import validate_outputs


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Value must be a positive integer")
    return number


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    for command in ("run", "status"):
        sub = commands.add_parser(command, help="Generate/resume" if command == "run" else "Inspect progress without generating")
        sub.add_argument("--profile", choices=("scale", "reference"), default="scale")
        sub.add_argument("--config", type=Path, default=HERE / "config.json")
        sub.add_argument("--output", type=Path, help="Owned run directory; default outputs/<profile>/<fingerprint-prefix>")
        if command == "run":
            sub.add_argument("--batch-size", type=positive, default=100, help="Units per durable checkpoint; a transfer pair is one unit")
            sub.add_argument("--until", choices=STAGES, help="Stop after this checkpoint stage; exports require a later run without --until")
            sub.add_argument("--stop-after-units", type=positive, help="Gracefully stop after this many newly committed units in this invocation")
    return result


def export_sources(store):
    for stage in STAGES[:-1]:
        rows = sorted(store.rows(stage), key=lambda row: row["_id"])

        def write_records(stream, rows=rows, stage=stage):
            for row in rows:
                stream.write(canonical(to_extended(stage, row)))

        store.export(stage + ".jsonl", write_records)

    transactions = sorted(store.rows("transactions"), key=lambda row: (row["bookingDate"], row["transactionId"]))

    def write_csv(stream):
        wrapper = io.TextIOWrapper(stream, encoding="utf-8", newline="", write_through=True)
        try:
            writer = csv.writer(wrapper, delimiter=";", quotechar='"', doublequote=True,
                                quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
            writer.writerow(CSV_FIELDS)
            for transaction in transactions:
                row = dict(transaction)
                year, month, day = row["bookingDate"].split("-")
                row["bookingDate"] = f"{day}/{month}/{year}"
                row["amount"] = money(row["amount"], ",")
                writer.writerow([row[field] for field in CSV_FIELDS])
            wrapper.flush()
        finally:
            wrapper.detach()  # atomic_write owns and fsyncs the underlying stream.

    store.export("transactions.csv", write_csv)


def run(args, config, catalogue, reference, run_identity, directory):
    check_output_directory(directory)
    sizes = stage_sizes(config, reference, args.profile)
    budget = args.stop_after_units
    with writer_lock(directory):
        check_output_directory(directory)
        store = Store(directory, run_identity, sizes, lambda: make_plan(config, reference, args.profile))
        try:
            for name, value in (("identity.json", run_identity), ("config.json", config),
                                ("catalogues.json", catalogue), ("reference.json", reference), ("scenario-plan.json", store.plan)):
                store.export_json(name, value)
            # Preserve exact implementation bytes for documented recovery later.
            for name in CODE_FILES:
                content = (HERE / name).read_bytes()
                if sha256(content).hexdigest() != run_identity["codeSha256"][name]:
                    raise GenerationError(f"Generator source changed after startup: {name}; restore original files before resuming")
                store.export("source-" + name, lambda stream, content=content: stream.write(content))
            for stage in STAGES:
                progress = store.progress(stage)
                if progress["completed_units"] < progress["total_units"]:
                    builder = Builder(config, catalogue, reference, args.profile, store.plan, store)
                    while progress["completed_units"] < progress["total_units"]:
                        count = min(args.batch_size, progress["total_units"] - progress["completed_units"])
                        if budget is not None:
                            count = min(count, budget)
                        start = progress["completed_units"]
                        units = [builder.unit(stage, index) for index in range(start, start + count)]
                        store.commit_units(stage, start, units)
                        progress = store.progress(stage)
                        print(f"{stage}: {progress['completed_units']}/{progress['total_units']} units; {progress['written_rows']} records committed", flush=True)
                        if budget is not None:
                            budget -= count
                            if budget == 0:
                                print("Stopped at requested unit budget. Repeat command without --stop-after-units to continue.")
                                return 0
                if args.until == stage:
                    print(f"Stopped after {stage}. Repeat run without --until to continue and export.")
                    return 0
            print("Records complete. Exporting canonical Extended JSON and CSV...", flush=True)
            export_sources(store)
            report, expected = validate_outputs(directory)
            store.export_json("quality-report.json", report)
            if not report["valid"]:
                raise GenerationError(f"Export validation failed: {report['errorCount']} errors; inspect quality-report.json")
            store.export_json("expected-query-results.json", expected)
            manifest = {"formatVersion": 1, "generatorVersion": VERSION, "profile": args.profile,
                        "fingerprint": run_identity["fingerprint"], "datasetId": run_identity["fingerprint"][:16],
                        "createdAt": store.get("startedAt"), "complete": True,
                        "counts": report["statistics"]["counts"], "files": store.exported_files(),
                        "mongoLoadingPerformed": False, "apiCallsRequired": False}
            store.export_json("manifest.json", manifest)
            verified, _ = validate_outputs(directory, require_manifest=True)
            if not verified["valid"]:
                raise GenerationError("Final manifest verification failed: " + "; ".join(verified["errors"][:5]))
            store.mark_complete()
            print(f"Complete and validated: {directory}")
            print("No MongoDB server, imports or API calls were used.")
            return 0
        finally:
            store.close()


def main(argv=None):
    args = parser().parse_args(argv)
    directory = None
    try:
        config, catalogue, reference = load_inputs(args.config.resolve())
        run_identity = identity(config, catalogue, reference, args.profile)
        directory = (args.output or HERE / "outputs" / args.profile / run_identity["fingerprint"][:16]).resolve()
        if args.command == "status":
            print(pretty(read_status(directory)).decode("utf-8"))
            return 0
        print(f"Output: {directory}", flush=True)
        print("Existing matching run resumes automatically. Ctrl+C preserves committed work.", flush=True)
        return run(args, config, catalogue, reference, run_identity, directory)
    except KeyboardInterrupt:
        print("Interrupted. Committed checkpoints preserved; repeat the same run command to resume.", file=sys.stderr)
        return 130
    except (GenerationError, OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        print(f"Generation stopped: {exc}", file=sys.stderr)
        if directory is not None:
            print(f"Run directory: {directory}", file=sys.stderr)
        print("Committed work is preserved. Resolve the error, then resume with unchanged inputs/code.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
