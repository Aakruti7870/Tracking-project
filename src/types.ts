export type UserRole = 
  | "customer"
  | "plant_owner"
  | "driver"
  | "dispatcher"
  | "operator"
  | "central_admin";

export type OrderStatus =
  | "DRAFT"
  | "CONFIRMED"
  | "BATCHING"
  | "DISPATCHED"
  | "ON_SITE"
  | "POURING"
  | "DELIVERED"
  | "CANCELLED";

export type PaymentStatus = "PAID" | "PENDING" | "PARTIAL";

export type ConcreteGrade = 
  | "M10"
  | "M15"
  | "M20"
  | "M25"
  | "M30"
  | "M35"
  | "M40"
  | "M50";

export type PumpType = "None (Direct Discharge)" | "Boom Pump (36m)" | "Line Pump (100m)" | "Static Placer";

export type Order = {
  id: string;
  order_number: string;
  customer_name: string;
  customer_phone: string;
  plant_id: string;
  plant_name: string;
  grade: ConcreteGrade;
  quantity_m3: number;
  site_name: string;
  site_address: string;
  delivery_date: string;
  delivery_time: string;
  status: OrderStatus;
  payment_status: PaymentStatus;
  pump_type: PumpType;
  slump: string;
  tm_number?: string;
  driver_name?: string;
  driver_mobile?: string;
  challan_number?: string;
  invoice_number?: string;
  rate_per_m3: number;
  total_amount: number;
  created_at: string;
  pour_type?: string;
  pod?: ProofOfDelivery;
};

export type SiloLevels = {
  cement_percent: number;
  fly_ash_percent: number;
  agg_10mm_percent: number;
  agg_20mm_percent: number;
  sand_percent: number;
  admixture_percent: number;
  water_reserve_percent: number;
};

export type Plant = {
  id: string;
  name: string;
  company: string;
  city: string;
  district: string;
  address: string;
  lat: number;
  lng: number;
  grades: ConcreteGrade[];
  contact_phone: string;
  service_area_km: number;
  verified: boolean;
  order_enabled: boolean;
  rating: number;
  capacity_m3_hr: number;
  base_rate_m25: number;
  silos: SiloLevels;
};

export type MixerTelemetry = {
  order_id: string;
  tm_number: string;
  driver_name: string;
  driver_mobile: string;
  capacity_m3: number;
  current_load_m3: number;
  speed_kmh: number;
  drum_rpm: number;
  drum_direction: "MIXING" | "AGITATING" | "DISCHARGING" | "STOPPED";
  concrete_temp_c: number;
  slump_measured_mm: number;
  progress_percent: number; // 0 to 100
  eta_minutes: number;
  current_lat: number;
  current_lng: number;
  start_lat: number;
  start_lng: number;
  dest_lat: number;
  dest_lng: number;
  status: "EN_ROUTE_SITE" | "ARRIVED_SITE" | "POURING" | "COMPLETED" | "RETURNING";
};

export type ProofOfDelivery = {
  order_id: string;
  receiver_name: string;
  receiver_phone: string;
  receiver_designation: string;
  delivered_quantity_m3: number;
  delivered_at: string;
  slump_at_pour_mm: number;
  cube_samples_taken: boolean;
  cube_count: number;
  signature_data?: string;
  site_notes: string;
  verified_by_driver: boolean;
};

export type PourCalculation = {
  structure_type: "slab" | "column" | "beam" | "footing" | "retaining_wall";
  length_m: number;
  width_m: number;
  height_m: number;
  count: number;
  wastage_percent: number;
  calculated_net_m3: number;
  calculated_gross_m3: number;
  recommended_grade: ConcreteGrade;
  suggested_truckloads: number;
};
