cube('MedicineIndications', {
  sql_table: 'medicine_indications',

  joins: {
    Diseases: {
      sql: `${CUBE}.disease_id = ${Diseases}.id`,
      relationship: 'many_to_one',
    },
    Medicines: {
      sql: `${CUBE}.medicine_id = ${Medicines}.id`,
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
    diseaseId: {
      sql: 'disease_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    indicationNote: { sql: 'indication_note', type: 'string' },
  },
});
