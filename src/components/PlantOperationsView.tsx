import { useState } from "react";
import { Plant, Order, SiloLevels } from "../types";
import { 
  Building2, 
  Droplets, 
  Layers, 
  RotateCw, 
  Play, 
  CheckCircle2, 
  Clock, 
  RefreshCw,
  Sliders,
  AlertTriangle
} from "lucide-react";

interface PlantOperationsViewProps {
  plants: Plant[];
  orders: Order[];
  onUpdateStatus: (orderId: string, status: Order["status"]) => void;
  onOpenChallan: (order: Order) => void;
}

export function PlantOperationsView({
  plants,
  orders,
  onUpdateStatus,
  onOpenChallan,
}: PlantOperationsViewProps) {
  const [selectedPlantId, setSelectedPlantId] = useState<string>(plants[0]?.id || "plant-1");
  const currentPlant = plants.find((p) => p.id === selectedPlantId) || plants[0];
  
  const [silos, setSilos] = useState<SiloLevels>(currentPlant.silos);
  const [batchingSimActive, setBatchingSimActive] = useState(false);

  const refillSilos = () => {
    setSilos({
      cement_percent: 95,
      fly_ash_percent: 90,
      agg_10mm_percent: 88,
      agg_20mm_percent: 92,
      sand_percent: 85,
      admixture_percent: 98,
      water_reserve_percent: 100,
    });
  };

  const startBatchingCycle = (orderId: string) => {
    setBatchingSimActive(true);
    onUpdateStatus(orderId, "BATCHING");
    setTimeout(() => {
      onUpdateStatus(orderId, "DISPATCHED");
      setBatchingSimActive(false);
      // Deplete silos slightly
      setSilos((prev) => ({
        ...prev,
        cement_percent: Math.max(10, prev.cement_percent - 4),
        sand_percent: Math.max(10, prev.sand_percent - 5),
        agg_20mm_percent: Math.max(10, prev.agg_20mm_percent - 4),
      }));
    }, 2500);
  };

  const siloCards = [
    { label: "OPC 53 Cement", level: silos.cement_percent, color: "#FF6A00", capacity: "120 Tons" },
    { label: "Fly Ash (Class F)", level: silos.fly_ash_percent, color: "#718096", capacity: "60 Tons" },
    { label: "River Sand (Zone II)", level: silos.sand_percent, color: "#ECC94B", capacity: "300 Tons" },
    { label: "10mm Aggregate", level: silos.agg_10mm_percent, color: "#A0AEC0", capacity: "250 Tons" },
    { label: "20mm Aggregate", level: silos.agg_20mm_percent, color: "#CBD5E0", capacity: "300 Tons" },
    { label: "PCE Admixture", level: silos.admixture_percent, color: "#9F7AEA", capacity: "5,000 Liters" },
    { label: "Water Reservoir", level: silos.water_reserve_percent, color: "#3182CE", capacity: "40,000 Liters" },
  ];

  return (
    <div className="space-y-6">
      {/* Plant Selector Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-2xl bg-[#14181F] border border-[#2D3748]">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18]">
            <Building2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">{currentPlant.name}</h2>
            <p className="text-xs text-gray-400">
              {currentPlant.address} · Rated: {currentPlant.capacity_m3_hr} m³/hr
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={selectedPlantId}
            onChange={(e) => {
              setSelectedPlantId(e.target.value);
              const p = plants.find((x) => x.id === e.target.value);
              if (p) setSilos(p.silos);
            }}
            className="bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs font-semibold text-white focus:border-[#FF6A00] focus:outline-none"
          >
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.company} ({p.city})
              </option>
            ))}
          </select>
          <button
            onClick={refillSilos}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748] text-xs font-semibold transition-all"
            title="Refill Bulk Silos"
          >
            <RefreshCw className="w-3.5 h-3.5 text-[#38A169]" />
            <span>Refill Silos</span>
          </button>
        </div>
      </div>

      {/* Silo Inventory Storage Gauges */}
      <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 shadow-xl">
        <div className="flex items-center justify-between pb-4 border-b border-[#2D3748]">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-[#FF7A18]" />
            <h3 className="text-sm font-bold text-white">Bulk Material Silo Telemetry</h3>
          </div>
          <span className="text-[11px] text-gray-400 font-mono">Automated ultrasonic level sensors</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mt-4">
          {siloCards.map((silo, idx) => {
            const isLow = silo.level < 25;
            return (
              <div
                key={idx}
                className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748] flex flex-col justify-between"
              >
                <div>
                  <span className="text-[10px] text-gray-400 font-semibold truncate block">{silo.label}</span>
                  <div className="flex items-baseline justify-between mt-1">
                    <span className="text-lg font-black text-white font-mono">{silo.level}%</span>
                    <span className="text-[9px] text-gray-500">{silo.capacity}</span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-[#14181F] rounded-full h-2 mt-3 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{
                      width: `${silo.level}%`,
                      backgroundColor: isLow ? "#E53E3E" : silo.color,
                    }}
                  />
                </div>
                {isLow && (
                  <span className="text-[9px] text-red-400 font-bold mt-1 flex items-center gap-1">
                    <AlertTriangle className="w-2.5 h-2.5" /> Reorder Alert
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Active Batching Queue & Pan Mixer Weighers */}
      <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 shadow-xl">
        <div className="flex items-center justify-between pb-4 border-b border-[#2D3748]">
          <div>
            <h3 className="text-sm font-bold text-white">Automated Batching Queue (Twin Shaft Pan Mixer)</h3>
            <p className="text-xs text-gray-400 mt-0.5">IS 4926 automated weigh-batching cycle</p>
          </div>
          <span className="px-2.5 py-1 rounded-full text-xs font-bold bg-[#12251A] text-[#38A169] border border-[#38A169]/30">
            PLC Weigher: Online
          </span>
        </div>

        <div className="divide-y divide-[#2D3748] mt-4">
          {orders.map((ord) => {
            const isBatching = ord.status === "BATCHING";
            const canBatch = ord.status === "CONFIRMED";
            return (
              <div key={ord.id} className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-white">{ord.order_number}</span>
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-[#FF6A00]/20 text-[#FF7A18]">
                      {ord.grade}
                    </span>
                    <span className="text-xs font-bold text-gray-300">{ord.quantity_m3} m³</span>
                    <span className="text-[11px] text-gray-400">· {ord.pump_type}</span>
                  </div>
                  <p className="text-sm font-bold text-white">{ord.site_name}</p>
                  <p className="text-xs text-gray-400">Assigned Transit Mixer: {ord.tm_number || "Unassigned"}</p>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onOpenChallan(ord)}
                    className="px-3 py-2 rounded-xl bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748] text-xs font-semibold"
                  >
                    View Batch Ticket
                  </button>

                  {canBatch && (
                    <button
                      onClick={() => startBatchingCycle(ord.id)}
                      disabled={batchingSimActive}
                      className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FF6A00] hover:bg-[#FF7A18] text-white text-xs font-bold shadow-md shadow-[#FF6A00]/25 transition-all"
                    >
                      <Play className="w-3.5 h-3.5" />
                      <span>Start Auto-Batching</span>
                    </button>
                  )}

                  {isBatching && (
                    <span className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#3B82F6]/20 text-[#3B82F6] text-xs font-bold border border-blue-500/30">
                      <RotateCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Pan Mixer Running...</span>
                    </span>
                  )}

                  {ord.status === "DISPATCHED" && (
                    <span className="px-3 py-2 rounded-xl bg-[#12251A] text-[#38A169] text-xs font-bold border border-[#38A169]/30">
                      Dispatched on Road
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
