import { Order } from "../types";
import { X, Printer, Download, CheckCircle, ShieldCheck, Building2, Calendar, Clock, Truck } from "lucide-react";

interface ChallanModalProps {
  order: Order | null;
  onClose: () => void;
}

export function ChallanModal({ order, onClose }: ChallanModalProps) {
  if (!order) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm overflow-y-auto">
      <div className="relative w-full max-w-2xl bg-[#FFFFFF] text-[#0E1116] rounded-2xl shadow-2xl overflow-hidden my-8 border border-gray-200">
        {/* Top bar with actions */}
        <div className="flex items-center justify-between px-6 py-3 bg-[#14181F] text-white border-b border-gray-800">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#38A169]" />
            <span className="text-xs font-bold font-mono">DIGITAL RMC DELIVERY CHALLAN</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.print()}
              className="p-1.5 rounded-lg text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Print Challan"
            >
              <Printer className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-300 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Challan Document Body */}
        <div className="p-6 space-y-5 print:p-0">
          {/* Header Banner */}
          <div className="flex justify-between items-start pb-4 border-b-2 border-gray-900">
            <div>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#FF6A00] flex items-center justify-center text-white font-black text-sm">
                  CK
                </div>
                <h1 className="text-xl font-black text-gray-900 tracking-tight">TrackMyRMC</h1>
              </div>
              <p className="text-[11px] font-semibold text-gray-600 mt-1">Ready Mix Concrete Automated Batching Slip</p>
              <p className="text-[10px] text-gray-500 font-mono">Complies with IS 4926 : 2003 Quality Standards</p>
            </div>
            <div className="text-right">
              <span className="text-[10px] font-bold text-gray-500 uppercase">Challan Reference</span>
              <p className="text-base font-black text-gray-900 font-mono">{order.challan_number || "CHL-2026-9901"}</p>
              <p className="text-[11px] text-gray-600">Order: {order.order_number}</p>
            </div>
          </div>

          {/* Plant & Consignee Columns */}
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-[10px] font-bold text-gray-400 uppercase">Batching Plant Origin</span>
              <p className="font-bold text-gray-900 mt-0.5">{order.plant_name}</p>
              <p className="text-gray-600 text-[11px] mt-0.5">Wagle MIDC Industrial Hub, Thane West, MH</p>
              <p className="text-gray-500 text-[10px] font-mono mt-1">GSTIN: 27AABCU1234F1ZM</p>
            </div>

            <div className="p-3 rounded-lg bg-gray-50 border border-gray-200">
              <span className="text-[10px] font-bold text-gray-400 uppercase">Consignee & Pour Site</span>
              <p className="font-bold text-gray-900 mt-0.5">{order.customer_name}</p>
              <p className="text-gray-700 font-medium text-[11px] mt-0.5">{order.site_name}</p>
              <p className="text-gray-600 text-[10px]">{order.site_address}</p>
            </div>
          </div>

          {/* Mix Specifications Table */}
          <div className="border border-gray-300 rounded-lg overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-100 text-gray-700 font-bold border-b border-gray-300">
                <tr>
                  <th className="p-2.5">Mix Design</th>
                  <th className="p-2.5">Quantity</th>
                  <th className="p-2.5">Slump at Batch</th>
                  <th className="p-2.5">W/C Ratio</th>
                  <th className="p-2.5">Admixture</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                <tr className="font-medium text-gray-800">
                  <td className="p-2.5 font-bold font-mono text-[#D65700]">{order.grade} Design Mix</td>
                  <td className="p-2.5 font-bold">{order.quantity_m3} m³</td>
                  <td className="p-2.5">{order.slump}</td>
                  <td className="p-2.5 font-mono">0.42</td>
                  <td className="p-2.5">PCE Superplasticizer (0.8%)</td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Logistics & Transit Timeline */}
          <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-gray-50 border border-gray-200 text-xs">
            <div>
              <span className="text-[10px] text-gray-400 font-bold uppercase">Transit Mixer</span>
              <p className="font-bold text-gray-900 font-mono mt-0.5">{order.tm_number || "MH-04-EK-9214"}</p>
              <p className="text-[11px] text-gray-600">Capacity: 7 m³</p>
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-bold uppercase">Mixer Pilot (Driver)</span>
              <p className="font-bold text-gray-900 mt-0.5">{order.driver_name || "Rameshwar Gurjar"}</p>
              <p className="text-[11px] text-gray-600 font-mono">{order.driver_mobile || "+91 98451 22340"}</p>
            </div>
            <div>
              <span className="text-[10px] text-gray-400 font-bold uppercase">Discharge Window</span>
              <p className="font-bold text-[#D65700] mt-0.5">Max 120 Mins</p>
              <p className="text-[10px] text-gray-500">From plant batching time</p>
            </div>
          </div>

          {/* Verification & Signatures */}
          <div className="pt-4 border-t border-gray-200 grid grid-cols-2 gap-8 text-xs">
            <div>
              <p className="text-[10px] text-gray-500 font-semibold uppercase">Batching Quality In-charge</p>
              <div className="h-10 border-b border-gray-300 flex items-end">
                <span className="font-mono text-[11px] text-gray-700 italic">Er. S. M. Shinde (Digital Sign: #QM-8812)</span>
              </div>
              <p className="text-[10px] text-gray-400 mt-1">Batching Plant Weigher Certified</p>
            </div>

            <div>
              <p className="text-[10px] text-gray-500 font-semibold uppercase">Consignee Site Acceptance</p>
              <div className="h-10 border-b border-gray-300 flex items-end">
                <span className="font-mono text-[11px] text-gray-700 italic">
                  {order.pod ? order.pod.receiver_name : "Pending Site Arrival"}
                </span>
              </div>
              <p className="text-[10px] text-gray-400 mt-1">Authorized Site Receiver Signature</p>
            </div>
          </div>

          {/* Footer Notice */}
          <div className="p-2.5 rounded bg-amber-50 border border-amber-200 text-[10px] text-amber-800 leading-tight">
            <strong>Warning:</strong> Adding extra water on site without authorization from the quality engineer impairs
            concrete strength and voids the manufacturer warranty under IS 456 / IS 4926.
          </div>
        </div>

        {/* Modal Footer */}
        <div className="p-4 bg-gray-100 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-gray-900 hover:bg-black text-white text-xs font-bold transition-all"
          >
            Close Challan
          </button>
        </div>
      </div>
    </div>
  );
}
