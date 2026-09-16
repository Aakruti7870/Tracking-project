import { useState } from "react";
import {
  Order,
  Plant,
  MixerTelemetry,
  ConcreteGrade,
  OrderStatus,
  DrumDirection,
  TelemetryStatus,
} from "../types";
import { PourPlanner } from "./PourPlanner";
import { LiveTracker } from "./LiveTracker";
import { 
  Building2, 
  Truck, 
  MapPin, 
  Clock, 
  CheckCircle, 
  AlertCircle, 
  Plus, 
  FileText, 
  Calendar,
  Layers,
  ChevronRight,
  ShieldCheck,
  Search,
  ExternalLink
} from "lucide-react";

interface CustomerViewProps {
  orders: Order[];
  plants: Plant[];
  telemetry: Record<string, MixerTelemetry>;
  onOpenNewOrder: () => void;
  onApplyCalculation: (data: { grade: ConcreteGrade; quantity: number; notes: string }) => void;
  onUpdateOrderStatus: (orderId: string, status: OrderStatus) => void;
  onOpenChallan: (order: Order) => void;
  onOpenPod: (order: Order) => void;
}

export function CustomerView({
  orders,
  plants,
  telemetry,
  onOpenNewOrder,
  onApplyCalculation,
  onUpdateOrderStatus,
  onOpenChallan,
  onOpenPod,
}: CustomerViewProps) {
  const [activeTab, setActiveTab] = useState<"orders" | "planner" | "plants">("orders");
  const [selectedOrderId, setSelectedOrderId] = useState<string>(orders[0]?.id || "");
  const [searchFilter, setSearchFilter] = useState("");

  const activeOrder = orders.find((o) => o.id === selectedOrderId) || orders[0];
  const activeTelemetry: MixerTelemetry = (activeOrder && telemetry[activeOrder.id]) || {
    order_id: activeOrder?.id || "",
    tm_number: activeOrder?.tm_number || "MH-04-EK-9214",
    driver_name: activeOrder?.driver_name || "Rameshwar Gurjar",
    driver_mobile: activeOrder?.driver_mobile || "+91 98451 22340",
    capacity_m3: 7,
    current_load_m3: activeOrder?.quantity_m3 || 6,
    speed_kmh: 36,
    drum_rpm: 3.2,
    drum_direction: DrumDirection.Agitating,
    concrete_temp_c: 27.5,
    slump_measured_mm: 120,
    progress_percent: 65,
    eta_minutes: 15,
    current_lat: 19.215,
    current_lng: 72.97,
    start_lat: 19.198,
    start_lng: 72.956,
    dest_lat: 19.232,
    dest_lng: 72.985,
    status: TelemetryStatus.EnRouteSite,
  };

  const getStatusBadge = (status: OrderStatus) => {
    switch (status) {
      case OrderStatus.Dispatched:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#FF6A00]/20 text-[#FF7A18] border border-[#FF6A00]/30 animate-pulse">In Transit</span>;
      case OrderStatus.Batching:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#3B82F6]/20 text-[#3B82F6] border border-[#3B82F6]/30">Batching</span>;
      case OrderStatus.OnSite:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#A855F7]/20 text-[#A855F7] border border-[#A855F7]/30">At Site</span>;
      case OrderStatus.Pouring:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#EC4899]/20 text-[#EC4899] border border-[#EC4899]/30">Pouring</span>;
      case OrderStatus.Delivered:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#38A169]/20 text-[#38A169] border border-[#38A169]/30">Delivered</span>;
      case OrderStatus.Confirmed:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-[#DD6B20]/20 text-[#DD6B20] border border-[#DD6B20]/30">Confirmed</span>;
      default:
        return <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-gray-800 text-gray-400">Draft</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner with Quick Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-gray-400">Active Pour Orders</span>
            <h3 className="text-2xl font-black text-white mt-0.5">{orders.filter(o => o.status !== OrderStatus.Delivered).length}</h3>
          </div>
          <div className="p-3 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18]">
            <Truck className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-gray-400">Total Volume Poured</span>
            <h3 className="text-2xl font-black text-white mt-0.5">
              {orders.reduce((acc, o) => acc + o.quantity_m3, 0)} <span className="text-xs font-normal text-gray-400">m³</span>
            </h3>
          </div>
          <div className="p-3 rounded-xl bg-[#38A169]/10 text-[#38A169]">
            <Layers className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-gray-400">Verified Plant Network</span>
            <h3 className="text-2xl font-black text-white mt-0.5">{plants.length} <span className="text-xs font-normal text-gray-400">Hubs</span></h3>
          </div>
          <div className="p-3 rounded-xl bg-[#3B82F6]/10 text-[#3B82F6]">
            <Building2 className="w-5 h-5" />
          </div>
        </div>

        <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex items-center justify-between">
          <div>
            <span className="text-[11px] font-medium text-gray-400">Quality Compliance</span>
            <h3 className="text-2xl font-black text-[#38A169] mt-0.5">100%</h3>
          </div>
          <div className="p-3 rounded-xl bg-[#38A169]/10 text-[#38A169]">
            <ShieldCheck className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex items-center justify-between border-b border-[#2D3748] pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab("orders")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "orders"
                ? "bg-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/25"
                : "text-gray-400 hover:text-white hover:bg-[#1D232D]"
            }`}
          >
            Orders & Live Tracking ({orders.length})
          </button>
          <button
            onClick={() => setActiveTab("planner")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "planner"
                ? "bg-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/25"
                : "text-gray-400 hover:text-white hover:bg-[#1D232D]"
            }`}
          >
            Pour Planner & Volume Estimator
          </button>
          <button
            onClick={() => setActiveTab("plants")}
            className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
              activeTab === "plants"
                ? "bg-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/25"
                : "text-gray-400 hover:text-white hover:bg-[#1D232D]"
            }`}
          >
            Batching Plants ({plants.length})
          </button>
        </div>

        <button
          onClick={onOpenNewOrder}
          className="hidden sm:flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#1D232D] hover:bg-[#2D3748] text-[#FF7A18] border border-[#FF6A00]/30 text-xs font-bold transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>New Requisition</span>
        </button>
      </div>

      {/* TAB 1: ORDERS & TRACKING */}
      {activeTab === "orders" && (
        <div className="space-y-6">
          {/* Active Live Tracker Card if activeOrder is in progress */}
          {activeOrder && (
            <LiveTracker
              order={activeOrder}
              telemetry={activeTelemetry}
              onUpdateStatus={onUpdateOrderStatus}
              onOpenChallan={onOpenChallan}
              onOpenPod={onOpenPod}
            />
          )}

          {/* Orders List Table / Cards */}
          <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl overflow-hidden shadow-xl">
            <div className="p-4 border-b border-[#2D3748] flex items-center justify-between bg-[#1D232D]">
              <h3 className="text-sm font-bold text-white">All Requisitions & Active Dispatches</h3>
              <span className="text-xs text-gray-400">Click any order to display telemetry</span>
            </div>

            <div className="divide-y divide-[#2D3748]">
              {orders.map((o) => {
                const isSelected = o.id === selectedOrderId;
                return (
                  <div
                    key={o.id}
                    onClick={() => setSelectedOrderId(o.id)}
                    className={`p-4 transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                      isSelected ? "bg-[#FF6A00]/10 border-l-4 border-l-[#FF6A00]" : "hover:bg-[#1D232D]/50"
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-white">{o.order_number}</span>
                        {getStatusBadge(o.status)}
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-[#1D232D] text-[#FF7A18]">
                          {o.grade}
                        </span>
                        <span className="text-xs font-bold text-gray-300">{o.quantity_m3} m³</span>
                      </div>
                      <p className="text-sm font-bold text-white">{o.site_name}</p>
                      <p className="text-xs text-gray-400 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-gray-500" />
                        <span>{o.site_address}</span>
                      </p>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-center">
                      <div className="text-right">
                        <span className="text-xs font-bold text-white font-mono">
                          ₹{o.total_amount.toLocaleString("en-IN")}
                        </span>
                        <p className="text-[10px] text-gray-400">{o.delivery_date} · {o.delivery_time}</p>
                      </div>

                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenChallan(o);
                          }}
                          className="p-2 rounded-lg bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748]"
                          title="View Challan"
                        >
                          <FileText className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenPod(o);
                          }}
                          className="p-2 rounded-lg bg-[#1D232D] text-[#38A169] hover:bg-[#38A169]/20 border border-[#2D3748]"
                          title="Proof of Delivery"
                        >
                          <CheckCircle className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: POUR PLANNER */}
      {activeTab === "planner" && (
        <PourPlanner
          onApplyCalculation={(calc) => {
            onApplyCalculation(calc);
            setActiveTab("orders");
          }}
        />
      )}

      {/* TAB 3: BATCHING PLANTS DIRECTORY */}
      {activeTab === "plants" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {plants.map((plant) => (
            <div
              key={plant.id}
              className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 flex flex-col justify-between shadow-lg"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-bold text-[#FF7A18] uppercase tracking-wider">{plant.company}</span>
                    <h3 className="text-base font-bold text-white mt-0.5">{plant.name}</h3>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#12251A] text-[#38A169] border border-[#38A169]/30">
                    ★ {plant.rating}
                  </span>
                </div>

                <p className="text-xs text-gray-400 mt-2 flex items-start gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-500 shrink-0 mt-0.5" />
                  <span>{plant.address}</span>
                </p>

                <div className="mt-4 pt-3 border-t border-[#2D3748] space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Peak Capacity:</span>
                    <span className="text-white font-mono font-bold">{plant.capacity_m3_hr} m³/hr</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Service Radius:</span>
                    <span className="text-white font-medium">{plant.service_area_km} km</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Base M25 Rate:</span>
                    <span className="text-[#38A169] font-mono font-bold">₹{plant.base_rate_m25}/m³</span>
                  </div>
                  <div className="flex justify-between items-center pt-1">
                    <span className="text-gray-400">Grades:</span>
                    <div className="flex gap-1">
                      {plant.grades.slice(0, 4).map((g) => (
                        <span key={g} className="px-1.5 py-0.5 rounded text-[9px] font-mono bg-[#1D232D] text-gray-300">
                          {g}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-5 pt-3 border-t border-[#2D3748]">
                <button
                  onClick={onOpenNewOrder}
                  className="w-full py-2.5 rounded-xl bg-[#FF6A00] text-white text-xs font-bold hover:bg-[#FF7A18] transition-all"
                >
                  Order from this Plant
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
