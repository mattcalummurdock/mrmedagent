cube('Indications', {
  sql_table: 'v_medicines_by_indication',

  measures: {
    count: { type: 'count' },
  },

  dimensions: {
    diseaseId: {
      sql: 'disease_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    diseaseName: { sql: 'disease_name', type: 'string' },
    diseaseCategory: { sql: 'disease_category', type: 'string' },
    medicineId: {
      sql: 'medicine_id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    medicineName: { sql: 'medicine_name', type: 'string' },
    genericName: { sql: 'generic_name', type: 'string' },
    sellingPrice: { sql: 'selling_price', type: 'number' },
    isAvailable: { sql: 'is_available', type: 'boolean' },
    prescriptionRequired: { sql: 'prescription_required', type: 'boolean' },
    therapeuticClass: { sql: 'therapeutic_class', type: 'string' },
  },
});
