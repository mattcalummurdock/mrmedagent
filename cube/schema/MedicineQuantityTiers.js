cube('MedicineQuantityTiers', {
  sql_table: 'medicine_quantity_tiers',

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
    medicineId: {
      sql: 'medicine_id',
      type: 'number',
    },
    quantity: {
      sql: 'quantity',
      type: 'number',
    },
    totalPrice: {
      sql: 'total_price',
      type: 'number',
    },
    label: {
      sql: 'label',
      type: 'string',
    },
    displayOrder: {
      sql: 'display_order',
      type: 'number',
    },
  },
});
