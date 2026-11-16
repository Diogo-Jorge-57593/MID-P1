# Banking queries in the lessons' logical notation

Date: 15 November 2026. Scope: BQ1 and BQ2, using the current scale-profile
identifiers. This document specifies the queries; it is not an executable
Datalog program for a particular engine.

## 1. Notation found in the lessons

The notation is **Datalog-style rules / conjunctive queries**:

```text
Q(C, P) :- Sale(O, C, P), Product(P, "book").
```

- Lesson 7, printed slide 08 (PDF page 8), explains conjunctive queries and
  shows a logical rule beside its SQL equivalent. Printed slide 10 explains
  Datalog programs, base relations and derived relations.
- Lesson 9, printed slides 04-05 (PDF pages 8-9), explains the head, body,
  repeated join variables and existential variables using the example above.
- Lesson 7 explicitly excludes union, negation and aggregation from a single
  conjunctive query. BQ2's complete totals therefore require an extension.

Read `:-` as "if". The head on the left contains the output attributes.
Commas on the right mean AND. Reusing a variable links matching values.
Variables occurring only in the body are not returned. Quoted values are
constants. Relational answers are unordered sets; sorting is a presentation step.

Source PDFs are `Aulas/DMI_Lesson7.pdf` and `Aulas/DMI_Lesson9.pdf` in the
original university workspace, outside the shared Git repository.

## 2. Logical relations used below

These are projections of existing source fields, with the argument order fixed
by this table. They do not require additional stored entities.

| Predicate | Ordered arguments | Existing source fields |
|---|---|---|
| `CreditApplication(A, C, M, S)` | application ID, client ID, amount, status | MongoDB `applications`: `_id`, `clientId`, `requestedAmount`, `status` |
| `Client(C)` | client ID | MongoDB `clients._id` |
| `Account(K, C)` | account ID, client ID | MongoDB `accounts`: `_id`, `clientId` |
| `Transaction(T, K, D, Dir, M, U)` | movement ID, account ID, date, direction, amount, currency | CSV: `transactionId`, `accountId`, `bookingDate`, `direction`, `amount`, `currency` |

`M` denotes exact EUR decimal money. A CSV wrapper parses comma-decimal text
without binary floating-point conversion. `D` uses canonical `YYYY-MM-DD`
calendar dates after parsing the stored `DD/MM/YYYY` text, making the date
comparisons below meaningful. The complete CSV, references and transfer pairs
are validated before selecting these fields or filtering dates.

`employeeId` is not needed by these questions. Applications without an employee
are still included by the `CreditApplication` projection. Similarly, omitting
`transferId` and `description` from the projected predicate does not remove rows:
every movement keeps its unique `T`.

## 3. BQ1 - A client's credit applications

Question: return application ID, requested amount and current status for client
`C000004`.

```text
BQ1(A, M, S) :-
    CreditApplication(A, "C000004", M, S).
```

The constant filters the client. The head returns only application ID, amount
and status. This is a conjunctive query with selection and projection.

Current scale-profile answer, displayed by application ID ascending:

| A | M (EUR) | S |
|---|---:|---|
| L000004 | 18000.00 | pending |
| L000005 | 32000.00 | declined |

For the small reference profile, replace `C000004` with `C004`; the corresponding
IDs are `L004` and `L005`. Query the selected profile's source consistently.

## 4. BQ2 - September incoming/outgoing totals per client

Question: return one row per client with incoming and outgoing totals across
all their accounts for 1-30 September 2026, including zero-activity clients.

### 4.1 Join and filter in the lessons' rule style

```text
SeptemberMovement(C, T, Dir, M) :-
    Client(C),
    Account(K, C),
    Transaction(T, K, D, Dir, M, "EUR"),
    D >= "2026-09-01",
    D <= "2026-09-30".
```

`C` joins clients to their accounts; `K` joins accounts to CSV movements.
Both date boundaries are included. This is the relational matching part of
BQ2, with built-in comparisons; it returns movements before aggregation.

### 4.2 Complete query in explicitly extended Datalog-style pseudocode

The slides' basic conjunctive-query language cannot express SUM and missing
movement groups. The following adds grouped aggregation and stratified
negation to specify the complete requirement. `sum<M>` is declared notation
here, not a claim about syntax taught in the slides or accepted by an installed
engine.

```text
Incoming(C, T, M) :- SeptemberMovement(C, T, "IN", M).
Outgoing(C, T, M) :- SeptemberMovement(C, T, "OUT", M).

HasIncoming(C) :- Incoming(C, T, M).
HasOutgoing(C) :- Outgoing(C, T, M).

IncomingTotal(C, sum<M>) :- Incoming(C, T, M).
OutgoingTotal(C, sum<M>) :- Outgoing(C, T, M).

IncomingTotal(C, 0.00) :- Client(C), not HasIncoming(C).
OutgoingTotal(C, 0.00) :- Client(C), not HasOutgoing(C).

BQ2(C, TotalIn, TotalOut) :-
    Client(C),
    IncomingTotal(C, TotalIn),
    OutgoingTotal(C, TotalOut).
```

Aggregation semantics: group rows `(C, T, M)` by `C` and sum `M` once for each
movement ID `T`. Two movements of the same amount still contribute twice.
`sum<M>` operates only on existing groups; the separate zero rules supply
missing incoming/outgoing groups. Money, including `0.00`, is exact decimal.
Negation is evaluated after `HasIncoming`/`HasOutgoing`; there is no negative
recursion.

These rules retain every client, even when only one direction is present or
both totals are zero. An internal transfer between the same client's accounts
contributes to both gross totals. Both legs retain their own movement IDs;
there is no transfer-ID deduplication. These are gross movements, not balances
or external-only income/spending. Display the final answer by client ID ascending.

Scale-profile expected examples:

| C | TotalIn (EUR) | TotalOut (EUR) |
|---|---:|---:|
| C000001 | 18804.03 | 3794.96 |
| C000002 | 0.00 | 736.22 |
| C000004 | 0.00 | 2780.85 |
| C000005 | 0.00 | 0.00 |

The complete expected result has 500 rows, one per client, in the scale run's
`expected-query-results.json`. These examples come from that independent
expected-result artefact. This document does not implement or execute BQ2.

If the report must use only pure conjunctive queries, retain section 4.1 as the
matching expression and describe grouping/zero-fill as a separate processing
step. Do not label the full aggregate query a plain conjunctive query.

## 5. Related definitions and execution status

- [requirements.md](requirements.md): business questions, output fields,
  difficulty and reference-profile examples.
- BQ1's corresponding MongoDB read was checked against the loaded scale
  source on 13 November 2026.
- BQ2's cross-source execution runner is still pending. These logical rules
  describe the required result independently of its eventual implementation.
