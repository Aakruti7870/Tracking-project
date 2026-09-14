import { useState, useMemo } from "react";
import { ConcreteGrade } from "../types";
import { Calculator, CheckCircle2, ArrowRight, Layers, Box, Columns3, Compass } from "lucide-react";

interface PourPlannerProps {
  onApplyCalculation: (data: { grade: ConcreteGrade; quantity: number; notes: string }) => void;
}

type StructureType = "slab" | "column" | "beam" | "footing" | "retaining_wall";

export function PourPlanner({ onApplyCalculation }: PourPlannerProps) {
  const [structure, setStructure] = useState<StructureType>("slab");
  
  // Dimensions in meters
  const [length, setLength] = useState<number>(12);
  const [width, setWidth] = useState<number>(8);
  const [thickness, setThickness] = useState<number>(0.15); // 150mm standard slab
  const [count, setCount] = useState<number>(1);
  const [wastage, setWastage] = useState<number>(5); // 5% standard

  // Recommended grades by structure
  const gradeRecommendations: Record<StructureType, ConcreteGrade> = {
    slab: "M25",
    column: "M35",
    beam: "M30",
    footing: "M20",
    retaining_wall: "M30",
  };

  const selectedGrade = gradeRecommendations[structure];

  // Volume calculations
  const { netVolume, grossVolume, mixerLoads } = useMemo(() => {
    let baseVolume = 0;
    if (structure === "slab" || structure === "footing" || structure === "retaining_wall") {
      baseVolume = length * width * thickness * count;
    } else if (structure === "column" || structure === "beam") {
      baseVolume = length * width * thickness * count;
    }
    const net = Math.round(baseVolume * 100) / 100;
    const gross = Math.round(net * (1 + wastage / 100) * 10) / 10;
    const loads = Math.ceil(gross / 6); // 6 m³ standard transit mixer
    return {
      netVolume: net,
      grossVolume: Math.max(1, gross),
      mixerLoads: loads,
    };
  }, [length, width, thickness, count, wastage, structure]);

  const structureOptions = [
    { id: "slab", label: "Slab & Raft", icon: Layers, desc: "Roof, floor, or foundation raft" },
    { id: "column", label: "RCC Columns", icon: Columns3, desc: "Vertical structural columns" },
    { id: "beam", label: "Plinth / Beams", icon: Box, desc: "Horizontal tie & roof beams" },
    { id: "footing", label: "Footings", icon: Compass, desc: "Isolated or strip footings" },
  ];

  return (
    <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 lg:p-6 shadow-xl">
      <div className="flex items-center justify-between pb-4 border-b border-[#2D3748]">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18] border border-[#FF6A00]/20">
            <Calculator className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Concrete Pour Planner & Volume Estimator</h2>
            <p className="text-xs text-gray-400">IS 456 compliant calculation with transit load estimation</p>
          </div>
        </div>
        <span className="hidden sm:inline-block text-[11px] px-2.5 py-1 rounded-full bg-[#1F2937] text-gray-300 font-medium border border-[#374151]">
          Standard 6m³ / Mixer
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-5">
        {/* Left: Configuration Form */}
        <div className="lg:col-span-7 space-y-5">
          {/* Structure Selector */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-2">Select Structural Element</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {structureOptions.map((opt) => {
                const Icon = opt.icon;
                const active = structure === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      setStructure(opt.id as StructureType);
                      if (opt.id === "column") {
                        setLength(0.45);
                        setWidth(0.45);
                        setThickness(3.0);
                        setCount(12);
                      } else if (opt.id === "beam") {
                        setLength(6.0);
                        setWidth(0.3);
                        setThickness(0.45);
                        setCount(8);
                      } else if (opt.id === "footing") {
                        setLength(1.8);
                        setWidth(1.8);
                        setThickness(0.6);
                        setCount(10);
                      } else {
                        setLength(12);
                        setWidth(8);
                        setThickness(0.15);
                        setCount(1);
                      }
                    }}
                    className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition-all ${
                      active
                        ? "bg-[#FF6A00]/15 border-[#FF6A00] text-white"
                        : "bg-[#1D232D] border-[#2D3748] text-gray-400 hover:text-gray-200 hover:border-[#374151]"
                    }`}
                  >
                    <Icon className={`w-4 h-4 mb-1.5 ${active ? "text-[#FF7A18]" : "text-gray-400"}`} />
                    <span className="text-xs font-semibold">{opt.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Dimension Inputs */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                {structure === "column" ? "Width / B (m)" : "Length (m)"}
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                value={length}
                onChange={(e) => setLength(Math.max(0.1, parseFloat(e.target.value) || 0.1))}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-sm text-white font-semibold focus:border-[#FF6A00] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                {structure === "column" ? "Depth / D (m)" : "Width (m)"}
              </label>
              <input
                type="number"
                step="0.05"
                min="0.1"
                value={width}
                onChange={(e) => setWidth(Math.max(0.1, parseFloat(e.target.value) || 0.1))}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-sm text-white font-semibold focus:border-[#FF6A00] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">
                {structure === "column" ? "Height (m)" : "Thickness / Depth (m)"}
              </label>
              <input
                type="number"
                step="0.01"
                min="0.05"
                value={thickness}
                onChange={(e) => setThickness(Math.max(0.01, parseFloat(e.target.value) || 0.05))}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-sm text-white font-semibold focus:border-[#FF6A00] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-400 mb-1">Number of Units</label>
              <input
                type="number"
                min="1"
                step="1"
                value={count}
                onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-sm text-white font-semibold focus:border-[#FF6A00] focus:outline-none"
              />
            </div>
            <div className="col-span-2">
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-gray-400">Pumping & Placement Allowance</label>
                <span className="text-xs font-bold text-[#FF7A18]">+{wastage}% Margin</span>
              </div>
              <input
                type="range"
                min="2"
                max="12"
                step="1"
                value={wastage}
                onChange={(e) => setWastage(parseInt(e.target.value))}
                className="w-full accent-[#FF6A00] bg-[#1D232D] rounded-lg cursor-pointer h-2"
              />
              <p className="text-[10px] text-gray-500 mt-1">Recommended: 5% for slabs, 7% for boom pumps, 10% for deep shafts</p>
            </div>
          </div>
        </div>

        {/* Right: Real-time Calculation Summary Card */}
        <div className="lg:col-span-5 bg-gradient-to-br from-[#1A222E] to-[#12161E] border border-[#2D3748] rounded-xl p-5 flex flex-col justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-[#FF7A18]">Estimated Requirement</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-4xl font-black text-white">{grossVolume}</span>
              <span className="text-xl font-bold text-gray-400">m³</span>
              <span className="text-xs text-gray-400 ml-auto font-mono">Net: {netVolume} m³</span>
            </div>

            <div className="mt-4 pt-4 border-t border-[#2D3748] space-y-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Recommended Grade:</span>
                <span className="px-2 py-0.5 rounded bg-[#FF6A00]/20 text-[#FF7A18] font-bold font-mono">
                  {selectedGrade}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Recommended Slump:</span>
                <span className="text-white font-medium">120 ± 25 mm (Pumpable)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Transit Mixer Requirement:</span>
                <span className="text-[#38A169] font-bold">
                  {mixerLoads} Truckload{mixerLoads > 1 ? "s" : ""} (~6 m³ each)
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Approx. Pour Duration:</span>
                <span className="text-white font-medium">{Math.round(grossVolume / 15 * 60)} - {Math.round(grossVolume / 10 * 60)} mins</span>
              </div>
            </div>
          </div>

          <div className="mt-5 pt-4 border-t border-[#2D3748]">
            <button
              id="apply-calculation-btn"
              type="button"
              onClick={() =>
                onApplyCalculation({
                  grade: selectedGrade,
                  quantity: grossVolume,
                  notes: `${structure.toUpperCase()}: ${count} unit(s), ${length}m x ${width}m x ${thickness}m (+${wastage}% margin)`,
                })
              }
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-[#FF6A00] text-white font-bold text-xs shadow-lg shadow-[#FF6A00]/25 hover:bg-[#FF7A18] active:scale-[0.98] transition-all"
            >
              <span>Transfer to Order Form</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <p className="text-[10px] text-center text-gray-500 mt-2">Calculations align with Indian Standard IS 456:2000</p>
          </div>
        </div>
      </div>
    </div>
  );
}
