import { useState } from "react";
import { Order, MixerTelemetry } from "../types";
import { 
  Truck, 
  MapPin, 
  Phone, 
  RotateCw, 
  Clock, 
  CheckCircle2, 
  FileText, 
  ShieldAlert, 
  Navigation,
  Compass,
  ArrowRight
} from "lucide-react";

interface DriverViewProps {
  orders: Order[];
  telemetry: Record<string, MixerTelemetry>;
  onUpdateStatus: (orderId: string, status: Order["status"]) => void;
  onOpenChallan: (order: Order) => void;
  onOpenPod: (order: Order) => void;
}

export function DriverView({
  orders,
  telemetry,
  onUpdateStatus,
  onOpenChallan,
  onOpenPod,
}: DriverViewProps) {
  const activeOrder = orders.find((o) => o.status !== "DELIVERED") || orders[0];
  const [drumSpeed, setDrumSpeed] = useState(3.4);
  const [dutyActive, setDutyActive] = useState(true);

  if (!activeOrder) {
    return (
      <div className="p-12 text-center bg-[#14181F] rounded-2xl border border-[#2D3748]">
        <Truck className="w-12 h-12 text-gray-500 mx-auto mb-3" />
        <h3 className="text-base font-bold text-white">No Active Trip Assigned</h3>
        <p className="text-xs text-gray-400 mt-1">Standby at the batching plant for your next dispatch ticket.</p>
      </div>
    );
  }

  const currentStatus = activeOrder.status;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Duty Status Bar */}
      <div className="p-4 rounded-2xl bg-[#14181F] border border-[#2D3748] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18] flex items-center justify-center font-bold">
            <Truck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white">Pilot: Rameshwar Gurjar</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#1D232D] text-[#38A169] font-bold">
                TM: MH-04-EK-9214
              </span>
            </div>
            <p className="text-xs text-gray-400">Shift Started: 06:30 AM · Trips Completed Today: 2</p>
          </div>
        </div>

        <button
          onClick={() => setDutyActive(!dutyActive)}
          className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
            dutyActive
              ? "bg-[#12251A] text-[#38A169] border border-[#38A169]/30"
              : "bg-red-950/40 text-red-400 border border-red-800/40"
          }`}
        >
          {dutyActive ? "● On Duty" : "○ Off Duty"}
        </button>
      </div>

      {/* Primary Active Trip Card */}
      <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl overflow-hidden shadow-2xl">
        <div className="p-5 bg-gradient-to-r from-[#1E293B] to-[#14181F] border-b border-[#2D3748] flex flex-wrap items-center justify-between gap-3">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#FF7A18]">
              Current Dispatch Ticket
            </span>
            <h2 className="text-xl font-black text-white mt-0.5">{activeOrder.site_name}</h2>
            <p className="text-xs text-gray-400 flex items-center gap-1 mt-1">
              <MapPin className="w-3.5 h-3.5 text-gray-500" />
              <span>{activeOrder.site_address}</span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onOpenChallan(activeOrder)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748] text-xs font-bold"
            >
              <FileText className="w-3.5 h-3.5 text-[#FF7A18]" />
              <span>Challan</span>
            </button>
            <a
              href={`https://maps.google.com/?q=${encodeURIComponent(activeOrder.site_address)}`}
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#3B82F6] hover:bg-blue-600 text-white text-xs font-bold"
            >
              <Navigation className="w-3.5 h-3.5" />
              <span>Google Maps</span>
            </a>
          </div>
        </div>

        {/* Concrete & Vehicle Specs */}
        <div className="p-5 grid grid-cols-2 sm:grid-cols-4 gap-3 bg-[#0E1116] border-b border-[#1F2937] text-xs">
          <div>
            <span className="text-[10px] text-gray-400 font-semibold uppercase">Concrete Grade</span>
            <p className="text-base font-black text-[#FF7A18] font-mono mt-0.5">{activeOrder.grade}</p>
            <p className="text-[10px] text-gray-500">{activeOrder.quantity_m3} m³ Net Batch</p>
          </div>
          <div>
            <span className="text-[10px] text-gray-400 font-semibold uppercase">Slump Specification</span>
            <p className="text-base font-bold text-white font-mono mt-0.5">{activeOrder.slump}</p>
            <p className="text-[10px] text-[#38A169]">Pumpable Grade</p>
          </div>
          <div>
            <span className="text-[10px] text-gray-400 font-semibold uppercase">Target Site Time</span>
            <p className="text-base font-bold text-white font-mono mt-0.5">{activeOrder.delivery_time}</p>
            <p className="text-[10px] text-gray-500">Max 120m window</p>
          </div>
          <div>
            <span className="text-[10px] text-gray-400 font-semibold uppercase">Site Contact</span>
            <p className="text-xs font-bold text-white truncate mt-0.5">{activeOrder.customer_name}</p>
            <a href={`tel:${activeOrder.customer_phone}`} className="text-[10px] text-[#3B82F6] font-mono hover:underline">
              {activeOrder.customer_phone}
            </a>
          </div>
        </div>

        {/* Telematics Controls for Driver */}
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <RotateCw className="w-4 h-4 text-[#FF7A18] animate-spin" />
              <span className="text-xs font-bold text-white">Transit Drum Rotation Control</span>
            </div>
            <span className="text-xs font-mono font-bold text-[#FF7A18]">{drumSpeed} RPM (Agitation)</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setDrumSpeed(3.2)}
              className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all ${
                drumSpeed <= 4
                  ? "bg-[#FF6A00]/20 border-[#FF6A00] text-[#FF7A18]"
                  : "bg-[#1D232D] border-[#2D3748] text-gray-400"
              }`}
            >
              Agitation Mode (2 - 4 RPM)
            </button>
            <button
              onClick={() => setDrumSpeed(12.0)}
              className={`flex-1 py-2 rounded-xl text-xs font-bold border transition-all ${
                drumSpeed > 4
                  ? "bg-[#FF6A00]/20 border-[#FF6A00] text-[#FF7A18]"
                  : "bg-[#1D232D] border-[#2D3748] text-gray-400"
              }`}
            >
              High-Speed Mix (12 RPM)
            </button>
          </div>

          {/* Interactive Driver Action Stepper */}
          <div className="pt-4 border-t border-[#2D3748]">
            <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 block mb-2">
              Advance Trip Stage
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <button
                onClick={() => onUpdateStatus(activeOrder.id, "DISPATCHED")}
                className={`py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all ${
                  currentStatus === "DISPATCHED"
                    ? "bg-[#FF6A00] text-white shadow-lg shadow-[#FF6A00]/25"
                    : "bg-[#1D232D] text-gray-300 hover:text-white"
                }`}
              >
                <span>1. Left Plant (In Transit)</span>
              </button>

              <button
                onClick={() => onUpdateStatus(activeOrder.id, "ON_SITE")}
                className={`py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 transition-all ${
                  currentStatus === "ON_SITE"
                    ? "bg-[#3B82F6] text-white shadow-lg shadow-blue-500/25"
                    : "bg-[#1D232D] text-gray-300 hover:text-white"
                }`}
              >
                <span>2. Arrived at Site</span>
              </button>

              <button
                onClick={() => onOpenPod(activeOrder)}
                className="py-3 px-4 rounded-xl font-bold text-xs flex items-center justify-center gap-2 bg-[#38A169] text-white shadow-lg shadow-[#38A169]/25 hover:bg-[#276749] transition-all"
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>3. Complete & Sign POD</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
