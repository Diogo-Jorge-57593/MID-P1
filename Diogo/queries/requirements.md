# P1 query definitions - banking

Date: 13 November 2026. Logical-notation update: 15 November 2026.

Status: two individual-subtopic query definitions. Sources were generated and
MongoDB loaded on 13 November 2026. BQ1 was checked against the loaded scale
source; BQ2's cross-source execution runner remains pending. Professor-style
logical expressions for both queries: [datalog.md](datalog.md).

Group subtopics, following the latest discussion:

- Banking: MongoDB and CSV.
- Venture capital investment firm: SQL and JSON. Detailed entities and field
  contracts have not yet been supplied by the other student.

## 1. What P1 and P2 require

The local project brief, section 2.3, explicitly places the following in P1:

| Query set | Number |
|---|---:|
| Banking student's individual-subtopic queries | 2 |
| Other student's individual-subtopic queries | 2 |
| Joint cross-subtopic queries | 8 |
| **Group total** | **12** |

The complete set must contain **four simple, four intermediate and four
complex queries**, with difficulty justified. P1 section 2.4 requires expected
results in the report. Section 3 then requires implementation and demonstration
of integrated global-schema queries in P2.

Therefore the eight cross-subtopic query definitions cannot all be postponed
until P2. P1 identifies the questions, relevant source information, difficulty
and expected results; P2 develops their global-schema execution. P1 also has
implementation and reproducibility deliverables: section 7.1 says queries must
be executable and return documented results. Keep execution evidence distinct
from proposed definitions; this document alone does not meet every deliverable.

**Cross-source** and **cross-subtopic** are different:

- Combining banking MongoDB and banking CSV is cross-source, within banking.
- Combining banking information with the venture capital firm's information
  is cross-subtopic. Those are the eight joint queries.

## 2. BQ1 - Retrieve a client's credit applications

**Question:** Which credit applications did client `C000004` submit, and what are
their requested amounts and current statuses?

| Property | Definition |
|---|---|
| Scope | Banking; first individual-subtopic query |
| Stakeholder need | Credit officer needs to inspect requests associated with a client |
| Requirement connection | Supports the application-retrieval part of FR3; does not itself retrieve the complete applicant profile |
| Source | MongoDB `dmi_p1_bank.applications` |
| Input | `clientId`: `C000004` in the current scale profile; `C004` in the reference profile |
| Filter | Exact equality on `applications.clientId` |
| Output | `_id`, `requestedAmount` in EUR, `status` |
| Output grain | One row per application |
| Ordering | `_id` ascending |
| Empty result | Empty list when no applications match; for example `C000005` in scale or `C005` in reference |
| Difficulty | **Simple**: one collection, equality filter, projection and sorting; no join or aggregation |

Corresponding `mongosh` query:

```javascript
const bankQueries = db.getSiblingDB('dmi_p1_bank');
bankQueries.applications.find(
  { clientId: 'C000004' },
  { _id: 1, requestedAmount: 1, status: 1 }
).sort({ _id: 1 });
```

Expected result, formatted for the report:

| _id | requestedAmount (EUR) | status |
|---|---:|---|
| L000004 | 18000.00 | pending |
| L000005 | 32000.00 | declined |

These scale-profile values preserve the small reference case: `C004` with
`L004` and `L005`. Current expected results are stored with the generated source
in `expected-query-results.json`, and the scale BQ1 read was checked against
MongoDB on 13 November 2026. Use matching client/application IDs for each profile.
Actual amounts must remain BSON Decimal128, not binary floating-point values.

**Data needed:** at least one client with multiple applications, different
statuses, and a client with no applications to demonstrate the empty result.
Generated profiles contain these cases. The logical expression is documented
in [datalog.md](datalog.md); it does not require employee assignment to exist.

## 3. BQ2 - Summarise client account movements within a period

**Question:** For each client, what are the total incoming and outgoing account
movements during September 2026, across all their accounts, including clients
with no movements?

| Property | Definition |
|---|---|
| Scope | Banking; second individual-subtopic query; cross-source within banking |
| Stakeholder need | Review a client's banking activity over a selected period |
| Requirement connection | Uses FR1 account ownership and FR2 period-filtered movements; adds the client-level aggregation agreed in the operation list |
| Sources | MongoDB `clients` and `accounts`; matching CSV `dataGeneration/outputs/<profile>/<dataset-id>/transactions.csv` (path relative to Diogo) |
| Inputs | Inclusive calendar dates: start `2026-09-01`, end `2026-09-30` |
| Ownership link | `accounts.clientId = clients._id` |
| Movement link | CSV `accountId = accounts._id` |
| Output | `clientId`, `totalIncomingEUR`, `totalOutgoingEUR` |
| Output grain | Exactly one row per MongoDB client |
| Ordering | `clientId` ascending |
| Missing movements | Both totals are zero for a client with no matching movements |
| Difficulty | **Intermediate**: relationships across sources, date conversion/filtering, grouping and conditional decimal sums, preserving clients without matching movements |

