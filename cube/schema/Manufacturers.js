cube('Manufacturers', {
  sql_table: 'manufacturers',

  measures: {
    count: { type: 'count' },
  },

  dimensions: {
    id: {
      sql: 'id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    name: { sql: 'name', type: 'string' },
    country: { sql: 'country', type: 'string' },
  },
});
