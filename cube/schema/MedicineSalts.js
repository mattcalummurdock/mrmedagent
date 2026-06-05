cube('MedicineSalts', {
  sql_table: 'medicine_salts',

  joins: {
    Salts: {
      sql: `${CUBE}.salt_id = ${Salts}.id`,
      relationship: 'many_to_one',
    },
  },

  measures: {
    count: { type: 'count' },
  },

  dimensions: {
    medicineId: {
      sql: 'medicine_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    saltId: {
      sql: 'salt_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    quantity: {
      sql: 'quantity',
      type: 'string',
    },
  },
});
