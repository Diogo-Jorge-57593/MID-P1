"""Deterministic scenario allocation and restartable per-unit record builders."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from common import GenerationError, STAGES, expanded, identifier, months_between, rng_for, weighted


def stage_sizes(config: dict, reference: dict, profile: str) -> dict:
    if profile == "reference":
        result = {name: (len(reference[name]), len(reference[name])) for name in STAGES[:-1]}
        groups = reference["transactionUnits"]
        result["transactions"] = (len(groups), sum(map(len, groups)))
        return result
    accounts = sum(int(k) * v for k, v in config["accounts"]["ownershipCounts"].items())
    tx = config["transactions"]
    recurring = sum(tx["recurringClients"].values()) * len(months_between(config["observationStart"], config["observationEnd"]))
    ordinary = recurring + sum(tx["ordinaryCounts"].values())
    transfers = tx["sameClientTransfers"] + tx["differentClientTransfers"]
    return {"clients": (config["clients"]["count"],) * 2, "employees": (config["employees"]["count"],) * 2,
            "accounts": (accounts,) * 2, "applications": (config["applications"]["count"],) * 2,
            "transactions": (ordinary + transfers, ordinary + 2 * transfers)}


def make_plan(config: dict, reference: dict, profile: str) -> dict:
    if profile == "reference":
        return {"profile": profile, "queryClientId": "C004", "emptyClientId": "C005",
                "queryStart": "2026-09-01", "queryEnd": "2026-09-30"}
    width = config["idWidth"]
    clients = [identifier("C", i + 1, width) for i in range(config["clients"]["count"])]
    employees = [identifier("E", i + 1, width) for i in range(config["employees"]["count"])]
    anchor, empty, boundary_client = clients[3], clients[4], clients[0]

    def shuffle(values, label):
        result = list(values)
        rng_for(config, "plan", label).shuffle(result)
        return result

    def sample(values, count, label):
        if count < 0 or count > len(values):
            raise GenerationError(f"Not enough eligible items for scenario {label}: need {count}, have {len(values)}")
        return rng_for(config, "plan", label).sample(list(values), count)

    employment = shuffle(expanded(config["clients"]["employmentCounts"]), "employment")
    employment_by_client = dict(zip(clients, employment))
    tx = config["transactions"]
    zero_period_pool = [c for c in clients if c not in {anchor, empty, boundary_client} and employment_by_client[c] != "retired"]
    zero_period = sorted([empty] + sample(zero_period_pool, tx["clientsWithoutPeriodMovements"] - 1, "zero-period"))
    zero_all = sorted([empty] + sample([c for c in zero_period if c != empty], tx["clientsWithoutAnyMovements"] - 1, "zero-all"))
    recurring = []
    for status in sorted(tx["recurringClients"]):
        pool = [c for c in clients if employment_by_client[c] == status and c not in zero_period]
        recurring.extend(sample(pool, tx["recurringClients"][status], "recurring-" + status))
    recurring.sort()

    ownership = [int(k) for k in shuffle(expanded(config["accounts"]["ownershipCounts"]), "ownership")]
    account_owners, account_types, primary = [], [], {}
    type_rng = rng_for(config, "plan", "account-types")
    for client, number in zip(clients, ownership):
        primary[client] = identifier("A", len(account_owners) + 1, width)
        for i in range(number):
            account_owners.append(client)
            account_types.append("current" if i == 0 else weighted(type_rng, config["accounts"]["extraAccountTypeWeights"]))
    accounts = [identifier("A", i + 1, width) for i in range(len(account_owners))]
    protected = sorted({primary[c] for c in recurring} | {primary[boundary_client]})
    counts = dict(config["accounts"]["statusCounts"])
    counts["active"] -= len(protected)
    if counts["active"] < 0:
        raise GenerationError("Insufficient active accounts for protected cases")
    other_statuses = iter(shuffle(expanded(counts), "account-statuses"))
    account_statuses = ["active" if a in protected else next(other_statuses) for a in accounts]
    unused = {a for a, c in zip(accounts, account_owners) if c in zero_all}
    candidates = [a for a in accounts if a not in unused and a not in protected]
    unused.update(sample(candidates, max(0, tx["unusedAccountsMinimum"] - len(unused)), "unused-accounts"))
    transfer_groups = defaultdict(list)
    for account, owner in zip(accounts, account_owners):
        if account not in unused:
            transfer_groups[owner].append(account)
    if tx["sameClientTransfers"] and not any(len(group) >= 2 for group in transfer_groups.values()):
        raise GenerationError("No non-empty multi-account owner remains for same-client transfers")
    if tx["differentClientTransfers"] and len(transfer_groups) < 2:
        raise GenerationError("Need two active source owners for different-client transfers")

    apps = config["applications"]
    no_apps = sorted([empty] + sample([c for c in clients if c not in {empty, anchor}], apps["clientsWithoutApplications"] - 1, "no-applications"))
    app_clients = [c for c in clients if c not in no_apps and c != anchor]
    free_positions = [i for i in range(apps["count"]) if i not in (3, 4)]
    if len(free_positions) < len(app_clients):
        raise GenerationError("Too few applications to cover all selected clients")
    owners = [None] * apps["count"]
    owners[3] = owners[4] = anchor
    owner_rng = rng_for(config, "plan", "application-owners")
    owner_weights = {c: owner_rng.randint(1, 5) for c in app_clients}
    for offset, position in enumerate(free_positions):
        owners[position] = app_clients[offset] if offset < len(app_clients) else weighted(owner_rng, owner_weights)

    def allocate_pinned(count_map, pins, label):
        remaining = dict(count_map)
        for value in pins.values():
            remaining[value] -= 1
        if min(remaining.values()) < 0:
            raise GenerationError(f"Insufficient quota for {label}")
        values = iter(shuffle(expanded(remaining), label))
        return [pins[i] if i in pins else next(values) for i in range(apps["count"])]

    statuses = allocate_pinned(apps["statusCounts"], {3: "pending", 4: "declined"}, "application-statuses")
    purposes = allocate_pinned(apps["purposeCounts"], {3: "home_improvement", 4: "debt_consolidation"}, "application-purposes")
    unassigned = set(sample([i for i, s in enumerate(statuses) if s == "pending" and i != 3], apps["unassignedPending"], "unassigned"))
    assignment_rng = rng_for(config, "plan", "assignments")
    staff = employees[:-1]
    staff_weights = {employee: assignment_rng.randint(1, 8) for employee in staff}
    assigned = [i for i in range(apps["count"]) if i not in unassigned]
    assignments = [None] * apps["count"]
    for offset, position in enumerate(assigned):
        assignments[position] = staff[offset] if offset < len(staff) else weighted(assignment_rng, staff_weights)

    return {"profile": profile, "queryClientId": anchor, "emptyClientId": empty,
            "queryStart": config["queryPeriodStart"], "queryEnd": config["queryPeriodEnd"],
            "clientIds": clients, "employeeIds": employees, "employment": employment,
            "accountIds": accounts, "accountOwners": account_owners, "accountTypes": account_types,
            "accountStatuses": account_statuses, "primaryAccounts": primary,
            "protectedAccounts": protected, "boundaryAccountId": primary[boundary_client],
            "clientsWithoutPeriodMovements": zero_period, "clientsWithoutAnyMovements": zero_all,
            "unusedAccounts": sorted(unused), "recurringClients": recurring,
            "clientsWithoutApplications": no_apps, "applicationOwners": owners,
            "applicationStatuses": statuses, "applicationPurposes": purposes,
            "applicationEmployees": assignments, "employeeWithoutApplications": employees[-1]}


class Builder:
    def __init__(self, config: dict, catalogue: dict, reference: dict, profile: str, plan: dict, store):
        self.config, self.catalogue, self.reference, self.profile, self.plan = config, catalogue, reference, profile, plan
        self.clients = {r["_id"]: r for r in store.rows("clients")}
        self.employees = {r["_id"]: r for r in store.rows("employees")}
        self.accounts = {r["_id"]: r for r in store.rows("accounts")}
        self.zero_period = set(plan.get("clientsWithoutPeriodMovements", []))
        self.unused = set(plan.get("unusedAccounts", []))
        self.protected = set(plan.get("protectedAccounts", []))
        self.available_accounts = sorted(a for a in self.accounts if a not in self.unused)
        self.account_groups = defaultdict(list)
        for account in self.available_accounts:
            self.account_groups[self.accounts[account]["clientId"]].append(account)
        self.multi_owners = sorted(c for c, group in self.account_groups.items() if len(group) >= 2)
        self.eligible_cache = {}
        self.months = months_between(config["observationStart"], config["observationEnd"])
        self.recurring_rows = len(plan.get("recurringClients", [])) * len(self.months)
        self.ordinary_rows = self.recurring_rows + sum(config["transactions"]["ordinaryCounts"].values())

    def unit(self, stage: str, index: int) -> list[dict]:
        if self.profile == "reference":
            return self.reference["transactionUnits"][index] if stage == "transactions" else [self.reference[stage][index]]
        rng = rng_for(self.config, stage, index)
        return getattr(self, "build_" + stage)(index, rng)

    def name(self, rng):
        return " ".join([rng.choice(self.catalogue["firstNames"]), rng.choice(self.catalogue["lastNames"]), rng.choice(self.catalogue["lastNames"])])

    def day(self, rng, lower: str, upper: str, avoid_query=False) -> str:
        first, last = date.fromisoformat(lower), date.fromisoformat(upper)
        if first > last:
            raise GenerationError(f"Empty eligible date range: {lower}..{upper}")
        spans = [(first, last)]
        if avoid_query:
            q1, q2 = date.fromisoformat(self.plan["queryStart"]), date.fromisoformat(self.plan["queryEnd"])
            spans = [(first, min(last, q1 - timedelta(days=1))), (max(first, q2 + timedelta(days=1)), last)]
            spans = [(a, b) for a, b in spans if a <= b]
        total = sum((b-a).days + 1 for a, b in spans)
        if total <= 0:
            raise GenerationError("No date available after preserving zero-period activity case")
        offset = rng.randrange(total)
        for a, b in spans:
            size = (b-a).days + 1
            if offset < size:
                return (a + timedelta(days=offset)).isoformat()
            offset -= size
        raise GenerationError("Date selection failed")

    def build_clients(self, index, rng):
        client = self.plan["clientIds"][index]
        status = self.plan["employment"][index]
        bands = self.config["clients"]["incomeBandsCents"][status]
        band = int(weighted(rng, {str(i): spec[2] for i, spec in enumerate(bands)}))
        low, high, _ = bands[band]
        return [{"_id": client, "name": self.name(rng), "email": client.lower() + "@example.invalid",
                 "annualIncome": rng.randint(low, high), "employmentStatus": status}]

    def build_employees(self, index, rng):
        return [{"_id": self.plan["employeeIds"][index], "name": self.name(rng)}]

    def build_accounts(self, index, rng):
        account, client = self.plan["accountIds"][index], self.plan["accountOwners"][index]
        if client not in self.clients:
            raise GenerationError(f"Account parent is not committed: {client}")
        first, last = self.config["accountOpeningStart"], self.config["accountOpeningEnd"]
        if account in self.protected:
            last = min(last, (date.fromisoformat(self.config["observationStart"]) - timedelta(days=1)).isoformat())
        opened = self.day(rng, first, last)
        return [{"_id": account, "clientId": client, "accountType": self.plan["accountTypes"][index],
                 "currency": self.config["currency"], "openedAt": opened + "T00:00:00.000Z", "status": self.plan["accountStatuses"][index]}]

    def build_applications(self, index, rng):
        spec = self.config["applications"]
        owner, employee = self.plan["applicationOwners"][index], self.plan["applicationEmployees"][index]
        if owner not in self.clients or (employee is not None and employee not in self.employees):
            raise GenerationError("Application parent is not committed")
        status, purpose = self.plan["applicationStatuses"][index], self.plan["applicationPurposes"][index]
        first, last = self.config["observationStart"], self.config["observationEnd"]
        if employee is None:
            first = spec["unassignedStart"]
        elif status == "pending":
            first = spec["pendingStart"]
        else:
            last = spec["decidedEnd"]
        principal = spec["purposes"][purpose]
        amount = 1800000 if index == 3 else 3200000 if index == 4 else rng.randint(*principal["amountCents"])
        seconds = rng.randrange(86400)
        timestamp = datetime.combine(date.fromisoformat(self.day(rng, first, last)), datetime.min.time(), tzinfo=timezone.utc) + timedelta(seconds=seconds)
        result = {"_id": identifier("L", index + 1, self.config["idWidth"]), "clientId": owner,
                  "requestedAmount": amount, "termMonths": rng.choice(principal["terms"]), "purpose": purpose,
                  "submittedAt": timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z"), "status": status}
        if employee is not None:
            result["employeeId"] = employee
        return [result]

    def movement(self, number, account, day, direction, amount, description, transfer=""):
        return {"transactionId": identifier("T", number, self.config["idWidth"]), "accountId": account,
                "transferId": transfer, "bookingDate": day, "direction": direction, "amount": amount,
                "currency": self.config["currency"], "description": description}

    def eligible(self, day, current_only):
        key = day, current_only
        if key not in self.eligible_cache:
            in_query = self.plan["queryStart"] <= day <= self.plan["queryEnd"]
            self.eligible_cache[key] = [a for a in self.available_accounts
                if self.accounts[a]["openedAt"][:10] <= day
                and (not current_only or self.accounts[a]["accountType"] == "current")
                and (not in_query or self.accounts[a]["clientId"] not in self.zero_period)]
        if not self.eligible_cache[key]:
            raise GenerationError(f"No eligible account for movement date {day}")
        return self.eligible_cache[key]

    def build_transactions(self, index, rng):
        tx = self.config["transactions"]
        descriptions = self.catalogue["descriptions"]
        if index < self.recurring_rows:
            owner = self.plan["recurringClients"][index // len(self.months)]
            year, month = self.months[index % len(self.months)]
            day = date(year, month, tx["recurringDay"]).isoformat()
            account = self.plan["primaryAccounts"][owner]
            base = (self.clients[owner]["annualIncome"] + 6) // 12
            percent = rng.randint(-tx["recurringVariationPercent"], tx["recurringVariationPercent"])
            amount = (base * (100 + percent) + 50) // 100
            if amount <= 0:
                raise GenerationError("Recurring income must remain positive; review income bands")
            description = rng.choice(descriptions[self.clients[owner]["employmentStatus"]])
            return [self.movement(index + 1, account, day, "IN", amount, description)]
        if index < self.ordinary_rows:
            offset = index - self.recurring_rows
            category = None
            for candidate in ("deposit", "purchase", "withdrawal", "fee"):
                if offset < tx["ordinaryCounts"][candidate]:
                    category = candidate
                    break
                offset -= tx["ordinaryCounts"][candidate]
            if category is None:
                raise GenerationError("Unknown ordinary movement position")
            if category == "purchase" and offset < 4:
                day = tx["boundaryDates"][offset]
                account = self.plan["boundaryAccountId"]
                amount = (1001, 2550, 9900, 1200)[offset]
                description = descriptions["purchase"][offset % len(descriptions["purchase"])]
            else:
                day = self.day(rng, self.config["observationStart"], self.config["observationEnd"])
                account = rng.choice(self.eligible(day, current_only=category != "fee"))
                low, high = tx["amountRangesCents"][category]
                if category == "withdrawal":
                    step = tx["withdrawalStepCents"]
                    amount = rng.randint((low + step - 1) // step, high // step) * step
                else:
                    amount = rng.randint(low, high)
                description = rng.choice(descriptions[category])
            return [self.movement(index + 1, account, day, "IN" if category == "deposit" else "OUT", amount, description)]

        transfer_index = index - self.ordinary_rows
        same_owner = transfer_index < tx["sameClientTransfers"]
        if same_owner:
            owner = rng.choice(self.multi_owners)
            sender, receiver = rng.sample(self.account_groups[owner], 2)
        else:
            sender = rng.choice(self.available_accounts)
            other = [a for a in self.available_accounts if self.accounts[a]["clientId"] != self.accounts[sender]["clientId"]]
            receiver = rng.choice(other)
        owners = {self.accounts[a]["clientId"] for a in (sender, receiver)}
        first = max(self.config["observationStart"], self.accounts[sender]["openedAt"][:10], self.accounts[receiver]["openedAt"][:10])
        day = self.day(rng, first, self.config["observationEnd"], avoid_query=bool(owners & self.zero_period))
        amount = rng.randint(*tx["amountRangesCents"]["transfer"])
        transfer = identifier("TR", transfer_index + 1, self.config["idWidth"])
        number = self.ordinary_rows + transfer_index * 2 + 1
        return [self.movement(number, sender, day, "OUT", amount, rng.choice(descriptions["transferOut"]).format(accountId=receiver), transfer),
                self.movement(number + 1, receiver, day, "IN", amount, rng.choice(descriptions["transferIn"]).format(accountId=sender), transfer)]
