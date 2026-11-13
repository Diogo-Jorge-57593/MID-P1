// Run through: python Diogo/run.py setup
// Separate P1 database. Existing exercise databases remain untouched.
const bank = db.getSiblingDB('dmi_p1_bank');
const text = { bsonType: 'string', minLength: 1 };
const money = { bsonType: 'decimal', minimum: NumberDecimal('0') };
const definitions = {
  clients: {
    required: ['_id', 'name', 'contact', 'annualIncome', 'employment'],
    properties: {
      _id: { bsonType: 'string', pattern: '^C[0-9]{3}$' }, name: text,
      contact: { bsonType: 'object', required: ['email', 'city'], properties: { email: text, city: text } },
      annualIncome: money, employment: { enum: ['permanent', 'fixed-term', 'self-employed'] }
    }
  },
  accounts: {
    required: ['_id', 'clientId', 'type', 'currency', 'openedAt', 'status'],
    properties: {
      _id: { bsonType: 'string', pattern: '^A[0-9]{3}$' },
      clientId: { bsonType: 'string', pattern: '^C[0-9]{3}$' },
      type: { enum: ['current', 'savings'] }, currency: { enum: ['EUR'] },
      openedAt: { bsonType: 'date' }, status: { enum: ['active', 'closed'] }
    }
  },
  applications: {
    required: ['_id', 'clientId', 'requestedAmount', 'termMonths', 'purpose', 'status', 'submittedAt', 'statusHistory'],
    properties: {
      _id: { bsonType: 'string', pattern: '^L[0-9]{3}$' },
      clientId: { bsonType: 'string', pattern: '^C[0-9]{3}$' },
      requestedAmount: { bsonType: 'decimal', minimum: NumberDecimal('0.01') },
      termMonths: { bsonType: 'int', minimum: 1, maximum: 480 }, purpose: text,
      status: { enum: ['pending', 'approved', 'declined'] }, submittedAt: { bsonType: 'date' },
      statusHistory: { bsonType: 'array', minItems: 1, items: {
        bsonType: 'object', required: ['status', 'at'], properties: {
          status: { enum: ['pending', 'approved', 'declined'] }, at: { bsonType: 'date' }
        }
      } }
    }
  }
};
for (const [name, schema] of Object.entries(definitions)) {
  const options = { validator: { $jsonSchema: { bsonType: 'object', ...schema } }, validationLevel: 'strict', validationAction: 'error' };
  if (bank.getCollectionNames().includes(name)) {
    assert.commandWorked(bank.runCommand({ collMod: name, ...options }));
  } else {
    bank.createCollection(name, options);
  }
}
bank.accounts.createIndex({ clientId: 1 });
bank.applications.createIndex({ clientId: 1, submittedAt: -1 });
bank.applications.createIndex({ status: 1, requestedAmount: -1 });

const clients = [
  ['C001', 'Joana Martins', 'Faro', '28500', 'permanent'],
  ['C002', 'Miguel Ferreira', 'Lisboa', '49000', 'permanent'],
  ['C003', 'Ines Ribeiro', 'Porto', '24000', 'self-employed'],
  ['C004', 'Tiago Costa', 'Faro', '31000', 'fixed-term'],
  ['C005', 'Ana Sousa', 'Loule', '36000', 'permanent']
].map(([id, name, city, income, employment]) => ({
  _id: id, name, contact: { email: id.toLowerCase() + '@example.invalid', city },
  annualIncome: NumberDecimal(income), employment
}));
const accounts = [
  ['A001', 'C001', 'current'], ['A002', 'C002', 'current'],
  ['A003', 'C003', 'current'], ['A004', 'C004', 'current'],
  ['A005', 'C002', 'savings'], ['A006', 'C005', 'current']
].map(([id, clientId, type]) => ({ _id: id, clientId, type, currency: 'EUR',
  openedAt: ISODate('2026-01-01T00:00:00Z'), status: 'active' }));
const applications = [
  ['L001', 'C001', '12000', 48, 'home_improvement', 'pending'],
  ['L002', 'C002', '25000', 60, 'education', 'approved'],
  ['L003', 'C003', '9000', 36, 'debt_consolidation', 'approved'],
  ['L004', 'C004', '18000', 60, 'home_improvement', 'pending'],
  ['L005', 'C004', '32000', 72, 'debt_consolidation', 'declined'],
  ['L006', 'C002', '15000', 48, 'education', 'approved']
].map(([id, clientId, amount, months, purpose, status], i) => {
  const submittedAt = ISODate(`2026-09-0${i + 1}T09:00:00Z`);
  const statusHistory = [{ status: 'pending', at: submittedAt }];
  if (status !== 'pending') statusHistory.push({ status, at: ISODate(`2026-09-0${i + 2}T10:00:00Z`) });
  return { _id: id, clientId, requestedAmount: NumberDecimal(amount), termMonths: NumberInt(months),
    purpose, status, submittedAt, statusHistory };
});
// Insert missing fixtures only: re-running never resets existing documents.
for (const [name, documents] of Object.entries({ clients, accounts, applications })) {
  for (const document of documents) {
    const { _id, ...fields } = document;
    bank[name].updateOne({ _id }, { $setOnInsert: fields }, { upsert: true });
  }
}
print('P1 bank schema and synthetic fixtures ready. Existing documents preserved.');
