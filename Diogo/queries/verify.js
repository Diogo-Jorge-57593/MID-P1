const bank = db.getSiblingDB('dmi_p1_bank');
assert.eq(5, bank.clients.countDocuments({}), 'Expected five fixture clients');
assert.eq(6, bank.accounts.countDocuments({}), 'Expected six fixture accounts');
assert.eq(6, bank.applications.countDocuments({}), 'Expected six fixture applications');
assert.eq(['L004', 'L005'], bank.applications.find({ clientId: 'C004' }).sort({ _id: 1 }).toArray().map(x => x._id));
const totals = bank.applications.aggregate([
  { $group: { _id: '$status', count: { $sum: 1 }, amount: { $sum: '$requestedAmount' } } }
]).toArray();
for (const [status, count, amount] of [['pending', 2, '30000'], ['approved', 3, '49000'], ['declined', 1, '32000']]) {
  const row = totals.find(x => x._id === status);
  assert(row, 'Missing status ' + status);
  assert.eq(count, row.count);
  assert.eq(NumberDecimal(amount), row.amount);
}
for (const collection of ['accounts', 'applications']) {
  assert.eq(0, bank[collection].aggregate([
    { $lookup: { from: 'clients', localField: 'clientId', foreignField: '_id', as: 'client' } },
    { $match: { client: { $size: 0 } } }, { $count: 'orphans' }
  ]).toArray().length, 'Orphan client reference in ' + collection);
}
for (const app of bank.applications.find().toArray()) {
  assert.eq(app.status, app.statusHistory[app.statusHistory.length - 1].status);
}
// Validation rejection without inserting any invalid persistent document.
const rejected = bank.runCommand({ insert: 'applications', documents: [{ _id: 'INVALID' }] });
assert(rejected.writeErrors && rejected.writeErrors[0].code === 121, 'Schema must reject incomplete document');
print('PASS: fixture counts, Q1, aggregates, references, history, schema rejection.');
