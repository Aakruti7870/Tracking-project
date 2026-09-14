import { useState } from "react";
import { Order, Plant } from "../types";
import { 
  ShieldCheck, 
  Users, 
  Building2, 
  Activity, 
  AlertTriangle, 
  Key, 
  Lock, 
  Unlock, 
  RefreshCw, 
  CheckCircle2, 
  FileText 
} from "lucide-react";

interface CentralAdminViewProps {
  orders: Order[];
  plants: Plant[];
}

export function CentralAdminView({ orders, plants }: CentralAdminViewProps) {
  const [adminTab, setAdminTab] = useState<"overview" | "workspaces" | "security" | "audit">("overview");
  const [elevatedAccess, setElevatedAccess] = useState(false);
  const [passcode, setPasscode] = useState("");
  const [passcodeError, setPasscodeError] = useState(false);

  const handleStepUpAuth = (e: React.FormEvent) => {
    e.preventDefault();
    if (passcode === "7870" || passcode === "admin123" || passcode === "rmc2026") {
      setElevatedAccess(true);
      setPasscodeError(false);
    } else {
      setPasscodeError(true);
    }
  };

  const auditLogs = [
    { timestamp: "10:14:22", action: "BATCH_DISPATCHED", user: "system@plant1", details: "Order RMC-2026-8819 weigher ticket cleared" },
    { timestamp: "09:45:10", action: "POD_SIGNED", user: "driver_rameshwar", details: "Site signature captured for Lodha Amara" },
    { timestamp: "09:12:05", action: "STEP_UP_AUTH", user: "admin@trackmyrmc", details: "Privileged token issued for Session #8812" },
    { timestamp: "08:30:19", action: "PLANT_VERIFIED", user: "reviewer@platform", details: "UltraTech Wagle hub safety audit passed" },
  ];

  return (
    <div className="space-y-6">
      {/* Admin Command Header */}
      <div className="p-5 rounded-2xl bg-[#14181F] border border-[#2D3748] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18]">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-white">Central Admin & Governance Command</h2>
              {elevatedAccess ? (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#12251A] text-[#38A169] border border-[#38A169]/30">
                  Elevated Root
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-950/40 text-amber-400 border border-amber-800/40">
                  Standard Mode
                </span>
              )}
            </div>
            <p className="text-xs text-gray-400">TrackMyRMC Multi-tenant Core & Role Security Matrix</p>
          </div>
        </div>

        {/* Elevate Privileges button */}
        {!elevatedAccess ? (
          <form onSubmit={handleStepUpAuth} className="flex items-center gap-2">
            <input
              type="password"
              placeholder="Admin PIN (e.g. 7870)"
              value={passcode}
              onChange={(e) => {
                setPasscode(e.target.value);
                setPasscodeError(false);
              }}
              className="bg-[#1D232D] border border-[#2D3748] rounded-xl px-3 py-1.5 text-xs text-white focus:border-[#FF6A00] focus:outline-none w-36"
            />
            <button
              type="submit"
              className="px-3 py-1.5 rounded-xl bg-[#FF6A00] text-white text-xs font-bold hover:bg-[#FF7A18]"
            >
              Elevate
            </button>
            {passcodeError && <span className="text-[10px] text-red-400">PIN: 7870</span>}
          </form>
        ) : (
          <button
            onClick={() => setElevatedAccess(false)}
            className="px-3 py-1.5 rounded-xl bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748] text-xs font-semibold"
          >
            Revoke Elevation
          </button>
        )}
      </div>

      {/* Admin Tabs */}
      <div className="flex gap-2 border-b border-[#2D3748] pb-3">
        <button
          onClick={() => setAdminTab("overview")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            adminTab === "overview" ? "bg-[#FF6A00] text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Operations Overview
        </button>
        <button
          onClick={() => setAdminTab("workspaces")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            adminTab === "workspaces" ? "bg-[#FF6A00] text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          RBAC & Plant Workspaces
        </button>
        <button
          onClick={() => setAdminTab("audit")}
          className={`px-4 py-2 rounded-xl text-xs font-bold transition-all ${
            adminTab === "audit" ? "bg-[#FF6A00] text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          Audit Stream
        </button>
      </div>

      {adminTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-5 rounded-2xl bg-[#14181F] border border-[#2D3748]">
            <span className="text-xs text-gray-400 font-semibold">Total Platform Volume</span>
            <p className="text-3xl font-black text-white mt-1">
              {orders.reduce((a, b) => a + b.quantity_m3, 0)} <span className="text-sm font-normal text-gray-400">m³</span>
            </p>
            <p className="text-[11px] text-[#38A169] mt-2">↑ 14.8% vs last week</p>
          </div>

          <div className="p-5 rounded-2xl bg-[#14181F] border border-[#2D3748]">
            <span className="text-xs text-gray-400 font-semibold">Gross Order Value</span>
            <p className="text-3xl font-black text-white font-mono mt-1">
              ₹{(orders.reduce((a, b) => a + b.total_amount, 0) / 100000).toFixed(1)} <span className="text-sm font-normal text-gray-400">Lakhs</span>
            </p>
            <p className="text-[11px] text-[#38A169] mt-2">All escrow accounts active</p>
          </div>

          <div className="p-5 rounded-2xl bg-[#14181F] border border-[#2D3748]">
            <span className="text-xs text-gray-400 font-semibold">API Microservices</span>
            <p className="text-3xl font-black text-[#38A169] mt-1">Operational</p>
            <p className="text-[11px] text-gray-400 mt-2">CAN-Bus telematics, Auth, Billing: 99.98%</p>
          </div>
        </div>
      )}

      {adminTab === "workspaces" && (
        <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 shadow-xl space-y-4">
          <h3 className="text-sm font-bold text-white">Registered RMC Plant Franchises & Verification</h3>
          <div className="divide-y divide-[#2D3748]">
            {plants.map((p) => (
              <div key={p.id} className="py-3 flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold text-white">{p.name}</p>
                  <p className="text-[11px] text-gray-400">{p.address}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#12251A] text-[#38A169]">
                    Verified
                  </span>
                  <span className="text-xs text-gray-400 font-mono">Rating: {p.rating}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {adminTab === "audit" && (
        <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl p-5 shadow-xl">
          <h3 className="text-sm font-bold text-white mb-4">Immutable Audit Trail</h3>
          <div className="space-y-2 font-mono text-xs">
            {auditLogs.map((log, i) => (
              <div key={i} className="p-2.5 rounded-lg bg-[#1D232D] border border-[#2D3748] flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-gray-500">{log.timestamp}</span>
                  <span className="px-1.5 py-0.5 rounded bg-[#FF6A00]/20 text-[#FF7A18] font-bold text-[10px]">
                    {log.action}
                  </span>
                  <span className="text-gray-300">{log.details}</span>
                </div>
                <span className="text-gray-500 text-[10px]">{log.user}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
