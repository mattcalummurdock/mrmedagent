cube('MedicineUses', {
  sql_table: 'medicine_uses',

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
    useText: { sql: 'use_text', type: 'string' },
    displayOrder: { sql: 'display_order', type: 'number' },
  },
});
