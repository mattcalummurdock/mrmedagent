cube('DrugInteractions', {
  sql_table: 'drug_interactions',

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
    interactingDrug: { sql: 'interacting_drug', type: 'string' },
    interactionEffect: { sql: 'interaction_effect', type: 'string' },
    severity: { sql: 'severity', type: 'string' },
  },
});
