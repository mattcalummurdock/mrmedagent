cube('Alternatives', {
  sql_table: 'v_alternatives_ranked',

  measures: {
    count: { type: 'count' },
    avgPriceDifference: {
      sql: 'price_difference',
      type: 'avg',
    },
  },

  dimensions: {
    sourceMedicineId: {
      sql: 'source_medicine_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    sourceMedicineName: { sql: 'source_medicine_name', type: 'string' },
    sourcePrice: { sql: 'source_price', type: 'number' },
    alternativeId: {
      sql: 'alternative_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    alternativeName: { sql: 'alternative_name', type: 'string' },
    alternativePrice: { sql: 'alternative_price', type: 'number' },
    alternativeRequiresRx: { sql: 'alternative_requires_rx', type: 'boolean' },
    alternativeInStock: { sql: 'alternative_in_stock', type: 'boolean' },
    priceDifference: { sql: 'price_difference', type: 'number' },
    matchScore: { sql: 'match_score', type: 'number' },
    matchReason: { sql: 'match_reason', type: 'string' },
    tier: { sql: 'tier', type: 'number' },
    isCheaper: {
      type: 'string',
      case: {
        when: [{ sql: `${CUBE}.price_difference < 0`, label: 'Yes' }],
        else: { label: 'No' },
      },
    },
  },
});
