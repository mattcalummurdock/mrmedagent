cube('Medicines', {
  sql_table: 'medicines',

  joins: {
    Manufacturers: {
      sql: `${CUBE}.manufacturer_id = ${Manufacturers}.id`,
      relationship: 'many_to_one',
    },
    MedicineUses: {
      sql: `${CUBE}.id = ${MedicineUses}.medicine_id`,
      relationship: 'one_to_many',
    },
    SideEffects: {
      sql: `${CUBE}.id = ${SideEffects}.medicine_id`,
      relationship: 'one_to_many',
    },
    DrugInteractions: {
      sql: `${CUBE}.id = ${DrugInteractions}.medicine_id`,
      relationship: 'one_to_many',
    },
    MedicineWarnings: {
      sql: `${CUBE}.id = ${MedicineWarnings}.medicine_id`,
      relationship: 'one_to_many',
    },
  },

  measures: {
    count: {
      type: 'count',
    },
    avgPrice: {
      sql: 'selling_price',
      type: 'avg',
      title: 'Average Selling Price',
    },
    minPrice: {
      sql: 'selling_price',
      type: 'min',
      title: 'Minimum Price',
    },
    maxPrice: {
      sql: 'selling_price',
      type: 'max',
      title: 'Maximum Price',
    },
    avgDiscount: {
      sql: 'discount_percent',
      type: 'avg',
      title: 'Average Discount %',
    },
    inStockCount: {
      type: 'count',
      filters: [{ sql: `${CUBE}.is_available = true` }],
      title: 'In Stock Count',
    },
    prescriptionCount: {
      type: 'count',
      filters: [{ sql: `${CUBE}.prescription_required = true` }],
      title: 'Prescription Required Count',
    },
    totalStockUnits: {
      sql: 'stock_quantity',
      type: 'sum',
      title: 'Total Stock Units',
    },
  },

  dimensions: {
    id: {
      sql: 'id',
      type: 'number',
      primaryKey: true,
      public: true,
    },
    name: {
      sql: 'name',
      type: 'string',
    },
    slug: {
      sql: 'slug',
      type: 'string',
    },
    genericName: {
      sql: 'generic_name',
      type: 'string',
    },
    brandName: {
      sql: 'brand_name',
      type: 'string',
    },
    form: {
      sql: 'form',
      type: 'string',
    },
    dosageStrength: {
      sql: 'dosage_strength',
      type: 'string',
    },
    packSize: {
      sql: 'pack_size',
      type: 'string',
    },
    mrp: {
      sql: 'mrp',
      type: 'number',
    },
    sellingPrice: {
      sql: 'selling_price',
      type: 'number',
    },
    discountPercent: {
      sql: 'discount_percent',
      type: 'number',
    },
    pricePerUnit: {
      sql: 'price_per_unit',
      type: 'number',
    },
    pricingModel: {
      sql: 'pricing_model',
      type: 'string',
    },
    isAvailable: {
      sql: 'is_available',
      type: 'boolean',
    },
    stockQuantity: {
      sql: 'stock_quantity',
      type: 'number',
    },
    prescriptionRequired: {
      sql: 'prescription_required',
      type: 'boolean',
    },
    scheduleType: {
      sql: 'schedule_type',
      type: 'string',
    },
    therapeuticClass: {
      sql: 'therapeutic_class',
      type: 'string',
    },
    pharmacologicalClass: {
      sql: 'pharmacological_class',
      type: 'string',
    },
    introduction: {
      sql: 'introduction',
      type: 'string',
    },
    mechanismOfAction: {
      sql: 'mechanism_of_action',
      type: 'string',
    },
    howToConsume: {
      sql: 'how_to_consume',
      type: 'string',
    },
    storageInstructions: {
      sql: 'storage_instructions',
      type: 'string',
    },
    wordOfAdvice: {
      sql: 'word_of_advice',
      type: 'string',
    },
    sideEffectsSummary: {
      sql: 'missed_dose_info',
      type: 'string',
    },
    googleRating: {
      sql: 'google_rating',
      type: 'number',
    },
    dispatchSlaHours: {
      sql: 'dispatch_sla_hours',
      type: 'number',
    },
    lastUpdatedAt: {
      sql: 'last_updated_at',
      type: 'time',
    },
    stockStatus: {
      type: 'string',
      case: {
        when: [
          { sql: `${CUBE}.stock_quantity > 50`, label: 'High Stock' },
          { sql: `${CUBE}.stock_quantity > 10`, label: 'Low Stock' },
          { sql: `${CUBE}.stock_quantity > 0`, label: 'Critical Stock' },
        ],
        else: { label: 'Out of Stock' },
      },
    },
    rxType: {
      type: 'string',
      case: {
        when: [
          { sql: `${CUBE}.prescription_required = false`, label: 'OTC' },
        ],
        else: { label: 'Prescription Only' },
      },
    },
    savingsAmount: {
      sql: `${CUBE}.mrp - ${CUBE}.selling_price`,
      type: 'number',
    },
  },

  dataSource: 'default',
});
