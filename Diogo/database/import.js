// Appended to schema.js and a validated request by load.py; executed in mongosh.
const bank = db.getSiblingDB(request.database);
const collections = Object.keys(schemas);
const expected = Object.fromEntries(collections.map(name => [name,
  request.documents[name].map(row => EJSON.deserialize(row, {relaxed: false}))
]));

function ordered(value) {
  if (Array.isArray(value)) return value.map(ordered);
  if (value !== null && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])]));
  }
  return value;
}

function canonical(value) {
  return JSON.stringify(ordered(EJSON.serialize(value, {relaxed: false})));
}

function requireCheck(condition, message) {
  if (!condition) throw new Error(message);
}

// Complete preflight before any collection, index or document write.
const existing = bank.getCollectionInfos();
requireCheck(existing.every(info => collections.includes(info.name)),
  'Target contains unrelated collections; select a separate database.');
const missing = {};
for (const name of collections) {
  const info = existing.find(item => item.name === name);
  const byId = new Map(expected[name].map(row => [row._id, row]));
  const actual = info ? bank.getCollection(name).find({}).toArray() : [];
  for (const row of actual) {
    requireCheck(byId.has(row._id), `Conflicting dataset: unexpected ${name} ID ${row._id}`);
    requireCheck(canonical(row) === canonical(byId.get(row._id)),
      `Conflicting document ${name}/${row._id}; existing data will not be overwritten.`);
  }
  if (info) {
    requireCheck(info.type === 'collection', `${name} is not a normal collection.`);
    requireCheck(canonical(info.options.validator) === canonical({$jsonSchema: schemas[name]})
      && info.options.validationLevel === 'strict' && info.options.validationAction === 'error',
      `Existing ${name} schema differs; use a separate database or a reviewed migration.`);
    const currentIndexes = bank.getCollection(name).getIndexes();
    for (const spec of indexes[name] || []) {
      const index = currentIndexes.find(item => item.name === spec.name);
      requireCheck(!index || (JSON.stringify(index.key) === JSON.stringify(spec.key) && !index.unique),
        `Existing index ${spec.name} differs; refusing replacement.`);
    }
  }
  const present = new Set(actual.map(row => row._id));
  missing[name] = expected[name].filter(row => !present.has(row._id));
}

const insertedCounts = Object.fromEntries(collections.map(name => [name, 0]));
if (!request.verifyOnly) {
  // Parents first. Retried runs insert only missing, previously verified IDs.
  for (const name of collections) {
    if (!existing.some(info => info.name === name)) {
      const created = bank.createCollection(name, {
        validator: {$jsonSchema: schemas[name]}, validationLevel: 'strict', validationAction: 'error'
      });
      requireCheck(created.ok === 1, `Could not create ${name}.`);
    }
    for (const spec of indexes[name] || []) {
      bank.getCollection(name).createIndex(spec.key, {name: spec.name});
    }
  }
  for (const name of ['clients', 'employees', 'accounts', 'applications']) {
    for (let position = 0; position < missing[name].length; position += 100) {
      const batch = missing[name].slice(position, position + 100);
      const result = bank.getCollection(name).insertMany(batch, {ordered: true});
      requireCheck(result.acknowledged, `${name} batch was not acknowledged.`);
      insertedCounts[name] += batch.length;
    }
  }
}

// Verify actual stored values, counts, validators, indexes and BSON types.
const counts = {};
const bsonTypes = {};
const typeFields = {
  clients: {annualIncome: 'decimal'},
  accounts: {openedAt: 'date'},
  applications: {requestedAmount: 'decimal', termMonths: 'int', submittedAt: 'date'}
};
for (const name of collections) {
  const collection = bank.getCollection(name);
  const actual = collection.find({}).toArray();
  requireCheck(actual.length === expected[name].length, `Wrong stored count for ${name}.`);
  const byId = new Map(expected[name].map(row => [row._id, canonical(row)]));
  requireCheck(actual.every(row => byId.get(row._id) === canonical(row)), `Stored ${name} differs from source.`);
  for (const spec of indexes[name] || []) {
    requireCheck(collection.getIndexes().some(index => index.name === spec.name), `Missing index ${spec.name}.`);
  }
  counts[name] = actual.length;
  for (const [field, type] of Object.entries(typeFields[name] || {})) {
    const invalid = collection.countDocuments({$expr: {$ne: [{$type: '$' + field}, type]}});
    requireCheck(invalid === 0, `Wrong BSON type for ${name}.${field}.`);
    bsonTypes[name + '.' + field] = type;
  }
}

function dangling(collection, field, target, optional = false) {
  const pipeline = optional ? [{$match: {[field]: {$exists: true}}}] : [];
  pipeline.push(
    {$lookup: {from: target, localField: field, foreignField: '_id', as: '__target'}},
    {$match: {__target: {$size: 0}}}, {$count: 'count'}
  );
  const rows = bank.getCollection(collection).aggregate(pipeline).toArray();
  return rows.length ? rows[0].count : 0;
}
const emptyOwners = bank.clients.aggregate([
  {$lookup: {from: 'accounts', localField: '_id', foreignField: 'clientId', as: '__accounts'}},
  {$match: {__accounts: {$size: 0}}}, {$count: 'count'}
]).toArray();
const referenceErrors = {
  accountsMissingClient: dangling('accounts', 'clientId', 'clients'),
  applicationsMissingClient: dangling('applications', 'clientId', 'clients'),
  applicationsMissingEmployee: dangling('applications', 'employeeId', 'employees', true),
  clientsWithoutAccount: emptyOwners.length ? emptyOwners[0].count : 0,
  unassignedNonPending: bank.applications.countDocuments({employeeId: {$exists: false}, status: {$ne: 'pending'}})
};
requireCheck(Object.values(referenceErrors).every(count => count === 0), 'Stored reference/cardinality checks failed.');
print('__BANK_RESULT__' + JSON.stringify({
  verified: true, database: request.database, serverVersion: db.version(),
  sourceFingerprint: request.fingerprint, counts, insertedCounts, bsonTypes, referenceErrors,
  verifiedOnly: request.verifyOnly
}));
