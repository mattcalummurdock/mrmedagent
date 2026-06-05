cube('Salts', {
  sql_table: 'salts',

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
    description: { sql: 'description', type: 'string' },
  },
});
