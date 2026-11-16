// Current physical model. Definitions only; load.py performs safe preflight and creation.
const nonBlankText = { bsonType: 'string', minLength: 1, pattern: '\\S' };
const schemas = {
  clients: {
    bsonType: 'object',
    additionalProperties: false,
    required: ['_id', 'name', 'email', 'annualIncome', 'employmentStatus'],
    properties: {
      _id: { bsonType: 'string', pattern: '^C[0-9]{3,}$' },
      name: nonBlankText,
      email: {
        bsonType: 'string',
        pattern: '^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$'
      },
      annualIncome: { bsonType: 'decimal', minimum: NumberDecimal('0.00') },
      employmentStatus: {
        bsonType: 'string',
        enum: ['employed', 'self-employed', 'unemployed', 'retired', 'student']
      }
    }
  },
  accounts: {
    bsonType: 'object',
    additionalProperties: false,
    required: ['_id', 'clientId', 'accountType', 'currency', 'openedAt', 'status'],
    properties: {
      _id: { bsonType: 'string', pattern: '^A[0-9]{3,}$' },
      clientId: { bsonType: 'string', pattern: '^C[0-9]{3,}$' },
      accountType: { bsonType: 'string', enum: ['current', 'savings'] },
      currency: { bsonType: 'string', enum: ['EUR'] },
      openedAt: { bsonType: 'date' },
      status: { bsonType: 'string', enum: ['active', 'blocked', 'closed'] }
    }
  },
  employees: {
    bsonType: 'object',
    additionalProperties: false,
    required: ['_id', 'name'],
    properties: {
      _id: { bsonType: 'string', pattern: '^E[0-9]{3,}$' },
      name: nonBlankText
    }
  },
  applications: {
    bsonType: 'object',
    additionalProperties: false,
    required: [
      '_id', 'clientId', 'requestedAmount', 'termMonths',
      'purpose', 'submittedAt', 'status'
    ],
    properties: {
      _id: { bsonType: 'string', pattern: '^L[0-9]{3,}$' },
      clientId: { bsonType: 'string', pattern: '^C[0-9]{3,}$' },
      employeeId: { bsonType: 'string', pattern: '^E[0-9]{3,}$' },
      requestedAmount: {
        bsonType: 'decimal', minimum: NumberDecimal('0.01')
      },
      termMonths: { bsonType: 'int', minimum: 1 },
      purpose: nonBlankText,
      submittedAt: { bsonType: 'date' },
      status: { bsonType: 'string', enum: ['pending', 'approved', 'declined'] }
    }
  }
};

const indexes = {
  accounts: [{key: {clientId: 1}, name: 'accounts_by_client'}],
  applications: [
    {key: {clientId: 1, submittedAt: -1}, name: 'applications_by_client_date'},
    {key: {employeeId: 1, submittedAt: -1}, name: 'applications_by_employee_date'},
    {key: {submittedAt: 1, status: 1}, name: 'applications_by_date_status'}
  ]
};
// Approved/declined applications require an assigned employee.
schemas.applications.anyOf = [
  {required: ['employeeId']},
  {properties: {status: {enum: ['pending']}}}
];
