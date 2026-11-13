"""Independently validate exported sources. This module never generates data."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys
import unicodedata

from common import (CODE_FILES, CSV_FIELDS, EMPLOYMENT, GenerationError, ID_PATTERNS, STAGES,
                    _unique_object, canonical, cents, file_hash, from_extended,
                    iso_instant, money, months_between, pretty, read_json,
                    validate_config)

FIELDS = {
    "clients": {"_id", "name", "email", "annualIncome", "employmentStatus"},
    "employees": {"_id", "name"},
    "accounts": {"_id", "clientId", "accountType", "currency", "openedAt", "status"},
    "applications": {"_id", "clientId", "employeeId", "requestedAmount", "termMonths", "purpose", "submittedAt", "status"},
    "transactions": set(CSV_FIELDS),
}
DATA_FILES = [name + ".jsonl" for name in STAGES[:-1]] + ["transactions.csv"]


class Problems:
    def __init__(self):
        self.count = 0
        self.messages = []

    def add(self, message):
        self.count += 1
        if len(self.messages) < 100:
            self.messages.append(str(message))

    def need(self, condition, message):
        if not condition:
            self.add(message)


def read_sources(directory: Path, problems: Problems) -> dict:
    result = {stage: [] for stage in STAGES}
    for stage in STAGES[:-1]:
        path = directory / (stage + ".jsonl")
        try:
            raw = path.read_bytes()
            if raw.startswith(b"\xef\xbb\xbf"):
                raise GenerationError("BOM is not allowed")
            text = raw.decode("utf-8", errors="strict")
            problems.need(not text or text.endswith("\n"), f"{path.name}: final newline missing")
            lines = text.split("\n")
            if lines and lines[-1] == "":
                lines.pop()
            for number, line in enumerate(lines, 1):
                try:
                    if not line.strip():
                        raise GenerationError("Blank record")
                    value = json.loads(line, object_pairs_hook=_unique_object,
                                       parse_constant=lambda x: (_ for _ in ()).throw(GenerationError(f"Invalid JSON number {x}")))
                    result[stage].append(from_extended(stage, value))
                except (ValueError, TypeError, KeyError, OverflowError, GenerationError) as exc:
                    problems.add(f"{path.name}:{number}: {exc}")
        except (OSError, UnicodeError, GenerationError) as exc:
            problems.add(f"{path.name}: {exc}")
    path = directory / "transactions.csv"
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise GenerationError("CSV must be UTF-8 without BOM")
        problems.need(raw.endswith(b"\r\n"), "CSV final CRLF missing")
        stripped = raw.replace(b"\r\n", b"")
        problems.need(b"\n" not in stripped and b"\r" not in stripped, "CSV export requires CRLF record endings")
        reader = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""), delimiter=";", quotechar='"', doublequote=True, strict=True)
        header = next(reader, [])
        if header != list(CSV_FIELDS):
            raise GenerationError("Wrong CSV header/order")
        for number, values in enumerate(reader, 2):
            try:
                if len(values) != len(CSV_FIELDS):
                    raise GenerationError(f"Expected eight fields, got {len(values)}")
                row = dict(zip(CSV_FIELDS, values))
                literal = row["bookingDate"]
                if re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", literal) is None:
                    raise GenerationError("Date must be DD/MM/YYYY")
                row["bookingDate"] = datetime.strptime(literal, "%d/%m/%Y").date().isoformat()
                row["amount"] = cents(row["amount"], ",")
                result["transactions"].append(row)
            except (ValueError, GenerationError) as exc:
                problems.add(f"transactions.csv:{number}: {exc}")
        problems.need(raw.count(b"\r\n") == len(result["transactions"]) + 1, "CSV has blank/multiline/unreadable records")
    except (OSError, UnicodeError, csv.Error, GenerationError) as exc:
        problems.add(f"transactions.csv: {exc}")
    return result


def check_records(config: dict, reference: dict, plan: dict, rows: dict, problems: Problems):
    profile = plan["profile"]
    records = {}
    for stage in STAGES:
        records[stage] = {}
        for offset, row in enumerate(rows[stage]):
            location = f"{stage}[{offset + 1}]"
            try:
                required = FIELDS[stage] - ({"employeeId"} if stage == "applications" else set())
                problems.need(required <= set(row) <= FIELDS[stage], f"{location}: missing or undeclared fields")
                key = row["transactionId"] if stage == "transactions" else row["_id"]
                problems.need(isinstance(key, str) and ID_PATTERNS[stage].fullmatch(key) is not None, f"{location}: invalid identifier")
                if profile == "scale" and isinstance(key, str):
                    prefix_length = 1
                    problems.need(len(key[prefix_length:]) == config["idWidth"], f"{location}: inconsistent scale identifier width")
                problems.need(key not in records[stage], f"{location}: duplicate identifier {key}")
                records[stage][key] = row
                for field, value in row.items():
                    if field not in {"annualIncome", "requestedAmount", "termMonths", "amount"}:
                        problems.need(isinstance(value, str), f"{location}.{field}: expected string")
                for field in ({"clients": ["name"], "employees": ["name"], "applications": ["purpose"], "transactions": ["description"]}.get(stage, [])):
                    problems.need(isinstance(row[field], str) and bool(row[field].strip()), f"{location}.{field}: blank text")
                if stage == "clients":
                    problems.need(type(row["annualIncome"]) is int and 0 <= row["annualIncome"] < 10**34, f"{location}: invalid income/precision")
                    problems.need(row["employmentStatus"] in EMPLOYMENT, f"{location}: invalid employment status")
                    problems.need(re.fullmatch(r"[^\s@]+@example\.invalid", row["email"]) is not None, f"{location}: synthetic reserved-domain email required")
                elif stage == "accounts":
                    problems.need(row["clientId"] in records["clients"], f"{location}: dangling client reference")
                    problems.need(row["accountType"] in ("current", "savings") and row["status"] in ("active", "blocked", "closed"), f"{location}: invalid account domain")
                    problems.need(row["currency"] == "EUR", f"{location}: wrong currency")
                    opening = iso_instant(row["openedAt"])
                    problems.need(not any((opening.hour, opening.minute, opening.second, opening.microsecond)), f"{location}: opening is not midnight UTC")
                    problems.need(config["accountOpeningStart"] <= opening.date().isoformat() <= config["accountOpeningEnd"], f"{location}: opening outside configured range")
                elif stage == "applications":
                    problems.need(row["clientId"] in records["clients"], f"{location}: dangling client reference")
                    problems.need("employeeId" not in row or row["employeeId"] in records["employees"], f"{location}: missing employee target")
                    problems.need(type(row["requestedAmount"]) is int and 0 < row["requestedAmount"] < 10**34, f"{location}: invalid requested amount")
                    problems.need(type(row["termMonths"]) is int and 0 < row["termMonths"] < 2**31, f"{location}: invalid term")
                    problems.need(row["status"] in ("pending", "approved", "declined"), f"{location}: invalid status")
                    day = iso_instant(row["submittedAt"]).date().isoformat()
                    problems.need(config["observationStart"] <= day <= config["observationEnd"], f"{location}: submission outside observation period")
                    if profile == "scale":
                        spec = config["applications"]["purposes"][row["purpose"]]
                        problems.need(spec["amountCents"][0] <= row["requestedAmount"] <= spec["amountCents"][1] and row["termMonths"] in spec["terms"], f"{location}: purpose range/term mismatch")
                        if "employeeId" not in row:
                            problems.need(row["status"] == "pending" and day >= config["applications"]["unassignedStart"], f"{location}: unassigned scenario mismatch")
                        elif row["status"] == "pending":
                            problems.need(day >= config["applications"]["pendingStart"], f"{location}: pending date mismatch")
                        else:
                            problems.need(day <= config["applications"]["decidedEnd"], f"{location}: decided-date mismatch")
                else:
                    account = records["accounts"][row["accountId"]]
                    day = date.fromisoformat(row["bookingDate"])
                    problems.need(account["openedAt"][:10] <= day.isoformat(), f"{location}: predates account opening")
                    problems.need(config["observationStart"] <= day.isoformat() <= config["observationEnd"], f"{location}: movement outside observation period")
                    problems.need(row["currency"] == account["currency"] == "EUR", f"{location}: currency mismatch")
                    problems.need(row["direction"] in ("IN", "OUT"), f"{location}: invalid direction")
                    problems.need(type(row["amount"]) is int and row["amount"] > 0, f"{location}: invalid amount")
                    problems.need(not row["transferId"] or ID_PATTERNS["transfers"].fullmatch(row["transferId"]) is not None, f"{location}: invalid transfer ID")
                    desc = row["description"]
                    problems.need(desc == desc.strip() and not any(unicodedata.category(c) == "Cc" for c in desc), f"{location}: padded/control-character description")
            except (KeyError, TypeError, ValueError, GenerationError) as exc:
                problems.add(f"{location}: {exc}")

    clients, accounts, applications, transactions = (records[s] for s in ("clients", "accounts", "applications", "transactions"))
    ordered = [(r.get("bookingDate", ""), r.get("transactionId", "")) for r in rows["transactions"]]
    problems.need(ordered == sorted(ordered), "CSV is not ordered by parsed booking date and transaction ID")
    ownership = Counter(row.get("clientId") for row in accounts.values())
    application_owners = Counter(row.get("clientId") for row in applications.values())
    assigned = Counter(row.get("employeeId") for row in applications.values() if "employeeId" in row)
    emails = [row.get("email") for row in clients.values()]
    problems.need(len(set(emails)) == len(emails), "Duplicate synthetic emails")
    problems.need(all(ownership[c] >= 1 for c in clients), "Some clients have no account")
    pairs, movement_owners, period_owners = defaultdict(list), Counter(), Counter()
    totals = {client: {"IN": 0, "OUT": 0} for client in clients}
    for row in transactions.values():
        try:
            owner = accounts[row["accountId"]]["clientId"]
            movement_owners[owner] += 1
            if row["transferId"]:
                pairs[row["transferId"]].append(row)
            if plan["queryStart"] <= row["bookingDate"] <= plan["queryEnd"]:
                period_owners[owner] += 1
                totals[owner][row["direction"]] += row["amount"]
        except (KeyError, TypeError):
            pass  # The malformed record is already reported above.
    same_owner = different_owner = 0
    for key, pair in pairs.items():
        problems.need(len(pair) == 2, f"Transfer {key}: expected two legs")
        if len(pair) != 2:
            continue
        a, b = pair
        problems.need(a["accountId"] != b["accountId"] and {a["direction"], b["direction"]} == {"IN", "OUT"}, f"Transfer {key}: invalid accounts/directions")
        problems.need(a["amount"] == b["amount"] and a["currency"] == b["currency"], f"Transfer {key}: amount/currency mismatch")
        if a["accountId"] in accounts and b["accountId"] in accounts:
            if accounts[a["accountId"]]["clientId"] == accounts[b["accountId"]]["clientId"]:
                same_owner += 1
            else:
                different_owner += 1

    if profile == "reference":
        expected_counts = {name: len(reference[name]) for name in STAGES[:-1]}
        expected_counts["transactions"] = sum(map(len, reference["transactionUnits"]))
    else:
        recurring_count = sum(config["transactions"]["recurringClients"].values()) * len(months_between(config["observationStart"], config["observationEnd"]))
        tx = config["transactions"]
        expected_counts = {"clients": config["clients"]["count"], "employees": config["employees"]["count"],
            "accounts": sum(int(k)*v for k, v in config["accounts"]["ownershipCounts"].items()), "applications": config["applications"]["count"],
            "transactions": recurring_count + sum(tx["ordinaryCounts"].values()) + 2*(tx["sameClientTransfers"] + tx["differentClientTransfers"])}
        problems.need(Counter(r["employmentStatus"] for r in clients.values()) == Counter(config["clients"]["employmentCounts"]), "Employment quotas differ")
        problems.need(Counter(str(ownership[c]) for c in clients) == Counter(config["accounts"]["ownershipCounts"]), "Ownership quotas differ")
        problems.need(Counter(r["status"] for r in accounts.values()) == Counter(config["accounts"]["statusCounts"]), "Account status quotas differ")
        problems.need(Counter(r["status"] for r in applications.values()) == Counter(config["applications"]["statusCounts"]), "Application status quotas differ")
        problems.need(Counter(r["purpose"] for r in applications.values()) == Counter(config["applications"]["purposeCounts"]), "Application purpose quotas differ")
        problems.need(sum("employeeId" not in r for r in applications.values()) == config["applications"]["unassignedPending"], "Unassigned quota differs")
        problems.need(sum(application_owners[c] == 0 for c in clients) == config["applications"]["clientsWithoutApplications"], "No-application client quota differs")
        problems.need(application_owners[plan["queryClientId"]] == 2, "BQ1 anchor must have exactly two applications")
        problems.need(plan["employeeWithoutApplications"] in records["employees"] and assigned[plan["employeeWithoutApplications"]] == 0, "Reserved employee received applications")
        problems.need(sum(assigned[e] == 0 for e in records["employees"]) == 1, "Expected exactly one zero-workload employee")
        problems.need(same_owner == tx["sameClientTransfers"] and different_owner == tx["differentClientTransfers"], "Transfer-owner quotas differ")
        used = {r["accountId"] for r in transactions.values()}
        problems.need(len(set(accounts)-used) >= tx["unusedAccountsMinimum"], "Unused-account minimum not met")
        problems.need(all(c in clients and movement_owners[c] == 0 for c in plan["clientsWithoutAnyMovements"]), "Reserved no-movement client has activity")
        problems.need(all(c in clients and period_owners[c] == 0 for c in plan["clientsWithoutPeriodMovements"]), "Reserved zero-period client has activity")
        problems.need(set(plan["unusedAccounts"]) <= set(accounts)-used, "Reserved unused account has activity")
        observed_dates = {r["bookingDate"] for r in transactions.values()}
        problems.need(set(tx["boundaryDates"]) <= observed_dates, "Boundary-date coverage missing")
        descriptions = [r["description"] for r in transactions.values()]
        problems.need(any(";" in d for d in descriptions) and any('"' in d for d in descriptions) and any(any(ord(c)>127 for c in d) for d in descriptions), "CSV quoting/Unicode coverage missing")
        problems.need(len(set(descriptions)) < len(descriptions), "Repeated-description case missing")
        for client in clients.values():
            bands = config["clients"]["incomeBandsCents"][client["employmentStatus"]]
            problems.need(any(a <= client["annualIncome"] <= b for a, b, _ in bands), f"Income outside configured bands: {client['_id']}")
        for owner in plan["recurringClients"]:
            account = accounts[plan["primaryAccounts"][owner]]
            problems.need(account["status"] == "active" and account["accountType"] == "current" and account["openedAt"][:10] < config["observationStart"], f"Recurring account mismatch: {owner}")
        ordinary = [r for r in transactions.values() if not r["transferId"]]
        problems.need(len(ordinary) == recurring_count + sum(tx["ordinaryCounts"].values()), "Ordinary movement count differs")
        # IDs identify the scenario allocation, independently of CSV sort order.
        indexed = {int(r["transactionId"][1:]): r for r in ordinary}
        position = 1
        for owner in plan["recurringClients"]:
            for year, month in months_between(config["observationStart"], config["observationEnd"]):
                row = indexed.get(position, {})
                problems.need(row.get("accountId") == plan["primaryAccounts"][owner] and row.get("direction") == "IN" and row.get("bookingDate") == date(year, month, tx["recurringDay"]).isoformat(), f"Recurring sequence mismatch at movement {position}")
                monthly = (Decimal(clients[owner]["annualIncome"]) / Decimal(12)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
                variation = tx["recurringVariationPercent"]
                lower = int((monthly * Decimal(100-variation) / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                upper = int((monthly * Decimal(100+variation) / Decimal(100)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
                problems.need(lower <= row.get("amount", 0) <= upper, f"Recurring income amount outside variation at {position}")
                position += 1
        for category in ("deposit", "purchase", "withdrawal", "fee"):
            low, high = tx["amountRangesCents"][category]
            for _ in range(tx["ordinaryCounts"][category]):
                row = indexed.get(position, {})
                amount = row.get("amount", 0)
                problems.need(row.get("direction") == ("IN" if category == "deposit" else "OUT") and low <= amount <= high, f"Ordinary category mismatch at movement {position}")
                if category == "withdrawal":
                    problems.need(amount % tx["withdrawalStepCents"] == 0, f"Withdrawal step mismatch at {position}")
                position += 1
    for stage, expected in expected_counts.items():
        problems.need(len(rows[stage]) == expected, f"{stage}: expected {expected} records, got {len(rows[stage])}")

    bq1 = [{"_id": r["_id"], "requestedAmountEUR": money(r["requestedAmount"]), "status": r["status"]}
           for r in sorted(applications.values(), key=lambda r: r["_id"]) if r.get("clientId") == plan["queryClientId"]]
    bq2 = [{"clientId": client, "totalIncomingEUR": money(values["IN"]), "totalOutgoingEUR": money(values["OUT"])} for client, values in sorted(totals.items())]
    if profile == "reference":
        problems.need(bq1 == reference["expected"]["BQ1"], "Reference BQ1 differs from hand-specified answer")
        problems.need(bq2 == reference["expected"]["BQ2"], "Reference BQ2 differs from hand-specified answer")
    else:
        problems.need([(r["requestedAmountEUR"], r["status"]) for r in bq1] == [("18000.00", "pending"), ("32000.00", "declined")], "Scale BQ1 reserved answer differs")
    statistics = {"counts": {s: len(rows[s]) for s in STAGES}, "employment": dict(Counter(r.get("employmentStatus") for r in clients.values())),
        "accountStatuses": dict(Counter(r.get("status") for r in accounts.values())), "applicationStatuses": dict(Counter(r.get("status") for r in applications.values())),
        "clientsWithoutApplications": sum(application_owners[c] == 0 for c in clients), "clientsWithoutPeriodMovements": sum(period_owners[c] == 0 for c in clients),
        "clientsWithoutAnyMovements": sum(movement_owners[c] == 0 for c in clients), "sameClientTransferPairs": same_owner, "differentClientTransferPairs": different_owner,
        "periodIncomingEUR": money(sum(v["IN"] for v in totals.values())), "periodOutgoingEUR": money(sum(v["OUT"] for v in totals.values()))}
    return statistics, {"BQ1": bq1, "BQ2": bq2}


def validate_outputs(directory: Path, require_manifest=False):
    problems = Problems()
    config, catalogue, reference, plan, identity = (read_json(directory / name) for name in ("config.json", "catalogues.json", "reference.json", "scenario-plan.json", "identity.json"))
    validate_config(config, catalogue)
    problems.need(config == identity["configuration"], "Configuration snapshot differs from run identity")
    problems.need(sha256(canonical(catalogue)).hexdigest() == identity["catalogueSha256"], "Catalogue snapshot differs from identity")
    problems.need(sha256(canonical(reference)).hexdigest() == identity["referenceSha256"], "Reference snapshot differs from identity")
    unsigned = {key: value for key, value in identity.items() if key != "fingerprint"}
    problems.need(sha256(canonical(unsigned)).hexdigest() == identity["fingerprint"], "Invalid identity fingerprint")
    problems.need(set(identity["codeSha256"]) == set(CODE_FILES), "Identity omits generator source files")
    for name, digest in identity["codeSha256"].items():
        if name not in CODE_FILES:
            problems.add(f"Unknown generator source file: {name}")
            continue
        path = directory / ("source-" + name)
        problems.need(path.is_file() and file_hash(path) == digest, f"Generator source snapshot mismatch: {name}")
    problems.need(plan["profile"] == identity["profile"], "Plan/profile mismatch")
    problems.need(plan["profile"] in ("scale", "reference"), "Unknown dataset profile")
    rows = read_sources(directory, problems)
    try:
        statistics, results = check_records(config, reference, plan, rows, problems)
    except (KeyError, TypeError, ValueError, GenerationError) as exc:
        problems.add(f"Dataset validation cannot continue: {exc}")
        statistics, results = {"counts": {s: len(rows[s]) for s in STAGES}}, {}
    data_hashes = {name: file_hash(directory / name) for name in DATA_FILES if (directory / name).is_file()}
    if require_manifest:
        manifest = read_json(directory / "manifest.json")
        problems.need(manifest.get("complete") is True and manifest.get("fingerprint") == identity["fingerprint"], "Manifest does not identify a completed matching run")
        for name, item in manifest.get("files", {}).items():
            if Path(name).name != name:
                problems.add("Unsafe manifest filename")
                continue
            path = directory / name
            problems.need(path.is_file() and path.stat().st_size == item["bytes"] and file_hash(path) == item["sha256"], f"Manifest checksum mismatch: {name}")
        problems.need(set(DATA_FILES) <= set(manifest.get("files", {})), "Manifest omits source files")
    report = {"valid": problems.count == 0, "errorCount": problems.count, "errors": problems.messages,
              "errorsTruncated": problems.count > len(problems.messages), "profile": plan["profile"], "fingerprint": identity["fingerprint"],
              "sourceSha256": data_hashes, "statistics": statistics,
              "scope": "Exported-file integrity and synthetic-data coherence; MongoDB loading/server-side BSON validation not executed."}
    expected = {"profile": plan["profile"], "fingerprint": identity["fingerprint"], "sourceSha256": data_hashes,
                "parameters": {"clientId": plan["queryClientId"], "periodStart": plan["queryStart"], "periodEnd": plan["queryEnd"]},
                "moneyRepresentation": "Exact EUR decimal strings", "results": results}
    return report, expected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Completed generator output directory")
    args = parser.parse_args(argv)
    try:
        report, _ = validate_outputs(args.directory.resolve(), require_manifest=True)
        print(pretty(report).decode("utf-8"))
        return 0 if report["valid"] else 1
    except (GenerationError, OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