Processing definition:

1. Read the client list and account-to-client mapping from MongoDB.
2. Parse CSV using the physical contract in `../physical.txt`. Validate the
   complete file, including account references and transfer pairs, before
   applying period or account filters.
3. Convert `bookingDate` from `DD/MM/YYYY` to a calendar date and `amount` from
   comma-decimal text directly to an exact decimal representation.
4. Retain movements where start date <= booking date <= end date.
5. Resolve each retained movement's owning client through its account.
6. Sum positive amounts separately for `IN` and `OUT` across all accounts of
   each client. Initialise both totals to decimal zero for every client.
7. Return one row per client, in client-ID order.

Expected result for the ten-row illustrative CSV specimen in `../physical.txt`
and the generated reference profile's ownership fixtures in `../dataGeneration/reference.json`:

| clientId | totalIncomingEUR | totalOutgoingEUR |
|---|---:|---:|
| C001 | 0.00 | 125.50 |
| C002 | 300.00 | 200.00 |
| C003 | 0.00 | 50.00 |
| C004 | 1500.00 | 10.00 |
| C005 | 0.00 | 0.00 |

Check totals: incoming **1800.00 EUR**, outgoing **385.50 EUR**. Eight movements
fall within September; records on 31 August and 1 October are excluded.

Important query semantics:

- Include both 1 and 30 September.
- Client `C002` owns accounts `A002` and `A005`; combine both without duplicating
  movements. Transfer `TR002` between those accounts contributes `200.00` to
  each gross total and cancels in net movement.
- Client `C005` owns `A006`, which has no movements; retain its zero-total row.
- A transfer's two movements each affect their own accounts. Do not treat the
  shared `transferId` as a reason to remove either account movement.
- These are gross movement totals, not external income/spending, account
  balances or creditworthiness measures.
- Only EUR is in scope; no currency conversion or aggregation across currencies.

**Data needed:** multiple accounts for a client; incoming and outgoing
movements; an internal transfer; an account with no movements; exact decimal
amounts; dates on and outside the period boundaries. The physical CSV specimen
and generated profiles contain these cases. Export validation is implemented;
the actual cross-source query runner remains pending. Full logical semantics,
including aggregation and zero-total rows, are specified in [datalog.md](datalog.md).

## 4. Remaining group query design

These banking proposals occupy one simple and one intermediate slot. Across
the remaining ten group queries, the difficulty targets are:

| Difficulty | Required overall | Used here | Remaining |
|---|---:|---:|---:|
| Simple | 4 | 1 | 3 |
| Intermediate | 4 | 1 | 3 |
| Complex | 4 | 0 | 4 |

The remaining ten comprise the colleague's two queries and the eight joint
queries. Agree classifications together rather than choosing each student's
queries independently of the group totals.

Before finalising the eight joint queries, obtain the colleague's SQL/JSON
entity and field definitions and agree a meaningful shared identifier. A
possible shared concept is an individual who is both a bank client and an
investor, **if** individual investor records exist in the venture capital
sources. This is a candidate, not a confirmed source contract.

The current banking Client model describes people, with employment status and
annual income. Do not assume portfolio companies are already represented as
bank clients, or join company/investor/client names as if they were stable
identifiers. Company-level banking queries would require an explicit extension
or mapping justified by the agreed group requirements.

For each joint query document its business question, inputs, source entities,
join keys, transformations, output grain, difficulty justification and expected
fixture results. SQL/JSON technology choices alone do not identify those links.

## 5. Relation to existing project files

- `mongo.js` already contains the same simple client-application query under
  label Q1, plus two supporting demonstrations. It still uses the small reference
  ID `C004`; use the scale-specific query above for the current database. BQ1 is that individual
  query; the demonstrations are not automatically additional required queries.
- `../report/report.tex` already proposes the same client movement-total
  question as Q2. BQ2 here makes its inputs, semantics and expected results
  explicit using the latest CSV specimen.
- `../physical.txt` defines the storage contracts. `../database/load.py` loads
  and verifies the current MongoDB source. Legacy fixture scripts remain
  separate; BQ2 execution is pending.
- `datalog.md` provides professor-style logical notation for both queries,
  explicitly marking aggregation/negation extensions needed by full BQ2.
- This document defines the two banking queries. It does not claim the other
  student's queries or the eight joint queries are already specified.

Source: local `../../../DMI_Projects_2026_2027.pdf`, sections 2.3-2.4, 3, 4.3 and
7.1. This course PDF remains outside the Git repository; the path refers to
the original university workspace. Model decisions follow the current logical
and physical specifications.
