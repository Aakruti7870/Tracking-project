import { useState, useEffect } from "react";
import { Order, MixerTelemetry } from "../types";
import { 
  Navigation, 
  Clock, 
  Thermometer, 
  RotateCw, 
  Gauge, 
  Phone, 
  ShieldCheck, 
  FileText, 
  CheckCircle2, 
  AlertCircle,
  Truck,
  Building,
  MapPin,
  Maximize2
} from "lucide-react";

interface LiveTrackerProps {
  order: Order;
  telemetry: MixerTelemetry;
  onUpdateStatus: (orderId: string, status: Order["status"]) => void;
  onOpenChallan: (order: Order) => void;
  onOpenPod: (order: Order) => void;
}

export function LiveTracker({ order, telemetry, onUpdateStatus, onOpenChallan, onOpenPod }: LiveTrackerProps) {
  const [progress, setProgress] = useState(telemetry.progress_percent || 65);
  const [speed, setSpeed] = useState(telemetry.speed_kmh || 38);
  const [rpm, setRpm] = useState(telemetry.drum_rpm || 3.4);
  const [eta, setEta] = useState(telemetry.eta_minutes || 14);

  // Live simulation tick
  useEffect(() => {
    if (order.status !== "DISPATCHED") return;
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 98) return 98;
        return prev + 1;
      });
      setSpeed((prev) => Math.max(25, Math.min(50, prev + (Math.random() * 4 - 2))));
      setEta((prev) => Math.max(2, Math.round(prev - 0.2)));
    }, 3000);
    return () => clearInterval(interval);
  }, [order.status]);

  const stages: { key: Order["status"]; label: string; desc: string }[] = [
    { key: "CONFIRMED", label: "Confirmed", desc: "Batch scheduled" },
    { key: "BATCHING", label: "Batching", desc: "Aggregates mixing" },
    { key: "DISPATCHED", label: "In Transit", desc: "Mixer en-route" },
    { key: "ON_SITE", label: "At Site", desc: "Truck positioned" },
    { key: "POURING", label: "Pouring", desc: "Chute / Pump active" },
    { key: "DELIVERED", label: "Delivered", desc: "POD signed" },
  ];

  const currentStageIndex = stages.findIndex((s) => s.key === order.status);

  // Map coordinates calculation along a curved SVG path
  const pathX = 80 + (progress / 100) * 440;
  const pathY = 120 + Math.sin((progress / 100) * Math.PI) * -50;

  return (
    <div className="bg-[#14181F] border border-[#2D3748] rounded-2xl overflow-hidden shadow-2xl">
      {/* Header */}
      <div className="p-5 border-b border-[#2D3748] bg-gradient-to-r from-[#1A222E] to-[#14181F] flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-[#FF7A18]">
              Live Transit Telemetry
            </span>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#38A169]/20 text-[#38A169] border border-[#38A169]/30">
              GPS Active
            </span>
          </div>
          <h2 className="text-lg font-extrabold text-white mt-0.5 flex items-center gap-2">
            <span>{order.site_name}</span>
            <span className="text-xs px-2 py-0.5 rounded bg-[#1D232D] text-gray-400 font-mono font-normal">
              {order.order_number}
            </span>
          </h2>
          <p className="text-xs text-gray-400">{order.plant_name} → {order.site_address}</p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onOpenChallan(order)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-[#1D232D] hover:bg-[#2D3748] text-white text-xs font-semibold border border-[#374151] transition-all"
          >
            <FileText className="w-3.5 h-3.5 text-[#FF7A18]" />
            <span>Digital Challan</span>
          </button>
          <button
            onClick={() => onOpenPod(order)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#FF6A00] hover:bg-[#FF7A18] text-white text-xs font-bold shadow-md shadow-[#FF6A00]/25 transition-all"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Proof of Delivery</span>
          </button>
        </div>
      </div>

      {/* State Progress Bar */}
      <div className="px-5 py-4 bg-[#0E1116] border-b border-[#1F2937]">
        <div className="grid grid-cols-2 sm:grid-cols-6 gap-2">
          {stages.map((stage, idx) => {
            const isDone = idx < currentStageIndex;
            const isCurrent = idx === currentStageIndex;
            return (
              <button
                key={stage.key}
                onClick={() => onUpdateStatus(order.id, stage.key)}
                className={`p-2.5 rounded-xl border text-left transition-all ${
                  isCurrent
                    ? "bg-[#FF6A00]/15 border-[#FF6A00] text-white shadow-md shadow-[#FF6A00]/15"
                    : isDone
                    ? "bg-[#14181F] border-[#38A169]/40 text-gray-300"
                    : "bg-[#14181F]/40 border-transparent text-gray-500 hover:text-gray-300"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] font-mono uppercase font-bold text-gray-400">Step 0{idx + 1}</span>
                  {isDone ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-[#38A169]" />
                  ) : isCurrent ? (
                    <span className="w-2 h-2 rounded-full bg-[#FF6A00] animate-ping" />
                  ) : null}
                </div>
                <div className={`text-xs font-bold ${isCurrent ? "text-[#FF7A18]" : isDone ? "text-white" : "text-gray-400"}`}>
                  {stage.label}
                </div>
                <div className="text-[10px] text-gray-500 truncate">{stage.desc}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Map & Telemetry HUD Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
        {/* Interactive SVG Route Map */}
        <div className="lg:col-span-8 relative bg-[#0B0E13] p-4 min-h-[320px] flex flex-col justify-between overflow-hidden border-b lg:border-b-0 lg:border-r border-[#2D3748]">
          <div className="absolute top-4 left-4 z-10 flex items-center gap-2 px-3 py-1 rounded-lg bg-[#14181F]/90 backdrop-blur-md border border-[#2D3748] text-xs font-medium text-gray-300">
            <Navigation className="w-3.5 h-3.5 text-[#FF7A18]" />
            <span>Route Simulation (Thane Eastern Exp. Corridor)</span>
          </div>

          <div className="absolute top-4 right-4 z-10 flex items-center gap-2 px-3 py-1 rounded-lg bg-[#14181F]/90 backdrop-blur-md border border-[#2D3748] text-xs font-mono text-white">
            <span className="text-[#38A169]">●</span>
            <span>Progress: {progress}%</span>
          </div>

          {/* Map Vector Graphic */}
          <div className="my-auto py-8">
            <svg viewBox="0 0 600 240" className="w-full h-auto drop-shadow-lg">
              <defs>
                <linearGradient id="routeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#38A169" />
                  <stop offset="50%" stopColor="#FF6A00" />
                  <stop offset="100%" stopColor="#3B82F6" />
                </linearGradient>
                <filter id="glow">
                  <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                  <feMerge>
                    <feMergeNode in="coloredBlur"/>
                    <feMergeNode in="SourceGraphic"/>
                  </feMerge>
                </filter>
              </defs>

              {/* Grid lines simulating map streets */}
              <path d="M 0,60 L 600,60 M 0,120 L 600,120 M 0,180 L 600,180" stroke="#1A222E" strokeWidth="1" strokeDasharray="4,4" />
              <path d="M 120,0 L 120,240 M 240,0 L 240,240 M 360,0 L 360,240 M 480,0 L 480,240" stroke="#1A222E" strokeWidth="1" strokeDasharray="4,4" />

              {/* Highway Route Arc */}
              <path
                d="M 80,120 Q 300,50 520,120"
                fill="none"
                stroke="#252F3F"
                strokeWidth="10"
                strokeLinecap="round"
              />
              <path
                d="M 80,120 Q 300,50 520,120"
                fill="none"
                stroke="url(#routeGrad)"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray="8,4"
              />

              {/* Plant Marker (Start) */}
              <g transform="translate(80, 120)">
                <circle r="18" fill="#12251A" stroke="#38A169" strokeWidth="2" />
                <circle r="6" fill="#38A169" />
                <text x="0" y="32" fill="#9CA3AF" fontSize="11" textAnchor="middle" fontWeight="bold">Batching Plant</text>
              </g>

              {/* Site Marker (Destination) */}
              <g transform="translate(520, 120)">
                <circle r="18" fill="#172554" stroke="#3B82F6" strokeWidth="2" />
                <circle r="6" fill="#3B82F6" />
                <text x="0" y="32" fill="#9CA3AF" fontSize="11" textAnchor="middle" fontWeight="bold">Customer Pour Site</text>
              </g>

              {/* Moving Transit Mixer on Path */}
              <g transform={`translate(${pathX}, ${pathY})`} filter="url(#glow)">
                <circle r="20" fill="#FF6A00" fillOpacity="0.2" className="animate-ping" />
                <circle r="16" fill="#FF6A00" stroke="#FFFFFF" strokeWidth="2" />
                {/* Truck icon representation */}
                <path d="M -6,-4 L 2,-4 L 6,0 L 6,4 L -6,4 Z" fill="white" />
                <circle cx="-3" cy="5" r="2" fill="#14181F" />
                <circle cx="3" cy="5" r="2" fill="#14181F" />
                <text x="0" y="-22" fill="#FFFFFF" fontSize="10" textAnchor="middle" fontWeight="bold" className="font-mono">
                  {order.tm_number || "TM-9214"}
                </text>
              </g>
            </svg>
          </div>

          {/* Quick Simulation Stepper */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-[#1F2937]">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <span className="text-[#FF7A18] font-bold">Simulator Controls:</span>
              <span>Test pipeline transitions</span>
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setProgress((p) => Math.max(5, p - 20))}
                className="px-2.5 py-1 text-xs rounded bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748]"
              >
                Rewind -20%
              </button>
              <button
                onClick={() => setProgress((p) => Math.min(100, p + 20))}
                className="px-2.5 py-1 text-xs rounded bg-[#1D232D] text-gray-300 hover:text-white border border-[#2D3748]"
              >
                Advance +20%
              </button>
              <button
                onClick={() => onUpdateStatus(order.id, "ON_SITE")}
                className="px-3 py-1 text-xs rounded bg-[#38A169]/20 text-[#38A169] border border-[#38A169]/40 font-bold hover:bg-[#38A169]/30"
              >
                Trigger Arrival at Site
              </button>
            </div>
          </div>
        </div>

        {/* Telemetry Dashboard (Right Column) */}
        <div className="lg:col-span-4 p-5 bg-[#14181F] flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#2D3748]">
              <div className="flex items-center gap-2">
                <div className="p-2 rounded-xl bg-[#FF6A00]/10 text-[#FF7A18]">
                  <Truck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">{order.tm_number || "MH-04-EK-9214"}</h3>
                  <p className="text-[11px] text-gray-400">Schwing Stetter 7m³ Mixer</p>
                </div>
              </div>
              <span className="px-2 py-1 rounded bg-[#12251A] text-[#38A169] text-xs font-mono font-bold">
                {order.quantity_m3} m³ Loaded
              </span>
            </div>

            {/* Driver Profile Card */}
            <div className="mt-4 p-3 rounded-xl bg-[#1D232D] border border-[#2D3748] flex items-center justify-between">
              <div>
                <span className="text-[10px] text-gray-400 uppercase font-semibold">Assigned Mixer Pilot</span>
                <p className="text-xs font-bold text-white">{order.driver_name || "Rameshwar Gurjar"}</p>
                <p className="text-[11px] text-gray-400 font-mono">{order.driver_mobile || "+91 98451 22340"}</p>
              </div>
              <a
                href={`tel:${order.driver_mobile || "+919845122340"}`}
                className="p-2.5 rounded-xl bg-[#38A169] text-white hover:bg-[#276749] transition-all"
                title="Call Driver"
              >
                <Phone className="w-4 h-4" />
              </a>
            </div>

            {/* Live Telemetry Sensors */}
            <div className="grid grid-cols-2 gap-3 mt-4">
              {/* Drum Rotation */}
              <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                <div className="flex items-center justify-between text-gray-400 mb-1">
                  <span className="text-[11px]">Drum Rotation</span>
                  <RotateCw className="w-3.5 h-3.5 text-[#FF7A18] animate-spin" />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-bold font-mono text-white">{rpm}</span>
                  <span className="text-xs text-gray-400">RPM</span>
                </div>
                <p className="text-[10px] text-[#38A169] font-medium mt-0.5">Agitation Mode (CW)</p>
              </div>

              {/* Transit Speed */}
              <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                <div className="flex items-center justify-between text-gray-400 mb-1">
                  <span className="text-[11px]">Road Speed</span>
                  <Gauge className="w-3.5 h-3.5 text-[#3B82F6]" />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-bold font-mono text-white">{Math.round(speed)}</span>
                  <span className="text-xs text-gray-400">km/h</span>
                </div>
                <p className="text-[10px] text-gray-400 mt-0.5">Smooth flow, no harsh brakes</p>
              </div>

              {/* Concrete Temperature */}
              <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                <div className="flex items-center justify-between text-gray-400 mb-1">
                  <span className="text-[11px]">Mix Temp</span>
                  <Thermometer className="w-3.5 h-3.5 text-[#E53E3E]" />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-bold font-mono text-white">27.4</span>
                  <span className="text-xs text-gray-400">°C</span>
                </div>
                <p className="text-[10px] text-[#38A169] mt-0.5">Optimal (IS:456 &lt;32°C)</p>
              </div>

              {/* ETA Countdown */}
              <div className="p-3 rounded-xl bg-[#1D232D] border border-[#2D3748]">
                <div className="flex items-center justify-between text-gray-400 mb-1">
                  <span className="text-[11px]">Site ETA</span>
                  <Clock className="w-3.5 h-3.5 text-[#FF7A18]" />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className="text-xl font-bold font-mono text-[#FF7A18]">~{eta}</span>
                  <span className="text-xs text-gray-400">mins</span>
                </div>
                <p className="text-[10px] text-gray-400 mt-0.5">Target: {order.delivery_time}</p>
              </div>
            </div>
          </div>

          {/* Quality Gating Verification Badge */}
          <div className="p-3 rounded-xl bg-[#12251A] border border-[#38A169]/30 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-[#38A169] shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-bold text-white">IS 4926 Quality Assured</p>
              <p className="text-[10px] text-gray-400 leading-tight mt-0.5">
                Batch weight tickets verified at automated plant weigher. Batch water-cement ratio: 0.42.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
