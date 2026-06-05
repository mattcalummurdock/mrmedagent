cube('Diseases', {
  sql_table: 'diseases',

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
    category: { sql: 'category', type: 'string' },
  },
});
