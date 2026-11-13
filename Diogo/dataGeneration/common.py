"""Shared formats and configuration. Importing this module generates nothing."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import platform
import random
import re
import sqlite3

VERSION = "1.0.0"
HERE = Path(__file__).resolve().parent
STAGES = ("clients", "employees", "accounts", "applications", "transactions")
CODE_FILES = ("common.py", "checkpoint.py", "builder.py", "generate.py", "validate.py")
CSV_FIELDS = ("transactionId", "accountId", "transferId", "bookingDate", "direction", "amount", "currency", "description")
EMPLOYMENT = ("employed", "self-employed", "retired", "student", "unemployed")
ID_PATTERNS = {name: re.compile(rf"^{prefix}[0-9]{{3,}}$") for name, prefix in
               (("clients", "C"), ("employees", "E"), ("accounts", "A"), ("applications", "L"), ("transactions", "T"), ("transfers", "TR"))}
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class GenerationError(Exception):
    """An actionable configuration, checkpoint or validation failure."""


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def pretty(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise GenerationError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(GenerationError(f"Invalid JSON number: {value}")))
    except (OSError, ValueError) as exc:
        raise GenerationError(f"Cannot read JSON {path}: {exc}") from exc


def file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def iso_instant(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GenerationError(f"Expected UTC timestamp ending in Z: {value!r}")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GenerationError(f"Invalid timestamp: {value!r}") from exc
    if result.microsecond % 1000:
        raise GenerationError("BSON Date supports millisecond precision")
    return result


def money(cents: int, separator=".") -> str:
    if type(cents) is not int or cents < 0:
        raise GenerationError(f"Expected non-negative integer cents: {cents!r}")
    return f"{cents // 100}{separator}{cents % 100:02d}"


def cents(value: str, separator=".") -> int:
    pattern = r"(0|[1-9][0-9]*)" + re.escape(separator) + r"[0-9]{2}"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise GenerationError(f"Invalid monetary representation: {value!r}")
    whole, fraction = value.split(separator)
    return int(whole) * 100 + int(fraction)


def rng_for(config: dict, stage: str, unit: int | str = "plan") -> random.Random:
    material = f"{config['seed']}:{config['stageOffsets'][stage]}:{stage}:{unit}".encode("ascii")
    return random.Random(int.from_bytes(sha256(material).digest(), "big"))


def weighted(rng: random.Random, weights: dict):
    total = sum(weights.values())
    pick = rng.randrange(total)
    for value, weight in sorted(weights.items()):
        pick -= weight
        if pick < 0:
            return value
    raise GenerationError("No positive sampling weight")


def identifier(prefix: str, number: int, width: int) -> str:
    if number < 1 or len(str(number)) > width:
        raise GenerationError(f"Identifier {prefix}{number} does not fit width {width}")
    return f"{prefix}{number:0{width}d}"


def expanded(counts: dict) -> list:
    return [key for key in sorted(counts) for _ in range(counts[key])]


def months_between(start: str, end: str) -> list[tuple[int, int]]:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    result = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        result.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def validate_config(config: dict, catalogue: dict) -> None:
    """Validate supported scenario constraints without generating any records."""
    def need(condition, message):
        if not condition:
            raise GenerationError(message)

    def counts(values, label):
        need(isinstance(values, dict) and values, f"Missing {label}")
        need(all(type(n) is int and n >= 0 for n in values.values()), f"Invalid {label}")

    try:
        need(config["schemaVersion"] == 1, "Unsupported configuration schemaVersion")
        need(type(config["seed"]) is int, "seed must be an integer")
        need(type(config["idWidth"]) is int and config["idWidth"] >= 3, "idWidth must be >= 3")
        need(config["currency"] == "EUR", "Only EUR is supported")
        for name in ("plan", *STAGES):
            need(type(config["stageOffsets"][name]) is int, f"Invalid stage seed offset: {name}")
        dates = {key: date.fromisoformat(config[key]) for key in
                 ("observationStart", "observationEnd", "accountOpeningStart", "accountOpeningEnd", "queryPeriodStart", "queryPeriodEnd")}
        need(all(parsed.isoformat() == config[key] for key, parsed in dates.items()), "Configuration dates must use YYYY-MM-DD")
        need(dates["accountOpeningStart"] <= dates["accountOpeningEnd"] <= dates["observationEnd"], "Invalid opening-date range")
        need(dates["accountOpeningStart"] < dates["observationStart"] <= dates["observationEnd"], "Need pre-period opening dates")
        need(dates["observationStart"] <= dates["queryPeriodStart"] <= dates["queryPeriodEnd"] < dates["observationEnd"], "Invalid query/observation periods")
        n = config["clients"]["count"]
        need(type(n) is int and n >= 10, "At least 10 clients are needed for reserved cases")
        counts(config["clients"]["employmentCounts"], "employment counts")
        need(set(config["clients"]["employmentCounts"]) == set(EMPLOYMENT), "Employment categories must match model")
        need(sum(config["clients"]["employmentCounts"].values()) == n, "Employment counts do not sum to clients.count")
        for status in EMPLOYMENT:
            bands = config["clients"]["incomeBandsCents"][status]
            need(bool(bands), f"No income bands: {status}")
            for low, high, weight in bands:
                need(all(type(v) is int for v in (low, high, weight)) and 0 <= low <= high < 10**34 and weight > 0, f"Invalid income band: {status}")
        need(type(config["employees"]["count"]) is int and config["employees"]["count"] >= 2, "Need at least two employees")
        owners = config["accounts"]["ownershipCounts"]
        counts(owners, "ownership counts")
        need(all(key.isdigit() and int(key) >= 1 and str(int(key)) == key for key in owners), "Ownership keys must be canonical positive integers")
        need(sum(owners.values()) == n, "Ownership counts do not sum to client count")
        account_count = sum(int(k) * v for k, v in owners.items())
        counts(config["accounts"]["statusCounts"], "account statuses")
        need(set(config["accounts"]["statusCounts"]) == {"active", "blocked", "closed"}, "Invalid account status categories")
        need(sum(config["accounts"]["statusCounts"].values()) == account_count, "Account statuses do not sum to account count")
        weights = config["accounts"]["extraAccountTypeWeights"]
        counts(weights, "account type weights")
        need(set(weights) == {"current", "savings"} and sum(weights.values()) > 0, "Invalid account type weights")
        apps = config["applications"]
        need(type(apps["count"]) is int and apps["count"] >= 5, "Need at least five application positions")
        need(type(apps["clientsWithoutApplications"]) is int, "clientsWithoutApplications must be an integer")
        need(type(apps["unassignedPending"]) is int and apps["unassignedPending"] >= 0, "Invalid unassigned count")
        for label in ("statusCounts", "purposeCounts"):
            counts(apps[label], label)
            need(sum(apps[label].values()) == apps["count"], f"{label} do not sum to applications.count")
        need(set(apps["statusCounts"]) == {"pending", "approved", "declined"}, "Invalid application statuses")
        need(apps["statusCounts"]["pending"] >= apps["unassignedPending"] + 1 and apps["statusCounts"]["declined"] >= 1, "Insufficient pending/declined quota for reserved cases")
        need(1 <= apps["clientsWithoutApplications"] <= n - 2, "Invalid no-application client count")
        need(apps["count"] >= n - apps["clientsWithoutApplications"] + 1, "Insufficient applications for active-client coverage")
        need(apps["count"] - apps["unassignedPending"] >= config["employees"]["count"] - 1, "Need one assignment per working employee")
        for purpose, spec in apps["purposes"].items():
            low, high = spec["amountCents"]
            need(type(low) is int and type(high) is int and 1 <= low <= high < 10**34, f"Invalid principal range: {purpose}")
            need(spec["terms"] and all(type(t) is int and 1 <= t < 2**31 for t in spec["terms"]), f"Invalid terms: {purpose}")
        need(set(apps["purposes"]) == set(apps["purposeCounts"]), "Purpose specifications differ from quotas")
        for purpose, amount in (("home_improvement", 1800000), ("debt_consolidation", 3200000)):
            need(apps["purposeCounts"].get(purpose, 0) >= 1, f"Missing reserved purpose: {purpose}")
            low, high = apps["purposes"][purpose]["amountCents"]
            need(low <= amount <= high, f"Reserved amount outside {purpose} range")
        for field in ("pendingStart", "decidedEnd", "unassignedStart"):
            day = date.fromisoformat(apps[field])
            need(day.isoformat() == apps[field], f"{field} must use YYYY-MM-DD")
            need(dates["observationStart"] <= day <= dates["observationEnd"], f"Invalid {field}")
        need(apps["pendingStart"] <= apps["unassignedStart"], "Unassigned window must lie inside pending window")
        tx = config["transactions"]
        for field in ("recurringDay", "recurringVariationPercent", "clientsWithoutAnyMovements", "clientsWithoutPeriodMovements", "unusedAccountsMinimum"):
            need(type(tx[field]) is int, f"{field} must be an integer")
        counts(tx["recurringClients"], "recurring client quotas")
        need(set(tx["recurringClients"]) == {"employed", "retired"}, "Recurring categories must be employed/retired")
        for status, amount in tx["recurringClients"].items():
            need(config["clients"]["employmentCounts"][status] >= amount, f"Not enough clients for recurring {status}")
        need(1 <= tx["recurringDay"] <= 28, "Recurring day must be 1..28")
        need(0 <= tx["recurringVariationPercent"] < 100, "Invalid recurring variation")
        need(1 <= tx["clientsWithoutAnyMovements"] <= tx["clientsWithoutPeriodMovements"] < n - 1, "Invalid zero-activity client quotas")
        need(config["accounts"]["statusCounts"]["active"] >= sum(tx["recurringClients"].values()) + 1, "Insufficient active accounts for protected cases")
        need(0 <= tx["unusedAccountsMinimum"] < account_count - sum(tx["recurringClients"].values()) - 1, "Invalid unused-account minimum")
        counts(tx["ordinaryCounts"], "ordinary movement counts")
        need(set(tx["ordinaryCounts"]) == {"deposit", "purchase", "withdrawal", "fee"}, "Invalid ordinary movement categories")
        need(tx["ordinaryCounts"]["purchase"] >= 4, "Need four reserved purchase boundary cases")
        need(len(tx["boundaryDates"]) == 4 and len(set(tx["boundaryDates"])) == 4, "Need four different boundary dates")
        for value in tx["boundaryDates"]:
            parsed = date.fromisoformat(value)
            need(parsed.isoformat() == value and dates["observationStart"] <= parsed <= dates["observationEnd"], "Boundary must use YYYY-MM-DD within observation period")
        need(tx["boundaryDates"] == [(dates["queryPeriodStart"] - timedelta(days=1)).isoformat(), config["queryPeriodStart"], config["queryPeriodEnd"], (dates["queryPeriodEnd"] + timedelta(days=1)).isoformat()], "Boundary dates must bracket query period")
        for name, (low, high) in tx["amountRangesCents"].items():
            need(type(low) is int and type(high) is int and 1 <= low <= high, f"Invalid movement amount range: {name}")
        low, high = tx["amountRangesCents"]["purchase"]
        need(all(low <= value <= high for value in (1001, 2550, 9900, 1200)), "Purchase range must contain reserved boundary amounts")
        need(set(tx["amountRangesCents"]) == {"deposit", "purchase", "withdrawal", "fee", "transfer"}, "Missing movement amount range")
        need(type(tx["withdrawalStepCents"]) is int and tx["withdrawalStepCents"] > 0, "Invalid withdrawal step")
        low, high = tx["amountRangesCents"]["withdrawal"]
        step = tx["withdrawalStepCents"]
        need((low + step - 1) // step <= high // step, "Withdrawal range contains no supported step")
        for name in ("sameClientTransfers", "differentClientTransfers"):
            need(type(tx[name]) is int and tx[name] >= 0, f"Invalid {name}")
        if tx["sameClientTransfers"]:
            need(any(int(k) >= 2 and v > 0 for k, v in owners.items()), "Same-client transfers need multi-account owners")
        month_count = len(months_between(config["observationStart"], config["observationEnd"]))
        for year, month in months_between(config["observationStart"], config["observationEnd"]):
            day = date(year, month, tx["recurringDay"])
            need(dates["observationStart"] <= day <= dates["observationEnd"], "Observation window must contain every recurring day")
        row_count = month_count * sum(tx["recurringClients"].values()) + sum(tx["ordinaryCounts"].values()) + 2 * (tx["sameClientTransfers"] + tx["differentClientTransfers"])
        need(max(n, account_count, apps["count"], row_count, config["employees"]["count"]) < 10 ** config["idWidth"], "idWidth too short for target counts")
        need(catalogue["firstNames"] and catalogue["lastNames"], "Empty fictional-name catalogue")
        for name in ("employed", "retired", "deposit", "purchase", "withdrawal", "fee", "transferOut", "transferIn"):
            need(catalogue["descriptions"][name] and all(isinstance(x, str) and x.strip() == x and x for x in catalogue["descriptions"][name]), f"Invalid descriptions: {name}")
        for status, count in tx["recurringClients"].items():
            if count:
                need(all(band[0] >= 12 for band in config["clients"]["incomeBandsCents"][status]), f"Recurring {status} clients need positive monthly income")
    except (KeyError, TypeError, ValueError) as exc:
        raise GenerationError(f"Malformed configuration: {exc}") from exc


def load_inputs(config_path: Path):
    config, catalogue, reference = read_json(config_path), read_json(HERE / "catalogues.json"), read_json(HERE / "reference.json")
    validate_config(config, catalogue)
    return config, catalogue, reference


def identity(config: dict, catalogue: dict, reference: dict, profile: str) -> dict:
    code = {name: file_hash(HERE / name) for name in CODE_FILES}
    result = {"generatorVersion": VERSION, "profile": profile, "configuration": config,
              "catalogueSha256": sha256(canonical(catalogue)).hexdigest(),
              "referenceSha256": sha256(canonical(reference)).hexdigest(), "codeSha256": code,
              "runtime": {"implementation": platform.python_implementation(), "python": platform.python_version(), "sqlite": sqlite3.sqlite_version}}
    result["fingerprint"] = sha256(canonical(result)).hexdigest()
    return result


def to_extended(collection: str, record: dict) -> dict:
    result = dict(record)
    for field in ({"clients": ("annualIncome",), "applications": ("requestedAmount",)}.get(collection, ())):
        result[field] = {"$numberDecimal": money(result[field])}
    for field in ({"accounts": ("openedAt",), "applications": ("submittedAt",)}.get(collection, ())):
        delta = iso_instant(result[field]) - EPOCH
        millis = delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000
        result[field] = {"$date": {"$numberLong": str(millis)}}
    if collection == "applications":
        result["termMonths"] = {"$numberInt": str(result["termMonths"])}
    return result


def from_extended(collection: str, record: dict) -> dict:
    if not isinstance(record, dict):
        raise GenerationError("Extended JSON record must be an object")
    result = dict(record)
    for field in ({"clients": ("annualIncome",), "applications": ("requestedAmount",)}.get(collection, ())):
        value = result.get(field)
        if not isinstance(value, dict) or set(value) != {"$numberDecimal"}:
            raise GenerationError(f"{collection}.{field} must have Decimal128 Extended JSON type")
        result[field] = cents(value["$numberDecimal"])
    for field in ({"accounts": ("openedAt",), "applications": ("submittedAt",)}.get(collection, ())):
        value = result.get(field)
        if not isinstance(value, dict) or set(value) != {"$date"} or not isinstance(value["$date"], dict) or set(value["$date"]) != {"$numberLong"}:
            raise GenerationError(f"{collection}.{field} must have canonical BSON Date Extended JSON type")
        literal = value["$date"]["$numberLong"]
        if not isinstance(literal, str) or re.fullmatch(r"-?[0-9]+", literal) is None:
            raise GenerationError(f"Invalid BSON Date milliseconds: {literal!r}")
        instant = EPOCH + timedelta(milliseconds=int(literal))
        result[field] = instant.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    if collection == "applications":
        value = result.get("termMonths")
        if not isinstance(value, dict) or set(value) != {"$numberInt"}:
            raise GenerationError("termMonths must have BSON int Extended JSON type")
        literal = value["$numberInt"]
        if not isinstance(literal, str) or re.fullmatch(r"-?[0-9]+", literal) is None or not -2**31 <= int(literal) < 2**31:
            raise GenerationError("Invalid BSON 32-bit integer")
        result["termMonths"] = int(literal)
    return result


def sync_directory(path: Path):
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def atomic_write(path: Path, writer):
    """Only replace this run's own partial export after flushing its bytes."""
    partial = path.with_name(path.name + ".part")
    with partial.open("wb") as stream:
        writer(stream)
        stream.flush()
        os.fsync(stream.fileno())
    digest = file_hash(partial)
    if path.exists():
        if file_hash(path) != digest:
            raise GenerationError(f"Existing export differs; refusing overwrite: {path}")
        partial.unlink()
    else:
        os.replace(partial, path)
        sync_directory(path.parent)
    return digest
