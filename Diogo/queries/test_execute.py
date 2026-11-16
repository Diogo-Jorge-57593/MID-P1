"""Checks for Q2's date boundaries, account grouping and zero rows."""
from datetime import date
import unittest

from execute import movement_totals


class MovementTotalsTests(unittest.TestCase):
    def test_boundaries_both_transfer_legs_duplicate_amounts_and_zero_client(self):
        clients = [{"_id": "C1"}, {"_id": "C2"}]
        accounts = [{"_id": "A1", "clientId": "C1"}, {"_id": "A2", "clientId": "C1"}]
        # The same-client transfer contributes to both gross totals. Two equal
        # purchases are separate transactions and must not be deduplicated.
        specs = [("31/08/2026", "A1", "IN", "999,00"),
                 ("01/09/2026", "A1", "OUT", "100,10"),
                 ("01/09/2026", "A2", "IN", "100,10"),
                 ("30/09/2026", "A2", "OUT", "0,10"),
                 ("30/09/2026", "A2", "OUT", "0,10"),
                 ("01/10/2026", "A1", "OUT", "999,00")]
        movements = [dict(zip(["bookingDate", "accountId", "direction", "amount"], spec)) for spec in specs]
        rows, matched = movement_totals(clients, accounts, movements, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(matched, 4)
        self.assertEqual(rows, [
            {"clientId": "C1", "totalIncomingEUR": "100.10", "totalOutgoingEUR": "100.30"},
            {"clientId": "C2", "totalIncomingEUR": "0.00", "totalOutgoingEUR": "0.00"}])

    def test_empty_period_preserves_every_client(self):
        rows, matched = movement_totals([{"_id": "C1"}], [], [], date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(matched, 0)
        self.assertEqual(rows, [{"clientId": "C1", "totalIncomingEUR": "0.00", "totalOutgoingEUR": "0.00"}])


if __name__ == "__main__":
    unittest.main()
