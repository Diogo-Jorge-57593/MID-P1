const bank = db.getSiblingDB('dmi_p1_bank');
// Q1 (simple): credit requests submitted by C004.
print('Q1');
printjson(bank.applications.find({ clientId: 'C004' }, {
  _id: 1, requestedAmount: 1, status: 1
}).sort({ _id: 1 }).toArray());
// Supporting MongoDB demonstration; not an extra required individual query.
print('D1: applications by status');
printjson(bank.applications.aggregate([
  { $group: { _id: '$status', count: { $sum: 1 }, totalRequested: { $sum: '$requestedAmount' } } },
  { $sort: { _id: 1 } }
]).toArray());
print('D2: applications with client names');
printjson(bank.applications.aggregate([
  { $lookup: { from: 'clients', localField: 'clientId', foreignField: '_id', as: 'client' } },
  { $unwind: '$client' },
  { $project: { _id: 1, clientName: '$client.name', status: 1 } },
  { $sort: { _id: 1 } }
]).toArray());
