import { useState, useEffect } from "react";
import { ConcreteGrade, Plant, PumpType } from "../types";
import { X, Check, Building, MapPin, Calendar, Clock, DollarSign, Truck } from "lucide-react";

interface OrderModalProps {
  isOpen: boolean;
  onClose: () => void;
  plants: Plant[];
  initialData?: {
    grade?: ConcreteGrade;
    quantity?: number;
    notes?: string;
  };
  onSubmit: (orderData: {
    plant_id: string;
    grade: ConcreteGrade;
    quantity_m3: number;
    site_name: string;
    site_address: string;
    delivery_date: string;
    delivery_time: string;
    pump_type: PumpType;
    slump: string;
    rate_per_m3: number;
    total_amount: number;
  }) => void;
}

export function OrderModal({ isOpen, onClose, plants, initialData, onSubmit }: OrderModalProps) {
  const [selectedPlantId, setSelectedPlantId] = useState<string>(plants[0]?.id || "plant-1");
  const [grade, setGrade] = useState<ConcreteGrade>(initialData?.grade || "M25");
  const [quantity, setQuantity] = useState<number>(initialData?.quantity || 24);
  const [siteName, setSiteName] = useState<string>("Lodha World One - Phase 2");
  const [siteAddress, setSiteAddress] = useState<string>("Senapati Bapat Marg, Lower Parel, Mumbai 400013");
  const [deliveryDate, setDeliveryDate] = useState<string>("Today, 14 Sep 2026");
  const [deliveryTime, setDeliveryTime] = useState<string>("10:30 AM");
  const [pumpType, setPumpType] = useState<PumpType>("Boom Pump (36m)");
  const [slump, setSlump] = useState<string>("120 ± 25 mm");

  useEffect(() => {
    if (initialData?.grade) setGrade(initialData.grade);
    if (initialData?.quantity) setQuantity(initialData.quantity);
  }, [initialData]);

  if (!isOpen) return null;

  const currentPlant = plants.find((p) => p.id === selectedPlantId) || plants[0];
  
  // Rate calculation
  const gradeMultiplier: Record<ConcreteGrade, number> = {
    M10: 0.88,
    M15: 0.92,
    M20: 0.96,
    M25: 1.0,
    M30: 1.06,
    M35: 1.12,
    M40: 1.20,
    M50: 1.35,
  };

  const baseRate = currentPlant?.base_rate_m25 || 4200;
  const ratePerM3 = Math.round(baseRate * (gradeMultiplier[grade] || 1));
  const pumpCharge = pumpType.includes("Boom") ? 6500 : pumpType.includes("Line") ? 4500 : 0;
  const subtotal = ratePerM3 * quantity + pumpCharge;
  const gst18 = Math.round(subtotal * 0.18);
  const totalAmount = subtotal + gst18;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit({
      plant_id: selectedPlantId,
      grade,
      quantity_m3: quantity,
      site_name: siteName,
      site_address: siteAddress,
      delivery_date: deliveryDate,
      delivery_time: deliveryTime,
      pump_type: pumpType,
      slump,
      rate_per_m3: ratePerM3,
      total_amount: totalAmount,
    });
    onClose();
  };

  const grades: ConcreteGrade[] = ["M15", "M20", "M25", "M30", "M35", "M40", "M50"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-[#14181F] border border-[#2D3748] rounded-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#2D3748] bg-[#1D232D]">
          <div>
            <span className="text-[10px] font-bold tracking-widest text-[#FF7A18] uppercase">New RMC Requisition</span>
            <h3 className="text-lg font-bold text-white">Book Ready Mix Concrete Batch</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Plant Selector */}
          <div>
            <label className="block text-xs font-semibold text-gray-300 mb-1.5">Select Batching Plant</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              {plants.map((p) => {
                const active = selectedPlantId === p.id;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setSelectedPlantId(p.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      active
                        ? "bg-[#FF6A00]/15 border-[#FF6A00] text-white"
                        : "bg-[#1D232D] border-[#2D3748] text-gray-400 hover:border-gray-600"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-bold truncate text-white">{p.company}</span>
                      {active && <Check className="w-3.5 h-3.5 text-[#FF7A18]" />}
                    </div>
                    <p className="text-[11px] text-gray-400 truncate">{p.city}</p>
                    <p className="text-[10px] text-[#38A169] mt-1 font-mono">₹{p.base_rate_m25}/m³ base</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Grade & Quantity */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Concrete Grade</label>
              <div className="flex flex-wrap gap-1.5">
                {grades.map((g) => (
                  <button
                    key={g}
                    type="button"
                    onClick={() => setGrade(g)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold font-mono transition-all ${
                      grade === g
                        ? "bg-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/25"
                        : "bg-[#1D232D] text-gray-400 hover:text-white border border-[#2D3748]"
                    }`}
                  >
                    {g}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Order Volume (m³)</label>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="6"
                  max="500"
                  step="1"
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(6, parseInt(e.target.value) || 6))}
                  className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3.5 py-2 text-sm text-white font-bold focus:border-[#FF6A00] focus:outline-none"
                  required
                />
                <span className="text-xs font-bold text-gray-400 whitespace-nowrap font-mono">
                  ≈ {Math.ceil(quantity / 6)} Truckloads
                </span>
              </div>
            </div>
          </div>

          {/* Pump Type & Slump */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Placement / Pump Equipment</label>
              <select
                value={pumpType}
                onChange={(e) => setPumpType(e.target.value as PumpType)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white font-medium focus:border-[#FF6A00] focus:outline-none"
              >
                <option value="Boom Pump (36m)">Boom Pump (36m) - High rise / Slab</option>
                <option value="Line Pump (100m)">Line Pump (100m) - Pipeline discharge</option>
                <option value="None (Direct Discharge)">Direct Chute Discharge (No Pump)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Slump Tolerance</label>
              <select
                value={slump}
                onChange={(e) => setSlump(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white font-medium focus:border-[#FF6A00] focus:outline-none"
              >
                <option value="120 ± 25 mm">120 ± 25 mm (Standard Pumpable)</option>
                <option value="140 ± 25 mm">140 ± 25 mm (Heavily Reinforced)</option>
                <option value="100 ± 25 mm">100 ± 25 mm (Pavement / Direct Chute)</option>
              </select>
            </div>
          </div>

          {/* Site Details */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Site Name / Tower</label>
              <input
                type="text"
                value={siteName}
                onChange={(e) => setSiteName(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#FF6A00] focus:outline-none"
                placeholder="e.g. Tower B - 5th Floor Slab"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Delivery Address</label>
              <input
                type="text"
                value={siteAddress}
                onChange={(e) => setSiteAddress(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#FF6A00] focus:outline-none"
                placeholder="Full delivery location"
                required
              />
            </div>
          </div>

          {/* Schedule */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Delivery Date</label>
              <input
                type="text"
                value={deliveryDate}
                onChange={(e) => setDeliveryDate(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#FF6A00] focus:outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-300 mb-1.5">Preferred Pour Start Time</label>
              <input
                type="text"
                value={deliveryTime}
                onChange={(e) => setDeliveryTime(e.target.value)}
                className="w-full bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-2 text-xs text-white focus:border-[#FF6A00] focus:outline-none"
                required
              />
            </div>
          </div>

          {/* Pricing Calculation Summary */}
          <div className="bg-[#1D232D] border border-[#2D3748] rounded-xl p-4 space-y-2">
            <div className="flex justify-between text-xs text-gray-300">
              <span>RMC Rate ({grade} @ ₹{ratePerM3}/m³ × {quantity}m³):</span>
              <span className="font-mono">₹{(ratePerM3 * quantity).toLocaleString("en-IN")}</span>
            </div>
            {pumpCharge > 0 && (
              <div className="flex justify-between text-xs text-gray-300">
                <span>{pumpType} Fixed Setup:</span>
                <span className="font-mono">₹{pumpCharge.toLocaleString("en-IN")}</span>
              </div>
            )}
            <div className="flex justify-between text-xs text-gray-400">
              <span>GST @ 18%:</span>
              <span className="font-mono">₹{gst18.toLocaleString("en-IN")}</span>
            </div>
            <div className="pt-2 border-t border-[#374151] flex justify-between items-baseline">
              <span className="text-sm font-bold text-white">Estimated Total Payable:</span>
              <span className="text-lg font-extrabold text-[#38A169] font-mono">
                ₹{totalAmount.toLocaleString("en-IN")}
              </span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              id="confirm-order-submit-btn"
              type="submit"
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-[#FF7A18] to-[#FF6A00] text-white font-bold text-xs shadow-lg shadow-[#FF6A00]/25 hover:brightness-110 active:scale-95 transition-all"
            >
              Confirm & Issue Purchase Order
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
