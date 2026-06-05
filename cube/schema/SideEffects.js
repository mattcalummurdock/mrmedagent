cube('SideEffects', {
  sql_table: 'side_effects',

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
    effectText: { sql: 'effect_text', type: 'string' },
    severity: { sql: 'severity', type: 'string' },
    displayOrder: { sql: 'display_order', type: 'number' },
  },
});
