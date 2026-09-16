import { UserRole } from "../types";
import { 
  Building2, 
  Truck, 
  HardHat, 
  Radio, 
  ShieldCheck, 
  Clock, 
  Menu, 
  X,
  Plus
} from "lucide-react";
import { useState } from "react";

interface NavbarProps {
  currentRole: UserRole;
  onSelectRole: (role: UserRole) => void;
  onOpenNewOrder: () => void;
  orderCount: number;
}

export function Navbar({ currentRole, onSelectRole, onOpenNewOrder, orderCount }: NavbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const roles: { role: UserRole; label: string; icon: typeof HardHat; badge?: string }[] = [
    { role: UserRole.Customer, label: "Customer / Builder", icon: HardHat },
    { role: UserRole.Driver, label: "Driver (Mixer Pilot)", icon: Truck },
    { role: UserRole.PlantOwner, label: "Plant Operations", icon: Building2 },
    { role: UserRole.Dispatcher, label: "Fleet & Dispatch", icon: Radio },
    { role: UserRole.CentralAdmin, label: "Central Admin", icon: ShieldCheck },
  ];

  return (
    <header className="sticky top-0 z-40 bg-[#0E1116]/95 backdrop-blur-md border-b border-[#1F2937]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#FF7A18] to-[#FF6A00] flex items-center justify-center text-white font-extrabold text-base shadow-lg shadow-[#FF6A00]/25">
              CK
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-white tracking-tight">TrackMyRMC</span>
                <span className="hidden sm:inline-block px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded-full bg-[#FF6A00]/20 text-[#FF7A18] border border-[#FF6A00]/30">
                  RMC Master
                </span>
              </div>
              <p className="text-[11px] text-gray-400 -mt-0.5">Concrete Ordering & Operations</p>
            </div>
          </div>

          {/* Role Navigation Pills (Desktop) */}
          <nav className="hidden md:flex items-center gap-1.5 p-1 bg-[#14181F] rounded-xl border border-[#2D3748]">
            {roles.map((r) => {
              const Icon = r.icon;
              const active = currentRole === r.role;
              return (
                <button
                  key={r.role}
                  id={`role-btn-${r.role}`}
                  onClick={() => onSelectRole(r.role)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    active
                      ? "bg-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/30"
                      : "text-gray-300 hover:text-white hover:bg-white/5"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{r.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Quick Action Button & Live Status */}
          <div className="flex items-center gap-3">
            <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#12251A] border border-[#38A169]/30 text-[#38A169] text-xs font-medium">
              <span className="w-2 h-2 rounded-full bg-[#38A169] animate-pulse" />
              <span>Telemetry Live</span>
            </div>

            <button
              id="new-order-navbar-btn"
              onClick={onOpenNewOrder}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-gradient-to-r from-[#FF7A18] to-[#FF6A00] text-white font-semibold text-xs shadow-md shadow-[#FF6A00]/25 hover:brightness-110 active:scale-95 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Book Concrete</span>
              <span className="sm:hidden">Book</span>
            </button>

            {/* Mobile menu toggle */}
            <button
              id="mobile-menu-toggle"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-[#1D232D]"
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-[#1F2937] bg-[#14181F] px-4 py-3 space-y-2">
          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-wider px-2">Switch Workspace</p>
          <div className="grid grid-cols-1 gap-1">
            {roles.map((r) => {
              const Icon = r.icon;
              const active = currentRole === r.role;
              return (
                <button
                  key={r.role}
                  onClick={() => {
                    onSelectRole(r.role);
                    setMobileMenuOpen(false);
                  }}
                  className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    active ? "bg-[#FF6A00] text-white" : "text-gray-300 hover:bg-[#1D232D]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{r.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
}
