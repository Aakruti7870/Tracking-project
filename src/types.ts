/**
 * TrackMyRMC - Strongly Typed Domain Models & Enums
 * Adheres strictly to IS 456 / IS 4926 Standards for Ready Mix Concrete
 */

// ==========================================
// Strongly Typed Domain Enums
// ==========================================

export enum UserRole {
  Customer = "customer",
  PlantOwner = "plant_owner",
  Driver = "driver",
  Dispatcher = "dispatcher",
  Operator = "operator",
  CentralAdmin = "central_admin",
}

export enum OrderStatus {
  Draft = "DRAFT",
  Confirmed = "CONFIRMED",
  Batching = "BATCHING",
  Dispatched = "DISPATCHED",
  OnSite = "ON_SITE",
  Pouring = "POURING",
  Delivered = "DELIVERED",
  Cancelled = "CANCELLED",
}

export enum PaymentStatus {
  Paid = "PAID",
  Pending = "PENDING",
  Partial = "PARTIAL",
}

export enum ConcreteGrade {
  M10 = "M10",
  M15 = "M15",
  M20 = "M20",
  M25 = "M25",
  M30 = "M30",
  M35 = "M35",
  M40 = "M40",
  M50 = "M50",
}

export enum PumpType {
  None = "None (Direct Discharge)",
  Boom36m = "Boom Pump (36m)",
  Line100m = "Line Pump (100m)",
  StaticPlacer = "Static Placer",
}

export enum DrumDirection {
  Mixing = "MIXING",
  Agitating = "AGITATING",
  Discharging = "DISCHARGING",
  Stopped = "STOPPED",
}

export enum TelemetryStatus {
  EnRouteSite = "EN_ROUTE_SITE",
  ArrivedSite = "ARRIVED_SITE",
  Pouring = "POURING",
  Completed = "COMPLETED",
  Returning = "RETURNING",
}

export enum StructureType {
  Slab = "slab",
  Column = "column",
  Beam = "beam",
  Footing = "footing",
  RetainingWall = "retaining_wall",
}

// ==========================================
// Strongly Typed Domain Interfaces
// ==========================================

export interface SiloLevels {
  readonly cement_percent: number;
  readonly fly_ash_percent: number;
  readonly agg_10mm_percent: number;
  readonly agg_20mm_percent: number;
  readonly sand_percent: number;
  readonly admixture_percent: number;
  readonly water_reserve_percent: number;
}

export interface ProofOfDelivery {
  readonly order_id: string;
  readonly receiver_name: string;
  readonly receiver_phone: string;
  readonly receiver_designation: string;
  readonly delivered_quantity_m3: number;
  readonly delivered_at: string;
  readonly slump_at_pour_mm: number;
  readonly cube_samples_taken: boolean;
  readonly cube_count: number;
  readonly signature_data?: string;
  readonly site_notes: string;
  readonly verified_by_driver: boolean;
}

export interface Order {
  readonly id: string;
  readonly order_number: string;
  readonly customer_name: string;
  readonly customer_phone: string;
  readonly plant_id: string;
  readonly plant_name: string;
  readonly grade: ConcreteGrade;
  readonly quantity_m3: number;
  readonly site_name: string;
  readonly site_address: string;
  readonly delivery_date: string;
  readonly delivery_time: string;
  readonly status: OrderStatus;
  readonly payment_status: PaymentStatus;
  readonly pump_type: PumpType;
  readonly slump: string;
  readonly tm_number?: string;
  readonly driver_name?: string;
  readonly driver_mobile?: string;
  readonly challan_number?: string;
  readonly invoice_number?: string;
  readonly rate_per_m3: number;
  readonly total_amount: number;
  readonly created_at: string;
  readonly pour_type?: string;
  readonly pod?: ProofOfDelivery;
}

export interface Plant {
  readonly id: string;
  readonly name: string;
  readonly company: string;
  readonly city: string;
  readonly district: string;
  readonly address: string;
  readonly lat: number;
  readonly lng: number;
  readonly grades: readonly ConcreteGrade[];
  readonly contact_phone: string;
  readonly service_area_km: number;
  readonly verified: boolean;
  readonly order_enabled: boolean;
  readonly rating: number;
  readonly capacity_m3_hr: number;
  readonly base_rate_m25: number;
  readonly silos: SiloLevels;
}

export interface MixerTelemetry {
  readonly order_id: string;
  readonly tm_number: string;
  readonly driver_name: string;
  readonly driver_mobile: string;
  readonly capacity_m3: number;
  readonly current_load_m3: number;
  readonly speed_kmh: number;
  readonly drum_rpm: number;
  readonly drum_direction: DrumDirection;
  readonly concrete_temp_c: number;
  readonly slump_measured_mm: number;
  readonly progress_percent: number; // 0 to 100
  readonly eta_minutes: number;
  readonly current_lat: number;
  readonly current_lng: number;
  readonly start_lat: number;
  readonly start_lng: number;
  readonly dest_lat: number;
  readonly dest_lng: number;
  readonly status: TelemetryStatus;
}

export interface PourCalculation {
  readonly structure_type: StructureType;
  readonly length_m: number;
  readonly width_m: number;
  readonly height_m: number;
  readonly count: number;
  readonly wastage_percent: number;
  readonly calculated_net_m3: number;
  readonly calculated_gross_m3: number;
  readonly recommended_grade: ConcreteGrade;
  readonly suggested_truckloads: number;
}

// ==========================================
// Robust Type Guards & Type Assertions
// ==========================================

export function isUserRole(value: unknown): value is UserRole {
  return typeof value === "string" && Object.values(UserRole).includes(value as UserRole);
}

export function isOrderStatus(value: unknown): value is OrderStatus {
  return typeof value === "string" && Object.values(OrderStatus).includes(value as OrderStatus);
}

export function isConcreteGrade(value: unknown): value is ConcreteGrade {
  return typeof value === "string" && Object.values(ConcreteGrade).includes(value as ConcreteGrade);
}

export function isPaymentStatus(value: unknown): value is PaymentStatus {
  return typeof value === "string" && Object.values(PaymentStatus).includes(value as PaymentStatus);
}

export function isPumpType(value: unknown): value is PumpType {
  return typeof value === "string" && Object.values(PumpType).includes(value as PumpType);
}

export function isDrumDirection(value: unknown): value is DrumDirection {
  return typeof value === "string" && Object.values(DrumDirection).includes(value as DrumDirection);
}

export function isTelemetryStatus(value: unknown): value is TelemetryStatus {
  return typeof value === "string" && Object.values(TelemetryStatus).includes(value as TelemetryStatus);
}

/**
 * Compile-time exhaustiveness checking for discriminated unions and enums.
 * Causes a compile error if a switch case or branch is missing.
 */
export function assertExhaustive(x: never, message = "Unexpected unreachable code reached"): never {
  throw new Error(`${message}: ${String(x)}`);
}

/**
 * Result Monad Pattern for safe, type-safe operations without throwing uncaught exceptions.
 */
export type Result<T, E = Error> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: E };

export function Ok<T>(value: T): Result<T, never> {
  return { ok: true, value };
}

export function Err<E>(error: E): Result<never, E> {
  return { ok: false, error };
}

