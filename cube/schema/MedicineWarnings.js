cube('MedicineWarnings', {
  sql_table: 'medicine_warnings',

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
    medicineId: { sql: 'medicine_id', type: 'number' },
    warningText: { sql: 'warning_text', type: 'string' },
    audience: { sql: 'audience', type: 'string' },
  },
});
